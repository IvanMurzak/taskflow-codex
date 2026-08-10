# Taskflow for Codex

Taskflow is a four-stage lifecycle that a user or agent can invoke to turn a fuzzy change
into repository-evidenced architecture, adversarial verification, immutable task
specifications, and ROADMAP-driven execution.

```text
taskflow-frame → taskflow-review → taskflow-tasks → taskflow-execute
```

## Compatibility with 0.5.1

A bare `taskflow-execute <slug>` needs no new flags, no migration, and nothing to
configure. Every capability this version adds — parallel dispatch, code review,
execution tiers, submodule sync — is opt-in, and none of it activates unless you
type the flag for it. The default invocation, `--parallel=1 --review=off` in a
repository with no submodules, loads `skills/taskflow-execute/SKILL.md` and no
other file.

One default did change, deliberately. Dispatch is now explicitly serial
(`--parallel=1`): one task at a time. 0.5.1 had no `--parallel` flag at all — its
own prose said to "run only independent groups in parallel," and run for real that
meant a round could start more than one ready task at once. Pinning the new
default to `1` is strictly more conservative than that, but it is a genuine
behavior change rather than an identical rerun of 0.5.1's scheduling: a workflow
that relied on 0.5.1 starting several tasks in round one now sees one, and needs
`--parallel=N` (or `--parallel=auto`) to get that throughput back.

**On Codex that new default is also a correction, not only a caution.** 0.5.1
described each worker as "one isolated worktree worker" — and on this host no
worker ever had one. A Codex subagent gets no worktree of its own (measured; see
below), so 0.5.1's concurrent rounds placed several workers in a single working
tree with nothing separating them. Serial is the smallest honest default here.
Parallel dispatch is available again in this version, but only over a substrate
that actually supplies the isolation 0.5.1 assumed.

## Package

This self-contained Codex package has its manifest at `.codex-plugin/plugin.json`
and its four public skills in `skills/`. Any user or agent may invoke each stage;
no skill pins a model.

**Two agent roles ship in this repository that the manifest cannot install for
you.** `taskflow-execute` dispatches through `taskflow-implementer` and
`taskflow-reviewer`, defined at `.codex/agents/taskflow-implementer.toml` and
`.codex/agents/taskflow-reviewer.toml`. Codex discovers agent roles from the
*project's* own `.codex/agents/` directory, and a Codex plugin manifest accepts
`skills`, `apps` and `mcpServers` and nothing else — so there is no channel for
shipping a role. Copy both files into any project you intend to run Taskflow in;
it is a one-time action.

If they are absent the run still dispatches — with a generic agent type, the
worker rules inlined into each brief, and a line in the run report saying so. That
is a weaker arrangement rather than an impossible one: the rules are the same
text, but nothing then keeps a reviewer's definition structurally distinct from an
implementer's.

## `taskflow-execute` arguments

Every flag is optional and every default is the one shown below — this table is
kept in lockstep with `skills/taskflow-execute/SKILL.md` §3, which is the
authoritative source if the two ever disagree.

| Flag | Values | Default | Notes |
|---|---|---|---|
| `<slug>` (positional) | a taskflow folder under `.taskflow/` | the only folder there | ambiguity is resolved with you, never guessed |
| `--scope=` | `all` · `wave:N` · `group:B` · comma-separated id list | `all` | free-text scope after the slug is still accepted, unchanged from before |
| `--parallel=` | `1` · `N` · `auto` | `1` | `>1` (or `auto`) enables concurrent dispatch — and on this host requires the Pipeline CLI, see below |
| `--engine=` | `auto` · `toolkit` · `pipeline` | `auto` | picks the execution tier. **There is no `native` value here** — see "Execution tiers" |
| `--pipeline=` | a pipeline name | — | only valid together with `--engine=pipeline` |
| `--review=` | `off` · `low` · `medium` · `high` · `xhigh` | `off` | anything but `off` dispatches a reviewer subagent that is never the implementer |
| `--merge=` | `ask` · `on-green` · `never` | `ask` | applies outside the `pipeline` tier, which merges by its own run definition — see "Why `--merge` defaults to `ask`" |
| `--submodules=` | `auto` · `off` | `auto` | `auto` means "run the sync only when `git submodule status` is non-empty" |
| `--solo=` | comma-separated id list | empty | forces single-slot dispatch — the authoritative channel for a task that needs an exclusive resource |
| `--on-fail=` | `continue` · `stop` | `continue` | `stop` drains the in-flight slots and halts the run |
| `--dry-run` | flag | off | prints the resolved plan — flags, ready set, slot count, execution tier, withheld tasks — and dispatches nothing |

