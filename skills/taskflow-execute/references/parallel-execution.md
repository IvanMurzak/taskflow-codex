# Parallel execution — tiers, slots, worker briefs, merge, cleanup

Reference module for `taskflow-execute` on **Codex**. It is loaded **only** when
`--parallel > 1`. A `--parallel=1` run never reads it, which is what keeps the
default invocation as cheap as it has always been.

Read this as the **orchestrator**. Everything below the dispatch line is here:
which execution tier is in force, how a worker gets a working directory, what a
worker is told, what the orchestrator is still allowed to write, when a pull
request may merge, what happens when any of it fails, and how the run is torn
down. Workers never read this file.

**What lives elsewhere, and is not repeated here.**

| Subject | Home |
|---|---|
| Arguments, defaults, the ready set, the concurrency formula, the conditional loading table, the board vocabulary, the `spawn_agent` batching mechanism | `SKILL.md` |
| Review depths, gating, the K = 2 fix loop, the reviewer-is-not-the-implementer rule | `references/code-review.md` |
| Submodule detection, the per-round sync, the fetch constraint, the pointer bump | `references/submodules.md` |
| The measurement that removed the `native` tier | `docs/2026-08-09-codex-subagent-isolation.md` |

Where this file must lean on one of those, it points at it rather than restating
it as a second source of truth. Two places are deliberate exceptions and are
marked as such: the merge section states the one command in the whole run that
can elevate (§9.4), and §8 states the base-branch fast-forward constraint in one
sentence so this file reads standalone.

**Section numbers match the Claude module's**, deliberately, so the two can be
diffed section by section. Where a section's content differs, it differs because
the host does — never because the numbering drifted.

---

## 1. The tiers, and how `--engine=auto` resolves

`--engine` picks the substrate. Default `auto`.

| Tier | Precondition | Provides |
|---|---|---|
| `toolkit` *(the only parallel tier)* | `pipeline` present **at or above the minimum version that reports a hook-provisioned slot's submodule directories** | One CLI-provisioned slot per worker: a working directory outside the repository, a `worktree-<task-id>` branch cut from an arbitrary base, a resolved env file, a port block, and per-submodule worktrees. Also `ci-wait`, `submodule bump` and `gc` |
| `pipeline` | explicit `--engine=pipeline --pipeline=<name>` | Each task becomes one `pipeline drive` run; the pipeline owns the whole implement → review → PR → CI → merge → sync lifecycle |

**There is no `native` tier here, and this is the section where that costs
something.** On Claude Code, `native` is the default substrate: the host cuts a
worktree per worker and enforces the boundary, and `toolkit` is an upgrade that
adds ports, submodule worktrees and an arbitrary base branch on top. On Codex the
host cuts nothing — measured on `codex-cli 0.147.0`, two concurrently spawned
subagents shared the root agent's working directory, git-dir and common-dir, and
no worktree was created for either. **So `toolkit` is not the upgrade here; it is
the floor.** Everything `native` would have supplied on the other host is
supplied by `pipeline worktree create` on this one, or it is not supplied at all.

### 1.1 The resolution rule for `auto`

```
pipeline --version        →  bare semver on one line, e.g. 0.17.0
```

- **At or above the minimum version that reports a hook-provisioned slot's
  submodule directories ⇒ `toolkit`.**
- **Below it, or `pipeline` absent, or the check failed ⇒ the sequential
  fallback (§2),** and the run states the reason once: *"pipeline X.Y.Z is below
  the minimum M.N.P that reports a hook-provisioned slot's submodule directories.
  Codex provides no per-worker isolation, so there is no parallel substrate
  underneath — running at `--parallel=1`; tasks needing a port, a submodule
  worktree, or a non-default base branch will be withheld."*

**Presence alone is explicitly insufficient, and this is not a stylistic
preference.** A CLI has been on PATH throughout this design that has no
`worktree` command at all (0.15.0). A presence check would resolve that install
to `toolkit` and then fail on first use — a silent misdetection that surfaces as
a broken dispatch instead of an announced degradation. The minimum-version
constant lives in `SKILL.md` §8.1; compare against it numerically, never by
testing whether a binary exists and never by probing a subcommand.

**`auto` never selects `pipeline`.** That tier hands the entire task lifecycle to
a pipeline definition, and such a pipeline merges by its own `merge-and-sync`
step rather than by `--merge`. Handing merge authority to a definition the run
did not choose is an owner decision, so it must be typed explicitly.

**`auto` never selects `native` either, because there is nothing to select.**
`--engine=native` is refused at parse time with its own message (`SKILL.md`
§3.1).

### 1.2 The tier is resolved once, and it can only degrade

Resolution happens before the first dispatch, and the resolved value is printed
with every other flag. If `pipeline` disappears mid-run — uninstalled, PATH
changed, a `worktree` call that starts failing on environment — **finish the
in-flight slots, then continue sequentially**, withholding the tasks that need
what is now gone. The run does not stop and does not upgrade back.

Note the asymmetry with the Claude module, which continues *in `native`* here and
keeps its parallelism. This one loses its parallelism, because losing the CLI on
this host means losing the only thing that separated the workers.

### 1.3 What `--merge` means per tier

`--merge` applies to `toolkit` and to the sequential fallback. In the `pipeline`
tier the run's own definition decides, §7 and §9 below are skipped entirely, and
the run report says so rather than implying `--merge` was honoured.

---

## 2. The sequential fallback — three gaps, and *withheld, not failed*

When there is no substrate (§1.1), `--parallel` is forced to `1` and the single
worker runs in the session's own checkout. That arrangement is sound because it
is serial — one worker, and an orchestrator that is waiting on it — and not
because anything is isolating it. Three kinds of task still cannot run:

| Gap | Why | Consequence for a task that needs it |
|---|---|---|
| **No port allocation** | Nothing hands out a free port block | A task whose verification binds a port is withheld, or deferred to a `toolkit` run |
| **No submodule worktrees** | The session checkout's submodules are the shared ones; a worker committing in them writes the checkout every other agent is using | A task whose `repo:` frontmatter names a submodule is withheld |
| **Base branch is the checkout's own only** | There is nowhere to cut a slot from another branch | A task whose repository integrates on another branch is withheld. **Both plugin repositories in this workspace are exactly that case:** they are gated and every PR targets `next` |

### 2.1 Withheld is not failed

This distinction is the whole point of the section. When a ready task needs one
of the three gaps:

1. **The row stays `⬜ pending`.** It is not `⛔`, not `🔒`, not skipped, not
   marked blocked. Nothing about the task is wrong.
2. **The reason is stated once per run, not once per task and not once per
   round.** One line naming the state, the gap, and the affected ids.
3. **Every other ready task still runs.** A withheld task consumes no slot and
   delays nothing else.
4. The completion report names the withheld ids and says what would unblock them
   — normally "install `pipeline` at or above the minimum version and re-run".

Announcing a degradation and continuing is the required behaviour; stopping the
run because one task in eight needs a port is not.

### 2.2 How the orchestrator knows a task needs one of the three

