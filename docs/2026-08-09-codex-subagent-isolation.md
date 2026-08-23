# Codex subagent isolation — experimental finding

**Date:** 2026-08-09
**Question:** Does a Codex subagent receive its own git worktree?
**Answer:** **No.** All agents in a Codex session share one working directory.
**Consequence:** **The `native` tier does not exist on Codex.** The Pipeline CLI
substrate is *mandatory* on Codex for any parallel work on the same repository.

This note records an experiment, not a reading of documentation. Every claim below
is tagged **OBSERVED** or **INFERRED**. Codex's subagent working-directory behaviour
is not part of any published stability contract, so this finding is pinned to the
build it was measured on and must be re-measured before it is relied on again.

---

## 1. Build under test

**OBSERVED**

| Item | Value |
|---|---|
| Codex CLI | `codex-cli 0.147.0` (`codex --version`) |
| Platform | `windows-x86_64`, Windows 11 Professional 10.0.26200 |
| Install | npm, `@openai/codex` → `codex-win32-x64` vendored binary |
| Auth | ChatGPT (`codex login status` → `Logged in using ChatGPT`) |
| Model | `gpt-5.6-terra` (session `turn_context`) |
| Invocation | `codex exec --sandbox workspace-write --json` |
| Approval policy | `never` (the `exec` default) |
| Subagent feature | `multi_agent` = `stable` / `true`; `multi_agent_v2` = `stable` / `false` (`codex features list`) |
| Concurrency overrides | none — `~/.codex/config.toml` contains no `[agents]` table and no `multi_agent*` key |

**Not tested:** Linux, macOS, WSL, `codex` TUI (only `codex exec`), sandbox modes
other than `workspace-write`, `--add-dir`, and nesting deeper than depth 1.

---

## 2. Experiment

A throwaway repository was built with a primary checkout, one linked worktree, and a
non-repo sibling directory:

```
C:/tmp/codex-g1-lab/main      # primary checkout        (must stay untouched)
C:/tmp/codex-g1-lab/wt1       # linked worktree         (the Codex session workspace)
C:/tmp/codex-g1-lab/outside   # not a git repo at all   (must stay untouched)
```

A single `codex exec` session was started with `-C .../wt1`. It was told to spawn
**two subagents concurrently** — both spawned before either was waited on — and to
have each report, from its own process:

- `pwd`, `git rev-parse --show-toplevel`, `--git-dir`, `--git-common-dir`, `git worktree list`
- a **shell-path** write inside the workspace, into the primary checkout, and outside the repo
- a **tool-path** (`apply_patch`) write to the same three targets

The shell and tool paths were probed separately because on Claude Code they behave
differently (see §6).

Both subagents were dispatched for real. The host recorded them as
`/root/probe_a` (thread `019fe63a-…`) and `/root/probe_b` (thread `019fe63b-…`),
both with `parent_thread_id` = the root thread, `depth: 1`.

---

## 3. What was observed

### 3.1 No worktree is created for a subagent

**OBSERVED.** Both subagents reported an identical working directory, identical to
the root agent's:

```
pwd                          C:\tmp\codex-g1-lab\wt1
git rev-parse --show-toplevel  C:/tmp/codex-g1-lab/wt1
git rev-parse --git-dir        C:/tmp/codex-g1-lab/main/.git/worktrees/wt1
git rev-parse --git-common-dir C:/tmp/codex-g1-lab/main/.git
```

`git worktree list`, run from inside both subagents *while both were live*, returned
exactly the two worktrees that existed before the session started:

```
C:/tmp/codex-g1-lab/main f90b47f [master]
C:/tmp/codex-g1-lab/wt1  f90b47f [wt1]
```

No third worktree. The host created nothing.

This is corroborated independently of anything the model said. Codex writes a session
rollout per agent thread, and each one carries its own `cwd` in its `session_meta`:

| thread | `agent_path` | `cwd` |
|---|---|---|
| `019fe638-…` | *(root)* | `C:\tmp\codex-g1-lab\wt1` |
| `019fe63a-…` | `/root/probe_a` | `C:\tmp\codex-g1-lab\wt1` |
| `019fe63b-…` | `/root/probe_b` | `C:\tmp\codex-g1-lab\wt1` |

### 3.2 The concurrent case is not different from the single case

**OBSERVED.** After the run, all four files written by the two concurrently live
subagents — two by shell redirect, two by `apply_patch` — were in **one** directory:

```
C:/tmp/codex-g1-lab/wt1/
  MAIN_MARKER.txt
  SHELLWRITE_probe_a.txt
  SHELLWRITE_probe_b.txt
  TOOLWRITE_probe_a.txt
  TOOLWRITE_probe_b.txt
```

Two agents, one tree, no separation on either write path.

### 3.3 The vendor states this itself, in the shipped prompt

**OBSERVED.** Codex's own model-visible prompt says so verbatim. This was extracted
with `codex debug prompt-input`, which renders the prompt **without calling a model**,
so it is a property of the binary, not a model utterance:

> All agents share the same directory. In detail:
> - All agents have access to the same container and filesystem as you.
> - All agents use the same current working directory.
> - As a result, edits made by one agent are immediately visible to all other agents.

The behaviour is therefore intentional on this build, not an artifact of how the
experiment was phrased.

### 3.4 There *is* a boundary — but it is per-session, not per-agent

**OBSERVED.** Writes outside the session workspace were refused on **both** paths, by
both subagents, at both targets.

Shell path — refused at the OS level:

```
shell_main_exit=False
  Access to the path 'C:\tmp\codex-g1-lab\main\POISON_SHELL_probe_a.txt' is denied.

shell_outside_exit=False
  Access to the path 'C:\tmp\codex-g1-lab\outside\POISON_SHELL_probe_a.txt' is denied.
```

Tool path — refused by Codex:

```
patch rejected: writing outside of the project; rejected by user approval settings
```

**OBSERVED.** After the run, `main/` still contained only `MAIN_MARKER.txt` and
`outside/` still contained only `OUTSIDE_MARKER.txt`. Nothing leaked.

This boundary is real and it is stronger than Claude's (§6). But it is the boundary of
the **`--sandbox workspace-write` session workspace**, which every agent in the session
shares. It separates the session from the rest of the disk. It does not separate agents
from each other, which is the only thing the `native` tier needs.

### 3.5 `.codex/agents/*.toml` is real, and does not change any of the above

**OBSERVED.** Project-scoped agent roles are discovered. A file missing a required key
produced this host error, naming the exact path:

```
Ignoring malformed agent role definition: agent role file at
C:\tmp\codex-g1-lab\wt1\.codex\agents\probe.toml must define `developer_instructions`
```

Required keys, as enforced by 0.147.0: **`name`**, **`description`**,
**`developer_instructions`**.

**OBSERVED.** With a valid `.codex/agents/probe.toml` present, the role appears as a
`spawn_agent` `agent_type`. The root agent reported its allowed values as:

```
`probe`, `default`, `explorer`, `worker`
```

A subagent spawned with `agent_type: "probe"` started successfully and was tagged
`agent_role: probe` in its session metadata — **and its `cwd` was still
`C:\tmp\codex-g1-lab\wt1`**, identical to the root's. A named role changes the
persona; it does not change the filesystem.

### 3.6 Concurrency default

**OBSERVED.** With no override anywhere, the shipped prompt on this build reads:

> There are 4 available concurrency slots, meaning that up to 4 agents can be active
> at once, including you.

So the default is **4 concurrent agents including the root — i.e. 3 concurrent
subagents** — on `codex-cli 0.147.0`.

**OBSERVED**, by varying the keys and re-rendering the prompt (no model calls):

