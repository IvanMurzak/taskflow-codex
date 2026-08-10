# Submodule sync — detection, per-round sync, guarded pointer bump

Reference module for `taskflow-execute`. It is loaded **only** when
`git submodule status` is non-empty **and** `--submodules != off`. In a
repository without submodules it is never read, which is what keeps the default
invocation cheap.

Read this as the orchestrator. Everything here is an orchestrator action at a
round boundary: workers never run `git submodule` or `git worktree` in the
superproject, and never perform any part of this procedure.

**This module is host-neutral, and deliberately so.** Every command below is
`git`, `gh` or `pipeline`; none of it depends on how workers were dispatched or
on what isolates them. It is therefore the same text as the Claude plugin's copy
apart from two marked places: the worked example names this plugin's repository,
and §8 notes what "workers never run this" is worth on a host that does not
enforce it.

---

## 1. Detection

```
git submodule status
```

**Non-empty output is the whole test.** No parsing of `.gitmodules`, no
directory probing, no heuristic.

| `--submodules` | Meaning |
|---|---|
| `auto` *(default)* | Run the sync **only** when `git submodule status` is non-empty. That is exactly what `auto` means — nothing more. |
| `off` | Suppress both this runbook and the sync. Pointers are left where they are. Say so once in the run report; do not repeat it per round. |

Run detection once, at preflight, from the superproject root. The result holds
for the whole run.

Reading the output:

- A line with a **`-` prefix** is an uninitialized submodule. It has no checkout,
  so it received no merge and never enters the sync. Do **not** run
  `git submodule update --init` as part of the sync — initializing a submodule
  is a workspace setup decision, not a consequence of a task merging.
- A line with a **`+` prefix** means the checked-out commit differs from the
  recorded pointer. That is drift, and it may well predate this run. §6 explains
  why the round's bump names its submodules explicitly instead of sweeping up
  whatever happens to be drifted.

---

## 2. What the sync is, and when it runs

**Per round, not per task.** The sync is a round-boundary action:

> verify the round's tasks → commit the board → **sync** → recompute the ready set

One sync per dispatch round, producing **one pointer-bump commit per round** —
a count separate from, and not to be confused with, the board's own two
per-round commits at dispatch and outcome (`SKILL.md` §9). Three tasks that
merged into the same submodule in one round produce one fast-forward and one
pointer bump between them, not three.

**Only submodules that actually received a merge this round are touched.** Build
the round's touched set from merge evidence, not from `.gitmodules`: for each row
that reached verified-complete this round via a merged PR, map the repository
that PR merged into to its submodule path. A submodule with no merge this round
is not fetched, not fast-forwarded, and not bumped.

Do not sync mid-round between dispatches. A pointer that moves under a running
worker's feet buys nothing and multiplies commits.

---

## 3. Determining each submodule's integration branch

**The integration branch is not uniform across submodules, and assuming `main`
everywhere is wrong.** Determine it; never hard-code it. First rung that answers
wins:

1. **The branch the round's merged PR actually targeted.** Ground truth for
   "what received the merge":
   ```
   gh pr view <n> --repo <owner>/<name> --json baseRefName -q .baseRefName
   ```
2. **The task's declared base** — the `base_branch` frontmatter of the task spec,
   or the base the slot was provisioned with.
3. **The `.gitmodules` declaration**, when one exists:
   ```
   git config -f .gitmodules --get submodule.<name>.branch
   ```
   Often absent. When it is absent this rung answers nothing and the ladder falls
   through — an absent key is not a vote for `main`.
4. **The submodule's remote default branch**, last resort:
   ```
   git -C <path> symbolic-ref --short refs/remotes/origin/HEAD
   ```
   (`git -C <path> remote set-head origin --auto` first if it is unset.)

Resolve once per submodule per run, record the answer, and reuse it.

**Rung 4 is last for a concrete reason.** A gated repository's remote default
branch can still be `main` while every PR targets `next`. Asking the remote what
its default is would then answer confidently and wrongly. The branch that
received the merge is the branch to fast-forward.

### Worked example — this workspace

| Repository | Integration branch |
|---|---|
| superproject (parent) | `main` |
| `public/package/pipeline` | `main` |
| `public/plugin/taskflow-codex` | **`next`** |
| `public/plugin/taskflow-claude` | **`next`** |