An unrecognized `--flag`, or a value outside a flag's listed vocabulary, stops the
run rather than silently falling back to a default: a mistyped `--paralel=4` never
quietly means `1`. Every resolved value, including the defaults nobody typed, is
printed before dispatch begins.

`--parallel=auto` requests 8. What you actually get is the smallest of that, the
number of ready groups, the fixed ceiling of 8, and **the host's own concurrency
slots minus the one the orchestrator occupies** — 4 slots by default on
`codex-cli 0.147.0`, so three concurrent workers. That last term has no
counterpart in the Claude plugin, where nothing exposes the host's cap; here Codex
states it to the orchestrator directly, and the orchestrator reads it rather than
computing it from configuration.

Two things are fixed and not configurable by any flag: the review fix-round budget
(`K = 2`) and the concurrency ceiling (`8`). Review gating is fixed by depth as
well — `low` and `medium` are advisory, `high` and `xhigh` block — and there is no
flag that changes which.

`--worktree-root`, `--seed` and `--base` are deliberately not part of this
surface; each is owned elsewhere, and being unrecognized they stop the run.

## Execution tiers — and the Pipeline CLI is required, not optional

`--engine` picks the substrate that provisions a task's working directory.
Default `auto`.

| Tier | Needs | Provides |
|---|---|---|
| `toolkit` *(the only parallel tier)* | The `pipeline` CLI at **0.17.0** or above — see "Why the minimum is 0.17.0". `--engine=auto` resolves here once the installed CLI is at or above that version | One CLI-provisioned slot per worker: a working directory outside the repository, a `worktree-<task-id>` branch cut from an arbitrary base, a resolved env file and a port block, plus per-submodule worktrees, `ci-wait`, `submodule bump` and `gc` |
| `pipeline` | Explicit `--engine=pipeline --pipeline=<name>` | Each task becomes one `pipeline drive` run, which owns implement → review → PR → CI → merge → sync itself. `--merge` does not apply here |

`--engine=auto` never selects `pipeline`: that tier hands merge authority to a
pipeline definition, which is an owner decision and has to be typed.

### There is no `native` tier on Codex, and that is a measurement

The Claude plugin has a third tier, `native`, which needs no CLI at all because
Claude Code cuts a worktree per worker itself and enforces the main-checkout
boundary. **Codex offers neither half**, and that was measured rather than
assumed. On `codex-cli 0.147.0`, two subagents spawned concurrently reported the
same `pwd`, `git rev-parse --show-toplevel`, `--git-dir` and `--git-common-dir` as
the root agent; `git worktree list` was unchanged while both were live; all four
files they wrote landed in one directory; and each agent thread's own session
rollout recorded the root's working directory. Codex's shipped prompt states it
outright — *"All agents share the same directory … edits made by one agent are
immediately visible to all other agents."* A `.codex/agents/*.toml` role changes
the persona, not the filesystem.

The full experiment, its caveats, and instructions for re-running it against a
newer Codex build are in `docs/2026-08-09-codex-subagent-isolation.md`.

Because the tier does not exist, `--engine=native` stops the run at parse time
with its own message rather than the generic unknown-value one — it is the value a
reader porting a Claude command line will type.

**The consequence is the inverse of the Claude plugin's.**

- **The Pipeline CLI is mandatory here, not an upgrade.** On Claude Code the CLI
  adds ports, submodule worktrees and an arbitrary base branch on top of a working
  `native` tier. On Codex there is no tier underneath `toolkit` to fall back to.
- **`--parallel > 1` requires `toolkit` or `pipeline`.** Two Codex subagents
  working the same repository without CLI-provisioned slots collide on the same
  files, the same index and the same `HEAD` — with no host mechanism preventing it
  and no error when it happens.
- **Without the CLI the run is sequential, not parallel-but-unsafe.**
  `--parallel` is forced to `1`, the run says so once naming the version it found
  and the minimum required, and every ready task still runs — one at a time.
- **Dispatch and isolation are separate concerns on this host.** Codex subagents
  are the correct dispatch primitive and remain so; what they do not supply is a
  working directory. Do not read the presence of subagents as evidence of
  isolation.

### "Codex is less isolated" is the wrong summary