| override | slots reported |
|---|---|
| *(none)* | 4 |
| `agents.max_concurrent_threads_per_session=1` | 2 |
| `agents.max_concurrent_threads_per_session=2` | 3 |
| `agents.max_concurrent_threads_per_session=6` | 7 |
| `agents.max_concurrent_threads_per_session=10` | 11 |
| `features.multi_agent_v2.max_concurrent_threads_per_session=2` | 2 |
| `agents…=10` **and** `features.multi_agent_v2…=20` | 20 |

**INFERRED** from that table: `agents.max_concurrent_threads_per_session` counts
*subagent* threads and the reported slot count is that value **+ 1** for the root, so
its unset default is **3**; and an explicit `features.multi_agent_v2.…` value
overrides the total outright rather than capping it. An earlier "the two keys are
combined with `min()`" hypothesis was tested and **falsified** by the last two rows —
which is the reason this paragraph is labelled inference and the table above is not.

**Correction for the taskflow docs:** `06-migration-rollout.md` §2 Phase 4.11 names
`agents.max_concurrent_threads_per_session` as the bound. That key exists and works,
but it is not the only one — `features.multi_agent_v2.max_concurrent_threads_per_session`
also moves the effective ceiling on this build, and the number the orchestrator is told
is not equal to either key. Anything that computes a parallelism budget should read the
slot count the orchestrator is actually given, not assume it equals the config key.

---

## 4. Verdict

**The `native` tier does not exist on Codex.**

The `native` tier is defined in `02-target-architecture.md` §3 as *"the host offers
worker isolation — per-worker worktree with an enforced main-checkout boundary."*
Codex 0.147.0 offers neither half:

| `native` requires | Codex 0.147.0 |
|---|---|
| A worktree per worker | **No.** All agents share the session's single working directory (§3.1, §3.2), by design (§3.3) |
| An enforced main-checkout boundary | **Not per worker.** The enforced boundary is the shared session workspace (§3.4). Between two workers there is no boundary at all |

Codex has genuine parallelism — real concurrent subagents, 3 of them by default — but
it is parallelism *inside one working tree*. Two Codex subagents editing the same
repository concurrently will collide on the same files, the same index, and the same
`HEAD`, with no host mechanism preventing it.

**Therefore, Codex must not run parallel workers in the shared checkout.** The
host supplies concurrency but not isolation. Taskflow now supplies isolation by
creating one native git worktree per task; the Pipeline CLI is optional
automation.

### What `g2` must carry

The Codex contract must preserve these conclusions:

1. `native` means scheduler-created git worktrees, never host-provided isolation.
2. `--parallel > 1` requires one worktree per task, not necessarily the Pipeline CLI.
3. `--engine=auto` may use a compatible CLI or native git worktrees, but never
   the shared checkout.
4. Codex subagents remain the correct **dispatch** primitive (§3.5 — `.codex/agents/*.toml`
   works, with `name` / `description` / `developer_instructions`). What they do not
   supply is *isolation*. Dispatch and isolation are separate concerns on Codex, and the
   contract should say so rather than let a reader infer isolation from the presence of
   subagents.

---

## 5. Observed vs inferred — summary

**Observed** (measured on 0.147.0; raw output in §3):
- Both concurrently-dispatched subagents shared the root's cwd, toplevel, git-dir and git-common-dir.
- No worktree was created; `git worktree list` was unchanged during and after the run.
- All four files written by both agents landed in one directory.
- Writes outside the session workspace were refused on both the shell path and the tool path.
- The shipped prompt states the shared-directory behaviour verbatim.
- Default concurrency: 4 slots including the root.
- `.codex/agents/*.toml` is discovered, requires `name` / `description` / `developer_instructions`, and surfaces as a `spawn_agent` `agent_type`; a role-typed subagent still shares the cwd.

**Inferred** (reasoning, not measurement):
- That the unset default of `agents.max_concurrent_threads_per_session` is `3` — derived from the +1 relationship in §3.6, not read from a default value.
- That the enforced boundary is the *sandbox workspace root* rather than the git repository — consistent with `outside/` (not a repo) being refused too, but `--add-dir` was not tested.
- That the same behaviour holds on Linux and macOS. **Not tested.** The shell-path denial observed here was a Windows ACL denial; whether the shell path is equally enforced on other platforms is unknown and should not be assumed.
- That this behaviour persists in later builds. It is undocumented, so it may change without notice.