- **Submodule** — the task's `repo:` frontmatter names a path that appears in
  `git submodule status`.
- **Non-default base** — the task's declared base branch (its `base_branch`
  frontmatter, or the repository's known integration branch) is not the base the
  session checkout is on.
- **Port** — `--solo` naming the task is the **authoritative** channel. The scan
  of DoD text for a bound port is best-effort and can miss a task the owner did
  not name; a false negative here corrupts a run, which is why owners are
  expected to name known-exclusive tasks explicitly.

---

## 3. Slot provisioning, per tier

A **slot** is the triple a worker needs: a working directory, a branch, and a
resolved environment. **On this host the orchestrator provisions all three, for
every worker, every time.** There is no case in which a worker arrives
pre-placed.

### 3.1 `toolkit` — the CLI is the placement, not an addition to one

```
pipeline worktree create --name <task-id> --base <base> \
                         [--submodules <declared>] [--ports <n>] --json
```

Run it **from the project root** — the command uses the current directory as
`PIPELINE_WT_PROJECT_ROOT`, exactly as the pipeline run path does.

Call it for **every** dispatched task, not only for tasks needing a port, a
submodule or a non-default base. That last sentence is the inversion of the
Claude module, which provisions a CLI slot only for the gaps its `native` tier
cannot cover and warns *"it is not a reason to provision a CLI slot for every
dispatch — do not."* **Here it is exactly that reason.** Without a slot, a
dispatched Codex worker works in the session's shared checkout, alongside every
other worker in the round.

`--json` returns one object; the fields that matter to dispatch are:

| Field | Meaning |
|---|---|
| `status` | `created` · `reused` · `failed` — see §5 |
| `worktree_path` | absolute path to the provisioned **parent** directory. **This is the path brief item 2 names.** For a submodule task it is *not* where the work goes — see the next row |
| `branch` | the branch that was cut, `worktree-<name>` by contract |
| `env_file` | absolute path to the dotenv file — the input to §6 |
| **`submodule_slots`** | **one entry per declared submodule — `{path, name, dir, base, source, exists}` — and `dir` is the directory a submodule task's worker actually works in.** `[]` when none were declared: never `null`, never absent |
| `ports` / `port_base` / `ports_source` | the allocated block, its base, and which side allocated it (`builtin` or `hook`) |
| `provisioner` | `builtin` or `hook` — which side cut this slot |
| `reused` / `reused_evidence` | `true` plus `registry` or `git-worktree` when the slot already existed |
| `base_branch`, `submodules`, `hook_dir` | echoed back as resolved |
| `detail` | the failure reason when `status` is `failed` |

Exit **0** success · **1** the provisioning hook failed (soft-fail or hard-fail;
`detail` says which) · **2** usage, an invalid `--name`, or an invalid
`--outcome`.

**`submodule_slots` is in this table because a resume depends on it.**
`pipeline worktree list --json` reports the same field per slot, derived at list
time for slots the current process did not create — which is the only channel a
resumed run has (§11). Each entry's `source` says which channel named `dir`, so a
derived guess is never dressed up as a reported fact:

| `source` | where `dir` came from |
|---|---|
| `record` | the built-in provisioner reported it as it cut it, and the slot record kept it |
| `env-file` | the slot's env file publishes it — a **hook's** own answer, on the channel the frozen contract leaves for it |
| `derived` | neither channel named it, so this is the layout convention both provisioners follow (`<parent slot dir>--<submodule basename>`) — check `exists` |

A `derived` entry carries `base: ""` rather than a guessed branch; the key is
always present either way.

**The env file names the same directories, and named them first.** Beside
`WORKTREE_PATH` and the ports, it carries `SUBMODULE_COUNT` and, per submodule,
`SUBMODULE_<n>_PATH` · `SUBMODULE_<n>_NAME` · **`SUBMODULE_<n>_DIR`** ·
`SUBMODULE_<n>_BASE`, plus `SUBMODULE_DIR_<NAME>` / `SUBMODULE_BASE_<NAME>`
aliases. `SUBMODULE_<n>_DIR` is the submodule worktree — the value §7 item 5
inlines into a submodule task's brief.

**Which directory the worker actually enters:**

- **An ordinary task.** `worktree_path`. The worker enters it and stays there.
- **A submodule task.** The submodule's own CLI-provisioned worktree — branched
  from *that submodule's* integration branch, not from the superproject's pin —
  is where the work happens. Its directory and branch are inlined, and it is what
  brief item 2 names for that task.

**Two properties of the shipped command worth knowing before relying on it.**

1. **`create` runs the consumer's `worktree-create.*` hook where one exists**,
   resolved from `<project>/.pipeline/.hooks` (override with `--hook-dir <path>`).
   `--base` and `--submodules` reach that hook as `PIPELINE_WT_BASE_BRANCH` and
   `PIPELINE_WT_SUBMODULES`, and the hook is then what cuts the branch. **A
   project with no such hook is not a failed create:** the CLI's built-in
   provisioner cuts the slot itself — the worktree outside the repository, one
   worktree per `--submodules` entry from *that submodule's* own integration
   branch, a free port block, and the env file — and reports
   `provisioner: "builtin"`. `toolkit` is reachable in a hookless project, so a
   task is not withheld for lack of a hook.
2. **`--ports <n>` is allocated, not merely recorded.** `--json` returns the block
   in `ports` and `port_base` and names the allocator in `ports_source`. The
   allocation is resolved **per field**, so a hook that returns no ports still
   receives the provisioner's: a hook-provisioned slot reports
   `provisioner: "hook"` alongside `ports_source: "builtin"`. §6.1 owns that
   precedence and explains why it is per-field.

### 3.1.1 The slot must be inside the session's workspace, or the worker cannot write to it

**This has no Claude analogue and it will stop a round dead if it is missed.**

A CLI slot is provisioned **outside the repository** (§4). Codex's sandbox
enforces the session's workspace roots on both the shell path and the
`apply_patch` path — measured: an attempted write to a directory outside the
workspace was refused with an OS-level *"Access to the path … is denied"* and
with *"patch rejected: writing outside of the project"* respectively. A slot the
session cannot write to is a slot no worker can use, and the failure arrives as a
permission denial in the middle of a worker's first edit rather than at
provisioning time.

So, before the first dispatch of a `toolkit` run:

- **Confirm the slot root is a workspace root of this session.** On
  `codex exec` the flag is `--add-dir <DIR>` — *"Additional directories that
  should be writable alongside the primary workspace"*, present on
  `codex-cli 0.147.0`. It is a **session-start** setting: it cannot be added to a
  session already running.
- **If it is not, the run cannot dispatch into CLI slots.** Report that, name the
  slot root `pipeline worktree create` reported in `worktree_path`, and treat the
  round exactly as §2 treats a missing substrate: withhold, state the reason once,
  and do not route around it by leaving workers in the shared checkout.
- **Do not widen the sandbox to `danger-full-access` to make this go away.** That
  removes the one boundary this host does enforce, and it is not the boundary
  that was in the way.