The two plugin repositories are **gated**: pull requests target `next`, and
`main` moves only when the owner promotes it, because marketplace entries install
from `main`. A sync that fast-forwarded `main` in `taskflow-codex` would be
advancing a branch this round never touched — a no-op at best, and a publish at
worst. Meanwhile `pipeline` in the same workspace really does integrate on
`main`. Both facts have to come out of the same procedure.

### Do not use `git submodule update --remote`

It resolves a branch by its own rules (the `.gitmodules` key, else the remote
default), moves **every** submodule including the ones this round never touched,
and writes the superproject index in whichever checkout you ran it from. Every
one of those is wrong here.

---

## 4. The fetch constraint

This is the trap this document exists to prevent.

### The failing form — do not use it

```
git -C <path> fetch origin main:main        # ✗ fails during a taskflow run
```

```
fatal: refusing to fetch into branch 'refs/heads/main' checked out at '<checkout>'
```

Exit **128**. The refspec form `<src>:<dst>` writes the local branch ref, and git
refuses to move a branch that **any** worktree of that repository has checked
out — including the worktree you are currently standing in. A taskflow run
guarantees that condition: workers hold worktrees of these repositories, and the
main checkout sits on the base branch. So this form does not "usually work and
occasionally fail"; during a parallel run it fails.

### Safe form 1 — fast-forward from the checkout that has the branch out

```
git -C <checkout> pull --ff-only
```

or, when the branch has no configured upstream:

```
git -C <checkout> fetch origin <branch>
git -C <checkout> merge --ff-only origin/<branch>
```

Use this wherever the **local branch must actually move**. It requires that
checkout to be on that branch and clean — for the main checkout, preflight's
clean-tree gate already guarantees this.

### Safe form 2 — fetch remote-tracking only, read `origin/<base>`

```
git -C <path> fetch origin
git -C <path> rev-parse origin/<base>
```

No local branch is written, so this works from any worktree regardless of what is
checked out anywhere. Use it wherever you only need to **know** where the branch
now is: deciding whether a pointer moved, comparing a slot's base, confirming a
merge landed.

### Which form applies where

| Need | Where you stand | Form |
|---|---|---|
| Move the superproject's local base branch | main checkout, on the base branch, clean | safe form 1 |
| Move a submodule's local integration branch | that submodule's own checkout, on that branch | safe form 1, as `git -C <submodule-path> pull --ff-only` |
| Only read where a branch now is | any worktree | safe form 2 |
| Anything at all, using a `<src>:<dst>` refspec | anywhere | not available — see above |

**The superproject's own base-branch fast-forward obeys the identical rule.** It
is one of the legal main-checkout writes at a round boundary, and it runs as
`git -C <main-checkout> pull --ff-only` while the main checkout is on the base
branch. Never as `git fetch origin main:main` from the orchestrator's or a
worker's worktree.

---

## 5. The per-round procedure

0. Skip entirely if `--submodules=off`, or if detection (§1) was empty.
1. Build the touched set from this round's merge evidence (§2).
2. Resolve each touched submodule's integration branch (§3), using the cached
   answer where one exists.
3. For each touched submodule, fetch and fast-forward its integration branch
   using a safe form from §4 — `git -C <submodule-path> pull --ff-only` when that
   checkout is on the branch, otherwise fetch and read `origin/<branch>` without
   moving the local ref. A failure here is reported and left to the next round
   (§7).
   **This step is a prerequisite of the bump, not a convenience.** The bump
   records the submodule commit that is checked out in the superproject's working
   tree; if that checkout is stale, the pointer recorded is stale.
4. Fast-forward the superproject's own base branch in the main checkout, by the
   same rule.
5. Bump the pointers that actually moved (§6).
6. One commit for the round.

---

## 6. Pointer bump

**Bump only pointers that actually moved.** Prefer the guarded command:

```
pipeline submodule bump --project-root <root> \
                        --submodules <path-a,path-b> \
                        --base <superproject-base-branch> \
                        --no-admin \
                        --json
```