Codex is not a weaker sandbox than Claude Code. It is a differently shaped one,
and at the **session edge it is tighter**: writes outside the session workspace
were refused on *both* the shell path and the `apply_patch` path, where Claude
Code's guard is git-aware rather than filesystem-aware and lets an ordinary shell
redirect through. What Codex lacks is a boundary **between workers** — and that is
the only boundary the `native` tier is defined by.

| | Claude Code | Codex 0.147.0 |
|---|---|---|
| Worktree per worker | Yes, host-created | **No** — one shared tree |
| Tool-path write outside the boundary | Blocked | Blocked |
| Shell-path write outside the boundary | **Not blocked** | Blocked |
| Boundary between two workers | Yes | **None** |

The two hosts fail in opposite directions and neither is strictly safer. That
asymmetry is the reason this plugin is not a mechanical copy of the Claude one,
and the reason the CLI is optional on one host and required on the other.

### Why the minimum is 0.17.0

`--engine=auto` reads `pipeline --version` and compares it **numerically** against
`0.17.0` — never by checking that the binary exists, and never by probing the
subcommand. At or above it, `auto` resolves to `toolkit`. Below it, absent, or
unparseable, the run states the reason once and continues sequentially. A CLI that
is present but older resolves the same way, because a presence check would resolve
it to `toolkit` and then fail on first use — a silent misdetection instead of an
announced degradation.

**0.17.0 is the first published release whose `pipeline worktree list --json`
reports a hook-provisioned slot's `submodule_slots[].dir`.** That property is what
this plugin depends on, and it is *not* the same as "the first release shipping
`pipeline worktree`" — that derivation yields 0.16.0, and 0.16.0 is unsafe. On
released 0.16.0 the array is empty for every hook-provisioned slot, so a resumed
run enumerates the repositories a slot spans from an empty list and concludes that
a submodule slot holding uncommitted work is an empty shell. That verdict
destroyed 21,880 bytes of finished implementation in this design's own proving
run.

**Refusing 0.16.0 costs more here than it does on the Claude side.** There the
fallback is `native`, which never consults `submodule_slots` at all and still
dispatches in parallel. Here the fallback is sequential execution. That is still
the right answer — a run that reaps live work is worse than a run that is slow —
but it is a larger bill, and it is why the CLI's minimum version matters more on
Codex than it does on Claude Code.

### What a sequential run withholds

Without the CLI, three kinds of task cannot run, and only these three:

- a task that needs a bound **port** — nothing hands out a free port block;
- a task whose `repo:` is a **submodule** — the session checkout's submodules are
  the shared ones, and a worker committing in them writes the checkout every other
  agent is using;
- a task that must integrate on a **base branch other than the repository
  default** — there is nowhere to cut a slot from another branch. (Both plugin
  repositories in this workspace are exactly this case: they are gated, and every
  PR targets `next`, not `main`.)

A withheld task's row stays pending, not failed. The reason is reported once per
run — naming the state, the gap and the affected task ids — and every other ready
task still runs. Installing `pipeline` at 0.17.0 or above and re-running is
normally all that unblocks them.

## Why `--merge` defaults to `ask`

`--merge=ask` holds each finished task at "verified, merge held" and waits for you
— nothing merges unattended. That is the default because an orchestrator that
merges pull requests by itself, by default, is a large blast radius for a plugin
anyone can install.

`--merge=on-green` (merge once CI is green, no blocking review finding is open,
and the row is behind no approval gate) and `--merge=never` (stop at "verified,
merge held" permanently, and never ask) both exist for when you want something
else — but they are opt-in, and neither bypasses branch protection nor elevates
under any circumstance. `--merge` governs the `toolkit` tier and the sequential
fallback; the `pipeline` tier merges by its own run definition instead.

## Workflow contract

- New artifacts live only in `.taskflow/YYYY-MM-DD-<slug>/`. Prefix every new
  Taskflow folder with its local creation date; do not rename existing folders.
- `ROADMAP.md` is the sole mutable task-state record. Task specs are immutable
  and never contain `status`.
- Task groups run sequentially by `sequence`; independent groups may run in
  parallel when their `needs` dependencies allow it, `--parallel` is raised above
  its default, and an execution tier is available to place the workers.
- `security_critical` and `production_touching` raise the model-routing tier —
  which is a different thing from the execution tier above, and the two never
  interact.
- Production, money, secrets, irreversible effects, and product decisions
  require an explicit owner gate.

Legacy `.claude/design/` and `.claude/taskflow/` folders are archives and are
not read or migrated.

## License

MIT