The session-edge boundary is not an obstacle to work around; it is the only
mechanical protection the run has. What it does not do — and no configuration
makes it do — is separate two workers inside the same workspace from each other.

### 3.2 `pipeline` — the run provisions itself

The orchestrator launches one run per task:

```
pipeline drive --root <pipeline_root> --run-id <id> --start <step-name> \
               [--effort code-review=<depth>] --json
```

The run creates its own slot, and **§7 and §9 are skipped entirely** — no worker
brief, no orchestrator-side merge. Mint the run id with `pipeline id`; never
invent one. `--merge` does not apply (§1.3).

### 3.3 A slot is made by the substrate or it is not made at all

**Never reproduce `pipeline worktree create` with raw git.** Not
`git worktree add -b worktree-<task-id> <base>` in the superproject, not
`git -C <submodule> worktree add …`, not "just this once, because `create` is
failing and the round is waiting".

When a slot cannot be provisioned — the CLI is below the minimum version, the
tier degraded mid-run, `create` exits non-zero, the hook refuses — the correct
response is the one §2.1 defines: **withhold the task and say why.** A withheld
row stays `⬜ pending`, costs one stated line in the run report, and delays
nothing else.

**What a hand-rolled worktree costs, concretely.** This is why the rule is a
correctness rule and not a preference:

- **no slot record** — nothing under `.pipeline/.runtime/worktrees/` knows it
  exists;
- **no env file** — §6's inlining has nothing to read, and §7 item 4 cannot be
  satisfied;
- **no port allocation** — a task that needed a port still does not have one;
- **invisible to `pipeline worktree list`**, which answers *"no provisioned
  worktree slots"* while the directories are live on disk;
- **invisible to the registry side of `pipeline gc`** — and a worktree hand-rolled
  inside a *submodule* is invisible to the superproject's `git worktree list`
  too, so §12.1's audit does not see it either;
- and therefore **the run-completion `gc` report is false**: it says the ground is
  clear because it cannot see what is standing on it.

**Observed, not hypothetical.** In this design's proving run on the other host, a
resumed round believed the CLI path was broken and hand-rolled two worktrees with
`git -C <submodule> worktree add … -b … origin/main`. Branch and base were
correct, so nothing looked wrong from the outside; there were simply no slots.
`pipeline worktree list` reported none while both were live, no env file existed
for either, no ports were allocated, and the run's `gc` reported clean ground. A
CLI defect is a reason to withhold and report — never a licence to route around
the substrate, because the substrate is also the bookkeeping.

---

## 4. Slot naming

| Item | Form | Why |
|---|---|---|
| **Slot name** | the task id, **validated against `tasks/` first** | The id reaches a filesystem path, a branch name, and a user-authored hook's environment. Validating that the id names a real file under `tasks/` before it reaches any of those is the gate |
| **Branch** | the substrate's own — `worktree-<name>` | Not invented by this skill. It is the namespace `pipeline gc` already scans and reaps, and the namespace the preflight's `git branch --list worktree-*` already reports |
| **Location** | the substrate's own root, outside the repository | A worker's build artifacts never land in the project folder — and see §3.1.1, because outside the repository is also outside the default workspace |

**The skill invents no branch namespace of its own.** `worktree-<name>` is the
substrate's, and it is the only one this skill creates or looks for — in the
preflight, in reconciliation (§11), and in `gc`'s reaping (§12). Do not create
branches under any other prefix and do not look for them under one. The raw
`worktree-*` glob is still not exclusive to this run, for the two reasons
`SKILL.md` §12 gives — another session's task branches, and another *host's*
isolation branches in a repository worked on from both.

The CLI additionally enforces its own name rules, which a validated task id
already satisfies: it must match `[A-Za-z0-9][A-Za-z0-9._-]*`, be at most 64
characters, contain no `..`, not end in `.`, and not be a Windows reserved device
name. A refusal is exit 2 with the reason — treat it as a bug in the task id, not
as something to work around by rewriting the name.

---

## 5. Collision safety is not git's job

**Slot creation is idempotent per name by frozen contract.** A second `create`
for a name that already has a slot does **not** fail: it **reuses** the existing
slot and re-reports it, with `status: "reused"` and `reused_evidence` naming what
proved it (`registry` — the CLI's own slot record, or `git-worktree` — a git
registration that predated the hook call). Exit code **0**.

That is correct behaviour for a contract that has to be re-runnable. It also
means **git will not catch a duplicate dispatch for you.**

Therefore:

1. **Uniqueness is the orchestrator's in-flight table.** One live slot per task
   id, asserted by the orchestrator before it calls `create`, not discovered
   afterwards.
2. **A `create` that reports `reused` is a duplicate-dispatch error.** It means
   invariant "one live slot per task id" was already violated. Do not proceed
   with the worker. Do not treat the exit code 0 as success. Stop that dispatch
   and reconcile through §11.
3. **The git refusal to check one branch out twice is a backstop only** — a
   second line of defence that happens to exist, never the control being relied
   on. **On this host it is a weaker backstop than on the other**, because two
   workers do not need two checkouts to collide: they are already in one
   directory unless the orchestrator put them elsewhere (§3.1). Git's refusal
   protects against provisioning the same branch twice; nothing protects against
   two briefs naming the same directory. That is `SKILL.md` invariant 7, and the
   orchestrator is its only enforcement.
4. **`--force` is never passed.** `pipeline worktree` exposes no force flag on
   any of its four verbs, and `git worktree add --force` — which would override
   exactly the backstop in point 3 — is never used by the orchestrator or by a
   worker. If a slot cannot be created without forcing, that is information, not
   an obstacle.

---

## 6. Environment — precedence, and inlining rather than sourcing

### 6.1 Precedence, later wins

For any value visible to a worker:

1. **The substrate's defaults.**
2. **The built-in provisioner's values.**
3. **The consumer hook's values — resolved *per field*, not wholesale.**
4. **Values the orchestrator inlines into the brief** (task-specific).

**Point 3 is per-field on purpose, and getting it wrong makes ports unreachable.**
A hook that returns `ports`/`port_base` **empty or absent does not suppress the
provisioner's ports** — the provisioner fills those fields, and only a hook
returning *non-empty* ports overrides them. Hook-wins-wholesale would have made
port allocation unreachable in every repository that already has a create hook,
including this one, whose hook returns `{}` for both fields.

### 6.2 The env file's grammar is constrained, and not by accident

The env file is dotenv. Values must be **unquoted and free of spaces and shell
metacharacters**. The tolerance of the parser is not the constraint that matters:
the file has a second consumer that reads it with `set -a && source`, and that
consumer will happily execute what a lenient parser would merely tolerate.

### 6.3 Inlining, not sourcing

**The orchestrator reads the env file and inlines the values as text in the
brief.** It never tells a worker to source it.

- **Why not source:** sourcing is shell-specific. `set -a && source` is not a
  thing on PowerShell, and the worker's shell is not something the orchestrator
  chose or can rely on — on this host the session reports its own shell, and it
  is frequently `powershell`. An inlined value works everywhere.