| Argument | Note |
|---|---|
| `--project-root` | The superproject root. Required. |
| `--submodules` | Comma-separated paths — **the ones that moved this round**. Omit it and the command auto-detects every drifted pointer, sweeping in drift that predates the run. Pass it explicitly. |
| `--base` | The **superproject's** base branch (default `main`). This is *not* the submodule's integration branch: it is the branch the pointer commit lands on. It is the one branch in this procedure that does not vary per submodule. |
| `--source-worktree` | Optional: where the merged submodule state lives, when that is not the superproject's own checkout. |
| `--dry-run` | Stage the change, capture the diff, then stop before push/PR/merge. Mutates nothing on the base branch. |
| `--no-admin` | **Passed on every invocation, always.** A bare flag that turns off the command's `--admin` merge retry, so a merge GitHub refuses is reported instead of bypassed. See *Elevation is suppressed, not surfaced* below. |

Output is one JSON object with `status` (`committed` · `noop` · `dry-run` ·
`halted`), `bumped[]`, `skipped[]` (each with a `reason`), `pr`,
`merge_outcome` (`"plain"` · `"admin"` · `"refused"` · `null`),
`merged_via_admin`, and `halt_reason`. Exit **0** for committed/noop/dry-run,
**1** halted, **2** usage or environment error.

`skipped[]` is worth reading rather than discarding. Its reasons are guards, not
noise — a pointer the run did not actually move (landing the run's value would
revert the base), a base that advanced the same pointer concurrently, an
unreachable or diverged submodule commit, a dirty or uninitialized submodule
checkout. Each is a deliberate refusal to clobber something.

### How it lands, and why it strengthens the main-checkout invariant

The command does its branch and commit work in **its own throwaway worktree**
taken off `origin/<base>`, opens a pull request, and **squash-merges** it. The
shared checkout only ever sees `fetch` + `merge --ff-only` afterwards.

**It does not write the main checkout's index and never commits from it.** The
pointer bump is nominally one of the writes the main-checkout invariant permits
at a round boundary; routing it through this command makes the actual write
smaller than the invariant allows — a fast-forward onto an already-merged commit.
That strengthens the invariant rather than straining it.

Two consequences follow from landing through a PR:

- It needs `gh` present and authenticated; without it the command exits **2**
  with an environment error and no bump happens.
- Branch protection and required checks apply to the bump exactly as they apply
  to a task PR.

### Elevation is suppressed, not surfaced

**`--no-admin` is on every invocation of this command.** Without it, the land
step retries a refused `gh pr merge` once with `--admin` — GitHub's administrator
bypass — and the landing PR merges *despite* the rule that refused it. The CLI's
default is still that fallback, so omitting the flag is not neutral: it opts in
to the bypass. The orchestrator never merges with elevation, and that promise is
only real when the flag is actually on the command line.

With the flag passed, the plain merge is attempted once and a refusal is
terminal and reported — `status: "halted"`, `merge_outcome: "refused"`,
`halt_reason` naming the PR, GitHub's own text in `stderr`, exit **1** — and
`gh` is never invoked with `--admin` at all. Nothing is lost: the commit is on
`origin` and the PR is open, so the bump lands by satisfying whatever gate
refused it, exactly like a task PR. Handle it as §7's halt row says — report,
leave the pointers unbumped, let the next round retry. Never re-run it without
the flag.

Consequently `merged_via_admin: true` (equivalently `merge_outcome: "admin"`) is
**unreachable when the flag was passed**. A bump that reports it is evidence the
invocation omitted `--no-admin` — a defect in the invocation, to be fixed, with
the elevation that already happened reported as a finding against the run. It is
not a routine round-report line.

A `--dry-run` is the cheapest confirmation that the flag reached the command:
its `planned_actions` name the merge that would be attempted, and that line
reads `(with --admin fallback)` only while the fallback is still live.

### Without the CLI

The bump can be done by hand, but the constraints do not relax: orchestrator
only, at a round boundary, in the main checkout, and only for pointers that
moved.

```
git -C <root>/<submodule-path> pull --ff-only     # §4 safe form 1
git -C <root> add -- <submodule-path>
git -C <root> commit -m "chore(submodules): bump <paths>"
git -C <root> push origin HEAD:<superproject-base-branch>
```

A rejected push is handled exactly as in §7: reported, not forced.

---

## 7. Failure paths

Every response below is defined and non-forcing. Nothing in this procedure ever
uses `--force`, `--force-with-lease`, `reset --hard`, or a non-fast-forward
merge.