---

## 6. Comparison with the Claude side

Measured on Claude Code in the same taskflow (finding **F-8**):

| | Claude Code (`isolation: worktree`) | Codex 0.147.0 (`spawn_agent`) |
|---|---|---|
| Worktree per worker | **Yes**, host-created | **No**, one shared tree |
| Isolation root | The *primary* checkout | The session workspace (shared by all agents) |
| Tool-path write outside (`Write`/`Edit` vs `apply_patch`) | Blocked | Blocked |
| Shell-path write outside (`printf x > …`) | **Not blocked** — the guard is git-aware, not filesystem-aware | **Blocked** — OS-level `Access … is denied` |
| Guard is between workers | Yes | **No** |

The two hosts fail in opposite directions, and neither is strictly safer:

- Claude isolates **workers from each other** but leaks on the **shell path** out of the
  worktree. Its guard understands git and not the filesystem.
- Codex holds the **filesystem** boundary on both paths — genuinely tighter than Claude
  at the session edge — but has **no boundary between workers at all**, which is exactly
  the boundary the `native` tier is defined by.

That asymmetry is the finding. It is why the CLI substrate is optional on one host and
mandatory on the other, and why the Codex contract cannot be a mechanical copy of the
Claude one.

---

## 7. Reproducing this

Re-run before trusting this note against a newer Codex build. Roughly ten minutes.

```bash
# 1. Lab: primary checkout + linked worktree + a non-repo sibling
mkdir -p /tmp/codex-lab/outside && : > /tmp/codex-lab/outside/OUTSIDE_MARKER.txt
git init -q /tmp/codex-lab/main
: > /tmp/codex-lab/main/MAIN_MARKER.txt
git -C /tmp/codex-lab/main add -A && git -C /tmp/codex-lab/main commit -qm base
git -C /tmp/codex-lab/main worktree add -q -b wt1 /tmp/codex-lab/wt1

# 2. Concurrency default and the shipped prompt — no model call, deterministic
cd /tmp/codex-lab/wt1
codex debug prompt-input "hi" | grep -o "There are [0-9]* available concurrency slots"
codex debug prompt-input "hi" | grep -o "All agents share the same directory[^\"]*"

# 3. The dispatch itself: spawn two subagents CONCURRENTLY (both before any wait) and
#    have each report pwd / --show-toplevel / --git-dir / --git-common-dir /
#    `git worktree list`, then attempt a shell write and an apply_patch write to
#    (a) its own cwd, (b) /tmp/codex-lab/main, (c) /tmp/codex-lab/outside.
codex exec -C /tmp/codex-lab/wt1 --sandbox workspace-write --json - < prompt.txt

# 4. Verify from the host, not from the model's summary:
git -C /tmp/codex-lab/wt1 worktree list     # unchanged => no per-agent worktree
ls /tmp/codex-lab/wt1                       # all agents' files in ONE directory
ls /tmp/codex-lab/main /tmp/codex-lab/outside   # unchanged => boundary held
```

The single most reliable check needs no model output at all: each agent thread writes
its own rollout under `$CODEX_HOME/sessions/YYYY/MM/DD/`, and the first line's
`session_meta` carries that thread's `cwd` and `agent_path`. If every subagent's `cwd`
equals the root's, there is no per-agent worktree — regardless of what any agent
reports.

---

## 8. Caveats

- One build (`0.147.0`), one platform (Windows), one sandbox mode (`workspace-write`),
  one depth (1). The behaviour is **undocumented** and can change without a version
  signal.
- The shared-directory behaviour is stated in Codex's own shipped prompt, which makes it
  deliberate on this build — but a shipped prompt is not a stability guarantee either.
- If a future Codex build does supply per-agent worktrees, the verdict in §4 must be
  re-derived from a fresh run of §7, not amended from this text.