- **Why only some keys:** the orchestrator inlines **only the keys the brief
  declares it needs** — the ports, the worktree path, the submodule directories.
  **Unknown keys are never echoed.**

**The privacy reason for that last rule, stated plainly.** The create hook is
**user-authored**, and the frozen contract does not forbid it writing a secret
into `env_file`. The file is *intended* to carry non-secret configuration; it is
not *guaranteed* to. An orchestrator that dumped the whole file into a brief
would put whatever a third party's hook chose to write there into an agent
transcript, a PR comment, and a run report. Declared keys only. Anything else a
worker genuinely needs is passed **by reference to the env file**, not by value.

### 6.4 Ports

Allocated per slot as a contiguous free block, probed from a deterministic base
derived from the slot name — so re-provisioning the same slot is stable, and a
port already in use on the machine is skipped rather than assumed free. The block
is written into the env file and inlined into the brief. **A worker never infers
a port and never picks a default one.**

---

## 7. The worker brief — the contract

Seven items. All seven are required; the brief is short, but it is not partial.

1. **The immutable specification** — Goal, Scope & seams, Definition of Done,
   taskflow refs. Verbatim, not summarised. The worker may not edit it.
2. **The slot directory the worker must enter, named as an absolute path**, and
   that it is the worker's only writable root. For an ordinary task that is
   `worktree_path`; for a submodule task it is that submodule's
   `submodule_slots[].dir`.

   > **This item is never optional on this host, and it never resolves to "the
   > host already placed you."** The Claude module has exactly that form for its
   > `native` tier — *no path is passed* — because there the host cut the
   > worktree and passing a path would cost an approval prompt. Neither half of
   > that is true here: nothing was cut, and a worker that receives no path stays
   > in the shared session checkout with every other worker in the round.
   > **A brief missing item 2 is not a terse brief — it is a broken one**, and on
   > this host it is broken silently.
3. **Branch and base branch.** The branch is `worktree-<task-id>`. The base is
   the repository's real integration branch — `next` for both plugin
   repositories in this workspace, not `main`. Never "the default"; name it.
4. **Resolved environment values, ports included — declared keys only** (§6.3).
5. **For a submodule task:** which submodule, which directory, and which
   integration branch. All three; two of the three is a worker guessing the
   third.
6. **The isolation boundary.** The slot is the only writable root; the project
   checkout and every sibling slot are read-only; the board is not the worker's
   to edit; `git worktree` and `git submodule` are never run outside the slot.
   **State these as rules the worker enforces on itself**, because on this host
   nothing else does: the sandbox permits every one of these writes, since the
   project checkout and the sibling slots are inside the same session workspace
   (§3.1.1). The Claude brief can say the host *enforces* the first two; this one
   cannot, and must not imply it.
7. **What to report:** outcome, evidence, PR reference — and that **the report is
   not proof of completion**. The orchestrator verifies every DoD item against
   the repository itself.

**Never included in a brief, under any flag:**

- **The board.** Not its contents, not its path, not a summary of it. A worker
  that can see the board is a worker that can be tempted to update it — and on
  this host it can also reach it on disk and write it.
- **Other tasks.** Not the wave, not the dependency graph, not what else is in
  flight. A task's spec is complete by construction; context about siblings only
  invites scope creep across a conflict boundary.
- **Permission to merge.** Merge authority is not delegated to a worker under any
  flag, in any tier. §9 is the orchestrator's, entirely.

### 7.1 The brief is the spawn's own instructions, and `fork_turns` must be `"none"`

Delivering the seven items is not enough if the host also delivers everything
else. A `spawn_agent` call with `fork_turns` omitted or set to `"all"` gives the
subagent **the spawning turn's full history** — which for this orchestrator
contains the board, the ready set, the dependency graph and every other task's
specification. That is all three of the never-included items, arriving through a
channel the brief does not control.

**Spawn every worker and every reviewer with `fork_turns: "none"`, and put the
whole brief in the spawn's instructions.** If a worker reports that it can see
the board or another task, treat that as a dispatch defect and fix the spawn, not
the worker.

The same setting is what makes the board's routing tier expressible: the host
refuses `model` and `reasoning_effort` overrides on a full-history fork and
accepts them only when `fork_turns` is `"none"` or a positive integer
(`SKILL.md` §6.1). The two requirements agree, which is convenient but not the
reason for either.

---

## 8. The main-checkout invariant (D6)

During `--parallel > 1`, **exactly three writes to the main checkout are legal**,
all performed by the orchestrator, all at round boundaries:

1. `.taskflow/<slug>/ROADMAP.md`;
2. a fast-forward of the base branch;
3. submodule pointer bumps.

Nothing else. No source edit, no test run that writes, no stash, no clean, no
`git checkout` of a worker's branch to "have a look".

### 8.1 On this host the boundary is requested, not enforced — and that inverts the Claude module

The Claude module's equivalent subsection lists what its host blocks in code:
tool writes into the main checkout, `git -C` redirects, `cd`-then-git, and the
same checks applied to every subagent. **None of that exists here.** What was
measured on `codex-cli 0.147.0` is a different boundary in a different place:

| Attempt, from any agent in the session | Result |
|---|---|
| `apply_patch` **outside** the session workspace | **blocked** — *"patch rejected: writing outside of the project"* |
| Shell write **outside** the session workspace | **blocked** — OS-level *"Access to the path … is denied"* |
| Any write into the **project checkout**, inside the workspace | **allowed** |
| Any write into a **sibling worker's slot**, inside the workspace | **allowed** |

Read the two allowed rows carefully. The enforced edge is the **session
workspace**, and every agent in the session — orchestrator, implementers,
reviewers — is inside it together. **The boundary this invariant needs is between
workers, and it does not exist.**

Two consequences, both practical:

- **The invariant is the only control.** On Claude Code the prose is a second
  control behind an enforced one; here it is the first and last. Write it into
  every brief (§7 item 6) and into the role definitions, and do not let a future
  editor delete either believing the other is doing the work — neither is.
- **Do not describe this host as "less isolated" and stop there.** At the session
  edge it is *stronger*: Claude Code's guard is git-aware rather than
  filesystem-aware, so an ordinary shell redirect out of a worker's worktree is
  permitted there and refused here. The hosts fail in opposite directions.

### 8.2 Orchestrator-side residue

**Preflight — the main tree must be clean.** With `--parallel > 1`, a dirty main
checkout **stops the run** before any dispatch. Report the dirty paths. **Do not
stash and do not clean** — the dirt may belong to another agent working in the
same shared checkout, which is exactly what was found in this workspace at
framing time. (`--dry-run` skips this gate deliberately.)

**Per-repo slots.** A task whose `repo:` is a submodule works in that submodule's
own worktree, on that submodule's integration branch. It does not work in the
superproject's worktree with a `cd` into a submodule directory.

**Postflight — after each round, the main-tree diff must contain only
`ROADMAP.md` and pointer bumps.** Anything else halts the whole run (§10).