| Failure | Response |
|---|---|
| Base-branch fast-forward fails — not a fast-forward, dirty checkout, network | Report the submodule and the reason. **Do not force.** Continue the round; the next round retries. |
| `refusing to fetch into branch … checked out at …` | Not a failure to retry — the refspec form was used. Switch to a safe form (§4). |
| Superproject base-branch fast-forward fails | Same as above: reported, retried next round, never forced. Pointers are not bumped onto a base you could not fast-forward. |
| Pointer bump halted (`status: halted`, exit 1) | Report `halt_reason` verbatim. **Leave the pointers unbumped.** Do not force-push. The next round retries. |
| Parent push rejected — non-fast-forward, protected branch, failing required check | Report it. Leave the pointers unbumped. No force-push, and no elevation flag added by the orchestrator. |
| `gh` absent or unauthenticated | The bump exits 2 on environment. Report once that pointers are unbumped for this run and continue; this is the same degradation the run already announces for the PR path. |
| Bump reports `merge_outcome: "refused"` (with `status: halted`) | GitHub refused the landing PR's merge and `--no-admin` kept it from being forced — the flag working, not an error to route around. Report the PR and GitHub's text from `stderr`; land it by satisfying the gate. **Never re-run without `--no-admin`.** |
| Bump reports `merged_via_admin: true` (`merge_outcome: "admin"`) | **`--no-admin` was not passed on that invocation.** Branch protection was bypassed on the orchestrator's behalf. Fix the invocation, and report the elevation as a finding against the run — not as a routine note. |
| Entries in `skipped[]` | Report path and reason. Do not re-run with `--submodules` widened to force them through — the skip is the guard doing its job. |
| A pointer is drifted that no task this round touched | Pre-existing drift, out of scope for the round's bump — which is why `--submodules` is passed explicitly. Report it; do not fold it in silently. |
| An uninitialized (`-`) submodule appears in the touched set | Contradiction: it has no checkout and cannot have received a merge. Report it and skip; do not initialize it as part of the sync. |
| The CLI disappears mid-run | Fall back to the manual bump in §6, or skip the bump and report it. Never force. |

A failed sync never fails the round's tasks. Their verification stands; only the
pointer lags, and the lag is visible and retried.

---

## 8. Ordering and concurrency

**The sync is serialized in the orchestrator.** Exactly one sync at a time. It is
never delegated to a worker and never overlaps itself.

**It is safe while workers still hold worktrees of the same submodules**, for two
reasons:

1. What it records is the **superproject's** pointer, not any worker's tree. No
   worker's working directory is touched.
2. Every branch write it performs obeys §4, so it never attempts to move a ref
   that a worker's worktree has checked out. A worker sitting on its own
   `worktree-<task-id>` branch inside a submodule is unaffected when that
   submodule's integration branch fast-forwards.

**Codex-specific — "workers never run this" is a rule, not a mechanism.** On this
host every agent shares one working directory and one set of permissions, so
nothing refuses a worker that runs `git submodule update` or a `git worktree`
command in the superproject; a Claude Code worker attempting the same is blocked
by its host. The two guarantees above therefore hold **only for as long as the
orchestrator is the sole party running this procedure.** Keep it out of briefs
entirely — a worker cannot be tempted by a step it was never shown — and if a
worker reports having run one of these commands, treat the round's pointer state
as unverified and re-derive it rather than assuming §5 still describes the tree.

Position in the round is fixed: after the round's verification and board commit,
before the next ready-set computation. That position is what makes "one commit
per round" true rather than aspirational.

Leaked-worktree collection is **not** part of the sync. `pipeline gc` scans
initialized submodules by default and reports per-submodule leaked branches and
stale worktree records; run it at run completion, not per round.

---

## 9. Commands this runbook names

| Command | Provided by |
|---|---|
| `git submodule status`, `git fetch`, `git pull --ff-only`, `git merge --ff-only`, `git config -f .gitmodules`, `git symbolic-ref`, `git rev-parse`, `git add` / `commit` / `push` | git |
| `gh pr view --json baseRefName` | GitHub CLI |
| `pipeline submodule bump --project-root … [--submodules …] [--base …] [--source-worktree …] [--dry-run] [--json]` | `@baizor/pipeline` |
| `pipeline gc` | `@baizor/pipeline` |

Per-submodule worktree *provisioning* is deliberately absent here; it belongs to
the parallel-execution reference module, not to the sync.