**The orchestrator's own writes are the ones most likely to break this**, because
the orchestrator is the agent actually standing in the main checkout. On the
other host a worker attempting the same write is refused; here the only thing
separating an orchestrator's legal board commit from an illegal source edit is
that the orchestrator does not make the second one.

### 8.3 The postflight diff uses the merge base — three dots, not two

```
git -C <main-checkout> diff --name-only <base>...HEAD        # ✔ three dots
git -C <main-checkout> diff --name-only <base>..HEAD         # ✘ two dots
```

**Two-dot compares the two tips.** If the base branch advanced after the round
started — someone else merged, or an earlier round's own pointer bump landed —
every file that moved on the base since then shows up in the diff as though this
line of work had *reverted* it. That reads exactly like foreign changes in the
main tree, and the response to foreign changes in the main tree is **halting the
entire run**. A false isolation-leak alarm is therefore not a cosmetic bug; it is
an outage of the orchestrator.

**Three-dot compares against the merge base** (`git merge-base <base> HEAD`),
which is what "what did this line of work change" actually means.

This is not theoretical: it fired during round 1 of this taskflow's own execution
on the sibling host and produced exactly that false alarm.

The general rule: **any diff that answers "what did this branch/line of work
change" uses three dots against the base.** Only a diff between two recorded
points on the *same* line of history may use two dots.

### 8.4 Where the fast-forward runs

Stated in one sentence for standalone reading, and owned in full by
`references/submodules.md` §4: git refuses to move a branch that any worktree has
checked out, so the base-branch fast-forward runs as
`git -C <main-checkout> pull --ff-only` while the main checkout is on the base
branch — never as a `<src>:<dst>` refspec fetch from a worktree. When you only
need to *know* where a branch is, fetch and read `origin/<base>` without moving
the local ref.

### 8.5 The orchestrator's own working directory

The orchestrator runs where the session was started, and every agent it spawns
starts there too (§8.1). Two things follow that the Claude module has to spend a
long subsection on and this one does not:

- **There is no primary-versus-linked-checkout question.** No host places
  anything, so nothing is placed relative to a primary checkout, and the
  "isolation root is the primary checkout, not your cwd" trap has no analogue.
  The orchestrator may itself be running in a linked worktree; slots are cut by
  the CLI from wherever it is run, and that is the whole of it.
- **There is no leftover-registration remedy to be unable to reach**, because
  there are no host-created registrations to leave behind. The only worktrees in
  play are the CLI's, and `pipeline worktree destroy` / `pipeline gc` own them.

What *does* carry over is the gitignore point, in a different form: a CLI slot
lives outside the repository, so it never appears in the main tree's diff at all.
If a consumer project configures a slot root *inside* the repository, add it to
`.gitignore` before the first `--parallel > 1` run, or §8.2's postflight reads
every slot as a leaked isolation boundary and halts the run.

---

## 9. Merge

| `--merge` | Behaviour |
|---|---|
| `ask` *(default)* | Hold the row at `🟣`, present the PR and its CI state, and wait for the owner. Nothing merges unattended |
| `on-green` | Merge only when **all four** conditions in §9.2 hold |
| `never` | Stop at `🟣` permanently. This run does not merge, and does not ask |

`--merge` applies to `toolkit` and to the sequential fallback. The `pipeline`
tier merges by its own definition (§1.3).

Before the first branch push and the first PR **per remote**, obtain
authorization once for that remote, for that run. Outward actions are not covered
by having been told to execute a taskflow.

### 9.1 Required-check presence is read from the branch-protection API

**Read once per repository per run, from the branch-protection / rulesets API:**

```
gh api repos/<owner>/<name>/branches/<base>/protection
gh api repos/<owner>/<name>/rulesets
```

Cache the answer for the run. What you are determining is a single fact: **does
this repository's base branch require any status check to pass before merge?**

**Never infer it from a `gh pr checks` exit code.** That exit code **cannot
distinguish "no required checks are configured" from "checks failed"** — both are
non-zero, and treating the first as the second (or worse, the second as the
first) is how an auto-merge fires on a repository where "green" was never
defined.

**No required checks ⇒ "green" is undefined ⇒ fall back to `ask`, and say so.**
Print the fallback: *"`<owner>/<name>` has no required checks on `<base>`; green
is undefined there, so `--merge=on-green` falls back to `ask` for its rows."*
Silently merging because nothing could fail is precisely backwards.

Note that `pipeline ci-wait`'s own exit **4** — *no checks appeared within
`--grace`* — is a fact about **this PR at this moment**, not about the
repository's configuration. It is not a substitute for the API read either.

### 9.2 The four conditions for `on-green`

All four, every time:

1. **CI reached a terminal pass.**

   ```
   pipeline ci-wait --pr <n> --repo <path|owner/name> [--timeout <sec>] [--json]
   ```

   Exit **0** every check passed · **1** a check failed · **2** usage or `gh`
   missing · **3** timeout · **4** no checks appeared within `--grace`. Only exit
   0 is green. It fails fast by default, so the first failed check ends the wait
   rather than burning the timeout.
2. **The repository actually has required checks on the base branch** (§9.1).
3. **No blocking review finding is open.** Whether a finding blocks is decided by
   `references/code-review.md`, not here.
4. **The row is behind no approval gate.** `on-green` never applies to a gated
   row — a gate is an owner decision and a green check is not one.

### 9.3 `on-green` never elevates

- It **never bypasses branch protection**.
- It **never passes `--admin`**, and never any other bypass flag or rule-bypass
  API call, to `gh pr merge` or to anything else.
- A merge GitHub **refuses is reported, not retried with elevation.** Report the
  PR, the refusal, and the reason; leave the row at `🟣`. The refusal *is* the
  repository's answer.
- It never force-pushes, and it never deletes a branch that is not its own
  `worktree-*` slot.

### 9.4 The one place elevation can occur — `pipeline submodule bump`

There is exactly one command in a taskflow run that can elevate, and the
orchestrator is responsible for stopping it.

**`pipeline submodule bump` lands its pointer commit through its own pull
request, and by default its land step retries a refused merge with
`gh pr merge --admin`**, reporting `merged_via_admin: true` — equivalently
`merge_outcome: "admin"` — when it did. That is the command's default, not the
orchestrator's policy; but a run that invokes it unguarded has elevated,
whatever the policy says.

Therefore:

- **The orchestrator suppresses that elevation by passing `--no-admin`, on every
  `submodule bump` invocation.** It is a bare flag, no value. Every invocation —
  including a `--dry-run` rehearsal. Not conditional on whether the repository
  looks protected.
- **The flag is what makes §9.3 true of this command.** With it, the plain merge
  is attempted once, a refusal is reported and terminal — `status: "halted"`,
  `merge_outcome: "refused"`, `halt_reason` naming the PR, GitHub's own text in
  `stderr`, exit **1** — and `gh` is never invoked with `--admin` at all.
- **A refused bump is reported and retried, never routed around.** Nothing is
  lost: the commit is on `origin` and the PR is open, so the bump lands by
  satisfying the gate that refused it, exactly like a task PR. Leave the pointers
  unbumped and let the next round retry.
- **`merged_via_admin: true` in a bump report is a defect, not a note.** The flag
  makes that outcome unreachable, so seeing it means the invocation omitted
  `--no-admin`. Fix the invocation; report the elevation that already happened as
  a finding against the run.
- The bump procedure itself belongs to `references/submodules.md` §6 and is not
  repeated here.

This is the only command that has to be told not to elevate. Task PRs never
elevate, under any flag, in any tier.

---

## 10. Failure paths

Every response is defined, announced, and non-forcing. Exactly one halts the run.

| Failure | Response |
|---|---|
| **Dirty main checkout at preflight** | Stop before any dispatch. Report the dirty paths. No stash, no clean |
| **Slot creation fails** | The row stays pending. Reap the partial slot with `pipeline worktree destroy --name <task-id> --outcome completed` — `completed` reaps, and `halted` would *preserve*, which is wrong for a slot with nothing in it. **Do not retry blindly, and do not hand-roll the slot with raw git** (§3.3): withhold the task and say why |
| **The slot root is outside the session workspace** | The worker cannot write to its own slot (§3.1.1). Withhold the affected dispatches, name the slot root, and state that the session must be started with that root added. **Do not** widen the sandbox to `danger-full-access`, and **do not** fall back to dispatching into the shared checkout |
| **`create` reports `reused`** | Duplicate dispatch (§5). Do not proceed with the worker. Reconcile via §11 |
| **A spawn is refused for concurrency** | Treat the current in-flight count as this run's cap for the rest of the run. Do not retry the spawn. The refused task's row stays `⬜ pending` |
| **A worker reports it is in the session checkout rather than its slot** | A dispatch defect, not a worker defect: item 2 was missing, wrong, or the worker was spawned as a full-history fork that talked it out of the brief. **Stop that worker before it writes** — `interrupt_agent` — inspect the shared checkout for what it already wrote, and re-dispatch with a corrected brief. This is the failure the whole of §7 item 2 exists to prevent |
| **A worker reports it can see the board or another task** | The spawn inherited the orchestrator's history. Fix the spawn to `fork_turns: "none"` (§7.1). Treat any board edit found in the tree as a leak and restore it from the last board commit |
| **`gh` absent or unauthenticated** | There is no PR path. Workers push branches only, rows stop at `🟣`, and the run says so **once** — not per task |
| **Base-branch fast-forward fails** | Do not force. Report and continue the round; the next round retries |
| **Pointer bump or parent push rejected** | Report. Leave pointers unbumped. No force-push, no elevation flag added by the orchestrator |
| **Port allocation exhausted** | Withhold the task exactly as in §2.1, and state the range that was tried |
| **Reviewer subagent fails** | Treat as a blocking finding for that round. A second failure escalates the row to `⛔` rather than merging unreviewed |
| **Reviewer role missing or not discoverable** | **Do not substitute a generic agent type for it.** A `default` spawn carries neither the never-review-your-own-diff rule nor the never-implement rule, and once posted to the PR its output is indistinguishable from a contract review. Either inline `taskflow-reviewer`'s rules into the reviewer's own brief and say in the report that the role file was absent, or hold the row unreviewed and report why. **A failed review round is the better outcome than a review that silently dropped both guarantees.** The substitution was made once on the sibling host, and the result was posted to a real PR |
| **Worker fails or times out** | `⛔` with the reason. **The slot is preserved** and its path recorded. `--on-fail=continue` keeps the other slots running; `--on-fail=stop` drains the in-flight slots and halts |
| **Review still blocking after K rounds** | `⛔`. Slot preserved. (K and the loop are `references/code-review.md`'s) |
| **CI red** | The row stays `🟣` with the failing check named. No merge |
| **Merge conflict** | `⛔`. The branch and the slot are preserved. **The orchestrator does not resolve conflicts on a task's behalf** |
| **Postflight finds foreign changes in the main tree** | **⚠ HALT THE WHOLE RUN.** Report the paths. Isolation has leaked, and every further dispatch compounds it. Check §8.3 first — a two-dot diff manufactures this alarm out of an advanced base branch |
| **`pipeline` disappears mid-run** | Finish the in-flight slots, then continue sequentially, withholding the tasks that need it (§1.2) |

**The halting row is the only one.** Everything else degrades, reports, and
continues — because a run that stops on the first imperfection finishes nothing,
and a run that continues past a leaked isolation boundary corrupts a shared
checkout.

### 10.1 What this table deliberately does not contain

The Claude module carries a long runbook for a host **isolation refusal** —
*"Refusing to use … as an isolation worktree"* — with a stale-versus-live lock
diagnosis, a `git worktree unlock` / `prune` remedy, and an observation table of
five runs recording which checkout shapes and dispatch batches were refused.
**None of it is mirrored here, and its absence is deliberate.**

That refusal is emitted by a host mechanism this host does not have: there is no
per-agent isolation worktree to refuse, no lock to leave behind, and no
`.claude/worktrees/` registration to reap. Mirroring the section would import an
observation set measured on another host as though it described this one — and
that section's own history is the argument against doing so: two confident
explanations of its trigger have been shipped there and **both were falsified by
the next run that relied on one**.

If a Codex-side failure of comparable shape is ever observed, record it the way
that table does — the arrangement, the batch it was part of, the verbatim
message, and any path the message names — and add it here **as a measurement**,
not as an analogy.

---

## 11. Interruption and resume

A dispatch round is not atomic, and a session can end mid-flight. On the next
invocation the preflight exposes the wreckage before anything is computed:

```
git worktree list                    # live slots
git branch --list worktree-*         # candidate dispatched branches
pipeline worktree list --json        # the registry, and the only reliable one
```

plus the board's own `🔵` rows.

**`worktree-*` yields candidates, not dispatches.** On this host the glob has one
producer — the CLI substrate — because Codex creates no isolation worktrees and
therefore no isolation branches (`SKILL.md` §12). It is still not exclusive to
this run: another session's task branches match it, and so do another host's
isolation branches in a repository worked on from both, which both plugin
repositories in this workspace are. **A dispatch is a row plus its slot**, so
judge every `worktree-*` branch by whether its suffix resolves to a task id
carrying a row on the board. One that does not is somebody else's — not
reconciliation evidence, and never an orphan of this run's to reap. §9.3's rule
("never deletes a branch that is not its own `worktree-*` slot") already covers
it, and §12 creates no exception to it.

**Reconcile all of it before any new dispatch.** Five cases:

| Evidence | Action |
|---|---|
| **1. A `🔵` row whose PR is merged** | Verify every DoD item against the repository, then record `✅` with the merged reference. The work is done; only the bookkeeping was interrupted |
| **2. A `🔵` row with an open PR** | **Adopt it.** Do not dispatch a second worker for that task — that is the duplicate dispatch §5 exists to prevent. Pick the row up at review or merge, wherever it actually is |
| **3. A `🔵` row with a branch but no PR** | **Run §12's reaping precondition before you form an opinion** — every repository the slot spans, branch commits *and* working-tree status, in that order. Where it finds work: resume the worker against the existing branch. Only where **every** repository the slot spans is both commitless and clean may the row reset to pending and the slot be reaped |
| **4. A live slot with no matching row** | A leak. `pipeline gc` reports it; `pipeline gc --clean` reaps it. A `⛔` row keeps its slot deliberately — that is not a leak, and reaping it destroys the post-mortem |
| **5. A `worktree-*` branch whose suffix matches no row** | **Not this run's.** Leave it — another session's task branch, or another host's isolation branch in a shared repository |

Reconciliation is the reason the in-flight table (§5) is rebuilt from repository
evidence at the start of every invocation rather than trusted from the board
alone. The board records what was *dispatched*; the tree records what *happened*.

**The glob is weaker evidence than the slot registry.** `pipeline worktree list`
names only the slots this run provisioned through `pipeline worktree create` — it
has no way to report a branch it did not cut. `git branch --list worktree-*` has
no such filter. Where the two disagree about whether a branch is this run's,
**the registry wins.**

**One resume hazard is specific to this host.** A session that ended mid-flight
took its subagents with it, and those subagents were writing into CLI slots that
survive them. There is no host registration to inspect and no lock to interpret —
which makes this simpler than the sibling host's equivalent — but it also means
the *only* evidence a worker was ever alive in a slot is what it left in the
slot. That is exactly why §12's precondition asks git about the branch **and**
the working tree, in every repository the slot spans, before anything is reaped.

---

## 12. Cleanup

**The reaping precondition — nothing below reaps on emptiness. Read this first.**

Every destructive step in this section reaps a directory *and a branch*: §12.2's
`destroy --outcome completed`, §12.4's `pipeline gc --clean`, and any "reset the
row and reap the slot" decision reached through §11. Each of them is preceded by
the same three checks, **in this order** — **the branch is checked, in every
repository the slot spans, before any directory is reaped.**

**And every one of them reaps only a branch this run's own board already
accounts for.** §11's row-derivation — a `worktree-*` branch whose suffix
resolves to a task id with a board row — is what proves a branch is this run's to
reap, not the raw glob by itself. `pipeline gc [--clean]` and
`--force-worktree-branches` (§12.4) act on whatever locally matches `worktree-*`;
a literal match is not, on its own, a licence to delete.

**1. A submodule task's work is not in the parent slot, and never was.** A task
whose `repo:` frontmatter names a submodule works in the **submodule** slot, on
that submodule's own integration branch (§8.2). The parent superproject slot is
empty, clean, and has uninitialized submodules **by design** — that is what a
correctly provisioned slot for such a task looks like. `worktree_path` is the
parent; **`submodule_slots[].dir` is where the work is** (§3.1). An empty parent
slot is the *expected* state and **proves nothing whatever** about whether the
task produced anything.

**2. Ask git before you judge a directory — in every repository the slot spans.**
Enumerate them first from `pipeline worktree list --json`: the parent
`worktree_path`, plus every `submodule_slots[].dir`. Then, in each:

```
git -C <dir> rev-parse --verify <base>                   # first: does <base> resolve HERE at all
git -C <dir> branch --list worktree-<task-id>            # [1] does the branch exist
git -C <dir> log --oneline <base>..worktree-<task-id>    # [2] does it carry commits
git -C <dir> status --porcelain                          # [3] is there uncommitted work
```

**All three, in every one of them.** `<base>` is that repository's own
integration branch, not the superproject's — a submodule slot is cut from the
submodule's branch, and asking the superproject's question of it returns a
confidently wrong answer. Any non-empty output, from any of the three, in any of
those repositories, means the slot holds work.

**Check [2] cannot run until its base resolves, and a check that errored is never
evidence of emptiness.** Measured in two proving runs, in the one repository this
precondition exists to protect: `pipeline worktree list --json` reports
`submodule_slots[].base` as a **bare branch name** — `next` — and a freshly
provisioned submodule slot has only `origin/next`. Run literally with that
string, `git -C <dir> log --oneline next..worktree-<task-id>` exits **128** and
prints *"fatal: ambiguous argument …"* **on stderr, with zero bytes on stdout** —
and zero bytes on stdout is exactly the input this section reads as *"no
commits"*. Re-asked as `origin/next..worktree-<task-id>` it exits **0** and
answers.

So: `rev-parse --verify <base>` first; if that fails, try `origin/<base>`, and
run check [2] against whichever spelling resolves. Read **each check's exit
status separately from its output** — never fold stderr into stdout with `2>&1`,
and never read only the final status of a chained three-command pipeline. **A
non-zero exit is not an answer**: a check that errored has said nothing about the
slot, so the slot holds work until the question is genuinely answered, and the
report names the check that could not be run.

**3. Only then judge what a directory contains** — and judge it at
`submodule_slots[].dir`, never at `worktree_path` alone.

**Why the third command is not optional.** A slot that needs reconciliation at
all is usually one whose worker was *killed*, and a killed worker's output is by
definition uncommitted. "The branch carries zero commits" is the expected answer
in that case and is **not** a finding of emptiness. Commits survive a removed
worktree; uncommitted work does not, and `--outcome completed` and `--clean`
delete the branch as well as the directory. There is nothing to recover from
afterwards.

**This ordering is the rule that was missing, and its absence is the most
expensive defect this design has recorded.** A resumed run inspected two
**parent** slots, ran its branch check in the **superproject** only, and
concluded — verbatim — *"Both abandoned branches carry zero commits and both
worktrees are clean — the killed workers produced nothing,"* and *"Both slots are
empty shells."* Every clause was true of the directory it looked at and false
about the work. The work was uncommitted, in the two **submodule** slots, on
same-named branches in different repositories. All four worktrees were reaped;
**21,880 bytes of finished implementation were destroyed**, and the run reported
that it had never existed.

### 12.1 The wave-boundary audit — every round, not only on interruption

Run §11's reconciliation — `git worktree list`, `git branch --list worktree-*`,
`pipeline worktree list --json`, the board's `🔵` rows — **after every round**,
not only when a session resumes from an interruption. Every `🔵` row has a live
slot or an open PR, every live slot has a `🔵` **or `⛔`** row, and a slot with no
row at all is a leak.

**This is the audit that caught the leaked-branch defect, and nothing else
would have.** A leaked local branch does not fail a task, does not fail CI, and
does not block a merge — it is invisible to every other check this runbook runs.
The same is true of a slot directory that survived its own removal behind a file
lock. Only a deliberate round-boundary comparison of slots against branches
against rows surfaces either one before it compounds.

**Add one Codex-specific check to the same audit: every live slot has at most one
live worker, and no two in-flight briefs named the same directory** (`SKILL.md`
invariant 7). `list_agents` is what the host offers for the first half; the
orchestrator's own in-flight table is the second half. Nothing on this host
detects a two-workers-one-directory collision after the fact — the tree simply
contains whatever the second writer left — so this check is the only point at
which it is catchable at all.

**`git worktree list` in the superproject does not show a submodule slot.** Take
those from `pipeline worktree list --json`'s `submodule_slots[].dir`, or the
audit reconciles only the half of each submodule task that never held the work.

The audit itself changes nothing — it is a read, not a `--clean`. Flag what it
finds in the round report.

### 12.2 Per task, on success

```
pipeline worktree finalize --name <task-id> [--json]      # where a terminal hook exists
pipeline worktree destroy  --name <task-id> --outcome completed [--json]
```

- **`destroy --outcome completed` reaps**: `PIPELINE_WT_DELETE_BRANCHES=1` — the
  worktree, every submodule worktree it provisioned, and the local
  `worktree-<task-id>` branch **in each of those repositories**, not only the
  slot directory — and the slot record is dropped.
- **`finalize` is strict must-succeed** — only an explicit `{"ok":true}` from the
  consumer's terminal hook passes, and a **missing** hook fails too. Call it only
  where the project defines one; a failure is reported and the slot preserved,
  never swallowed.
- **A removal that fails is not final.** The most common cause on Windows is a
  file lock held at the moment of removal — `destroy` reports the failure and the
  round continues, correctly; forcing it inline is not this subsection's job.
  Record the path and move on. `pipeline gc [--clean]` at run completion re-scans
  the same ground and reaps what it finds there through the same teardown, by
  which point a transient lock has usually cleared.

**Every slot on this host is a CLI slot, so `destroy` reaches all of them.** The
Claude module has to carry a caveat here that this one does not: there, a
`native`-tier worker's local branch survives the host's sweep and is reaped only
by run-completion `gc`. There is no host sweep here and no un-owned branch —
which is one of the few places the Codex arrangement is simpler rather than
weaker.

### 12.3 Per task, on failure — the slot is kept

**A failed task keeps its slot.** `⛔` rows, rows that exhausted the review fix
loop, rows with a merge conflict: the slot stays, and **its path is recorded on
the board row and in the report**. This is the whole point of preserving it —
somebody is going to look.

Where a slot must be explicitly preserved through the CLI, that is
`--outcome halted` (`PIPELINE_WT_DELETE_BRANCHES=0`, record kept). The one
inversion to remember is the failed *create* in §10: a slot with nothing in it is
reaped with `completed`, because there is nothing to preserve.

`pipeline worktree list [--json]` enumerates the slots this command group
provisioned and whether each is still on disk — use it to build the "what was
preserved and why" section of the report.

### 12.4 At run completion

When every scoped row is verified complete: update the taskflow README status and
the ROADMAP counter, remove any thin pointer created for this run, then

```
pipeline gc [--project <path>] [--json] [--no-submodules]
```

and **report what it found** — registered worktrees and their merged state, stale
unregistered directories, prunable worktree records, and orphaned `worktree-*`
branches, per initialized submodule as well as in the superproject. Reporting is
the deliverable; a `gc` whose output nobody reads has collected nothing.

- **`--clean`** prunes records, removes fully-merged worktrees, deletes stale
  directories and safe-deletes merged branches (`git branch -d`, never `-D`) —
  per submodule too. Run it — do not treat it as merely optional housekeeping —
  but never while a `⛔` row's slot is still wanted for inspection, and never
  before the reaping precondition at the head of this section has been satisfied
  for every row whose slot it would touch. `--clean` deletes branches, and this
  is the last point at which that is reversible.
- **A safe `-d` delete does not reap a squash-merged branch.** Git never sees the
  original commits as ancestors of a squash commit, so it reads as unmerged
  forever. If task PRs in a given repository squash-merge, plain `--clean` leaves
  those local branches behind; only **`--force-worktree-branches`** reaches them.
- **`--force-worktree-branches`** (requires `--clean`) additionally hard-deletes
  **unmerged** `worktree-*` branches. It destroys unmerged work by definition, so
  it is **never run unattended**: it requires an explicit owner decision. The
  owner making that decision needs to know it works from the same literal
  `worktree-*` match this section's precondition warns about — nothing in the
  flag distinguishes this run's own unmerged task branches from another session's
  or another host's. Confirm against the board (§11) before naming what it will
  touch, not after.

Finish by reporting verified results, withheld tasks and why (§2.1), preserved
slots and why (§12.3), any bump that reported `merged_via_admin: true` — as the
§9.4 defect it is, not as a routine line — and every outstanding gate.

---

## 13. Every command this runbook names

Each was verified against the CLI's own `--help` / usage output rather than
assumed. A command or flag that is not in this table does not belong in a brief
either.

| Command | Flags named here |
|---|---|
| `pipeline --version` | — (bare invocation; tier resolution, §1.1) |
| `pipeline id` | — (mints the UUIDv7 used as a run id in the `pipeline` tier) |
| `pipeline worktree create` | `--name` `--base` `--submodules` `--hook-dir` `--ports` `--json` |
| `pipeline worktree finalize` | `--name` `--base` `--submodules` `--hook-dir` `--json` |
| `pipeline worktree destroy` | `--name` `--outcome completed\|halted` `--hook-dir` `--json` |
| `pipeline worktree list` | `--json` |
| `pipeline ci-wait` | `--pr` `--repo` `--timeout` `--interval` `--grace` `--fail-fast` / `--no-fail-fast` `--json` `--verbose` |
| `pipeline gc` | `--project` `--clean` `--json` `--no-submodules` `--force-worktree-branches` |
| `pipeline drive` | `--root` `--run-id` `--start` `--effort <step_id>=<level>` `--json` |
| `pipeline submodule bump` | `--no-admin`, on every invocation (§9.4). The remaining flags are owned by `references/submodules.md` §6 |
| `git worktree list`, `git branch --list worktree-*`, `git rev-parse --verify <base>` — the base-resolution check that must precede `git log --oneline <base>..<branch>` (§12), `git status --porcelain`, `git diff --name-only <base>...HEAD`, `git merge-base`, `git submodule status`, `git -C <checkout> pull --ff-only` | git |
| `gh api repos/…/branches/…/protection`, `gh api repos/…/rulesets`, `gh pr merge` | GitHub CLI |
| `spawn_agent`, `wait_agent`, `followup_task`, `send_message`, `interrupt_agent`, `list_agents` | the Codex host — direct tool calls, never from inside a shell call (`SKILL.md` §10.2) |
| `codex exec --add-dir <DIR>` | the Codex host — a **session-start** setting, named here because §3.1.1 depends on it and because a run cannot apply it to itself |

**Named only to forbid them:** `--force` on slot creation (the CLI exposes none
on any `worktree` verb), `git worktree add` in **any** form as a substitute for
`pipeline worktree create` (§3.3), `gh pr merge --admin` or any other bypass
flag, and `--sandbox danger-full-access` as a way around §3.1.1. The
orchestrator runs none of these, and no brief asks a worker to. Likewise, no
branch namespace other than `worktree-*` appears in this system at all.
