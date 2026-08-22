# Taskflow Skills - Codex

[![Codex](https://img.shields.io/badge/Codex-plugin-10A37F?style=for-the-badge&labelColor=0D1117)](https://developers.openai.com/codex/)
[![Release](https://img.shields.io/github/v/release/IvanMurzak/taskflow-codex?style=for-the-badge&logo=github&logoColor=white&label=release&labelColor=0D1117&color=3FB950)](https://github.com/IvanMurzak/taskflow-codex/releases)
[![Skills](https://img.shields.io/badge/skills-4-A855F7?style=for-the-badge&labelColor=0D1117)](#the-four-skills)
[![License](https://img.shields.io/badge/license-MIT-6E7681?style=for-the-badge&labelColor=0D1117)](LICENSE)

![Taskflow — plan, review, tasks, execute](https://raw.githubusercontent.com/IvanMurzak/taskflow-codex/main/docs/taskflow-codex.svg)

**Tell it what you want in plain words. Get shipped pull requests.**

Taskflow reads your actual repository, writes the plan, argues with the plan,
breaks it into small tasks, and then runs those tasks — each in its own working
directory, each reviewed, each opening its own PR.

Four commands, in order. That is the whole thing.

## Install

```bash
codex plugin marketplace add IvanMurzak/pipeline-codex-marketplace
codex plugin add taskflow@pipeline
```

Restart Codex and the four skills are there.

If the marketplace was previously registered as `pipeline-codex`, replace that
legacy registration before installing:

```bash
codex plugin marketplace remove pipeline-codex
codex plugin marketplace add IvanMurzak/pipeline-codex-marketplace
codex plugin add taskflow@pipeline
```

> One marketplace carries both of my Codex plugins, and its id is `pipeline` —
> hence the `@pipeline` suffix. The plugin you just installed is `taskflow`;
> `pipeline` is the other one.

### Required for parallel execution on this host

```bash
bun add -g @baizor/pipeline    # the Pipeline CLI, 0.17.0 or above
```

Codex gives a subagent no working directory of its own — that is measured, not
assumed, and the experiment is [below](#there-is-no-native-tier-on-codex-and-that-is-a-measurement).
So the CLI is what supplies each concurrent worker a slot to work in. Without it
`--parallel` is forced to `1`; the run says so once, naming the version it found
and the minimum required, and every ready task still runs — one at a time.

<details>
<summary><b>Optional — the Pipeline plugin, which is a different thing</b></summary>

<br>

```bash
codex plugin add pipeline@pipeline
```

The plugin adds pipeline authoring — which is what
`--engine=pipeline --pipeline=<name>` then hands each task to. It is separate
from the CLI above and does not substitute for it: the CLI is what provisions a
worker's slot, and Taskflow resolves `pipeline` from `PATH`.

</details>

> **One extra copy, once per project.** `taskflow-execute` dispatches through two
> agent roles that a Codex plugin manifest has no channel for shipping. Copy
> `.codex/agents/taskflow-implementer.toml` and `.codex/agents/taskflow-reviewer.toml`
> from this repository into your project's own `.codex/agents/`. If they are
> missing the run still works — with a generic agent type, the worker rules
> inlined into each brief, and a line in the report saying so.

## How to use

![Four stages: plan, review, tasks, execute](docs/taskflow-steps.svg)

Pick a short name for your change. Every step uses that same name.

### 1. Plan it

Tell it the story the way you'd tell a colleague:

```text
/taskflow-plan device-pairing

People with two laptops sign in separately on each one and can't see which
machines are already signed in. I want pairing: approve a new device from
one you're already on, list the devices you have, and revoke any of them.
Revoking should end that device's session and nothing else.
```

It goes and reads your code —
every claim it writes down gets a `file:line` next to it — asks you the two or
three questions that actually change the outcome, and writes the plan to
`.taskflow/YYYY-MM-DD-device-pairing/`.

### 2. Review the plan

```text
/taskflow-review device-pairing
```

Three independent reviewers try to prove the plan wrong: against your code,
against the real specs and vendor docs, and against itself. Confirmed mistakes
get fixed on the spot. Anything that is your call comes back to you as a
question.

### 3. Turn it into tasks

```text
/taskflow-tasks device-pairing
```

The plan becomes numbered, immutable task specs — grouped so that two tasks in
the same wave can never touch the same files — plus a status board in
`ROADMAP.md`.

### 4. Execute

```text
/taskflow-execute device-pairing
```

> Best run in a **fresh context window**. It is a long job, and it does not need
> anything from the conversation you just had — everything it needs is on disk.

It works through the board: verified against the repository rather than against
what a worker claims, one PR per task, board updated after each one. Nothing
merges without you unless you ask for that.

Want it faster, and reviewed as it goes? This needs the
[Pipeline CLI](#execution-tiers--and-the-pipeline-cli-is-required-not-optional),
which is what gives each concurrent worker a working directory of its own:

```text
/taskflow-execute device-pairing --parallel=4 --review=high
```

## What lands on disk

```text
.taskflow/2026-08-10-device-pairing/
├── README.md                    the problem, and every decision you locked
├── ROADMAP.md                   the live status board — the only file that changes
├── 01-current-architecture.md   what your code does today, with file:line proof
├── 02-target-architecture.md    what it should do, and the D1..Dn decisions
├── 06-migration-rollout.md      phases, gates, rollback
├── 07-security.md               credentials, threats, controls
└── tasks/
    ├── a1-auth-token-store.md   immutable specs — written once, never edited
    └── b1-pairing-plane.md
```

`ROADMAP.md` is the only mutable record. Task specs never carry status, so a
half-finished run can never lie to you about where it got to.

---

## Documentation

- [The four skills](#the-four-skills)
- [`taskflow-execute` flags](#/taskflow-execute-flags)
- [Execution tiers — and the Pipeline CLI is required, not optional](#execution-tiers--and-the-pipeline-cli-is-required-not-optional)
- [There is no `native` tier on Codex, and that is a measurement](#there-is-no-native-tier-on-codex-and-that-is-a-measurement)
- [Why the minimum is 0.17.0](#why-the-minimum-is-0170)
- [Why `--merge` defaults to `ask`](#why---merge-defaults-to-ask)
- [Workflow contract](#workflow-contract)
- [What ships in this repository](#what-ships-in-this-repository)
- [License](#license)

## The four skills

| Skill | What it does | Writes |
|---|---|---|
| `taskflow-plan` | Explores every affected repository, asks the owner the decisions that change the outcome, and writes a self-contained architecture set. Every factual claim about existing code carries a `file:line` found in that session. | `.taskflow/YYYY-MM-DD-<slug>/` |
| `taskflow-review` | Runs three independent adversarial reviews — repository truth, external conformance, internal consistency — then applies the confirmed non-product corrections in one batch. Product questions come back to you. | corrections in place |
| `taskflow-tasks` | Decomposes the reviewed plan into immutable, PR-sized task specs with dependencies, conflict-safe groups, model routing tiers, and ROADMAP waves. | `<slug>/tasks/` + the board |
| `taskflow-execute` | Schedules. Computes what is ready, dispatches inside dependency and conflict limits, verifies against the repository rather than a worker's report, and is the sole writer of the board. | PRs + `ROADMAP.md` |

Any user or agent may invoke any stage. No skill pins a model.

### `taskflow-plan`

Give it the story and a short slug. It resolves `.taskflow/YYYY-MM-DD-<slug>/`,
reports the path, asks 2–4 owner questions that materially change the result, and
writes the document set — current architecture, target architecture, actor flows,
subsystem rules, infrastructure, migration, security, and user workflows — plus
the `ROADMAP.md` skeleton.

Two rules it will not bend: every statement about existing code needs evidence
found in that session, and product policy (deployment target, compatibility,
identity, UX, monetization, scope, anything irreversible) is yours to decide,
recorded as `D1..Dn`.

### `taskflow-review`

Reviewers try to **disprove** the plan, and a finding is only applied after it
has been verified against evidence — a plausible but false correction is worse
than no correction. Mechanical fixes are applied; anything touching product
policy is surfaced to you instead.

### `taskflow-tasks`

Runs only on a locked, reviewed plan with no open product question. Produces one
immutable file per PR-able task, a group table with the conflict rules, model
routing tiers (`security_critical` and `production_touching` route higher), and
the ROADMAP waves.

### `taskflow-execute`

Reads the board, reconciles every non-pending row against real repository
evidence — branches, commits, merged revisions, PRs, CI state — *before* it
dispatches anything, and only then starts work. It schedules; it does not
implement. Implementation happens in `taskflow-implementer` workers, review in
`taskflow-reviewer`, and a worker never reviews its own diff.

## `taskflow-execute` flags

Every flag is optional and every default is shown below. This table is kept in
lockstep with `skills/taskflow-execute/SKILL.md` §3, which wins if the two ever
disagree.

| Flag | Values | Default | Notes |
|---|---|---|---|
| `<slug>` (positional) | a taskflow folder under `.taskflow/` | the only folder there | ambiguity is resolved with you, never guessed |
| `--scope=` | `all` · `wave:N` · `group:B` · comma-separated id list | `all` | free-text scope after the slug is also accepted |
| `--parallel=` | `1` · `N` · `auto` | `1` | `>1` (or `auto`) enables concurrent dispatch — and on this host requires the Pipeline CLI, see below |
| `--engine=` | `auto` · `toolkit` · `pipeline` | `auto` | picks the execution tier. **There is no `native` value here** |
| `--pipeline=` | a pipeline name | — | only valid together with `--engine=pipeline` |
| `--review=` | `off` · `low` · `medium` · `high` · `xhigh` | `off` | anything but `off` dispatches a reviewer that is never the implementer |
| `--merge=` | `ask` · `on-green` · `never` | `ask` | applies outside the `pipeline` tier, which merges by its own run definition |
| `--submodules=` | `auto` · `off` | `auto` | `auto` means "run the sync only when `git submodule status` is non-empty" |
| `--solo=` | comma-separated id list | empty | forces single-slot dispatch for a task that needs an exclusive resource |
| `--on-fail=` | `continue` · `stop` | `continue` | `stop` drains the in-flight slots and halts the run |
| `--dry-run` | flag | off | prints the resolved plan — flags, ready set, slots, tier, withheld tasks — and dispatches nothing |

An unrecognized `--flag`, or a value outside a flag's vocabulary, stops the run
rather than silently falling back to a default: a mistyped `--paralel=4` never
quietly means `1`. Every resolved value, including defaults nobody typed, is
printed before dispatch begins.

`--parallel=auto` requests 8. What you actually get is the smallest of that, the
number of ready groups, the fixed ceiling of 8, and **the host's own concurrency
slots minus the one the orchestrator occupies** — 4 slots by default on
`codex-cli 0.147.0`, so three concurrent workers. Codex states that cap to the
orchestrator directly, and the orchestrator reads it rather than computing it
from configuration.

Two things are fixed and not configurable: the review fix-round budget (`K = 2`)
and the concurrency ceiling (`8`). Review gating is fixed by depth as well —
`low` and `medium` are advisory, `high` and `xhigh` block — and no flag changes
which.

`--worktree-root`, `--seed` and `--base` are deliberately not part of this
surface; each is owned elsewhere, and being unrecognized they stop the run.

## Execution tiers — and the Pipeline CLI is required, not optional

`--engine` picks the substrate that provisions a task's working directory.
Default `auto`.

| Tier | Needs | Provides |
|---|---|---|
| `toolkit` *(the only parallel tier)* | The `pipeline` CLI at **0.17.0** or above. `--engine=auto` resolves here once the installed CLI is at or above that version | One CLI-provisioned slot per worker: a working directory outside the repository, a `worktree-<task-id>` branch cut from an arbitrary base, a resolved env file and a port block, plus per-submodule worktrees, `ci-wait`, `submodule bump` and `gc` |
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
newer Codex build are in
[`docs/2026-08-09-codex-subagent-isolation.md`](docs/2026-08-09-codex-subagent-isolation.md).

Because the tier does not exist, `--engine=native` stops the run at parse time
with its own message rather than the generic unknown-value one — it is the value
a reader porting a Claude command line will type.

**The consequence is the inverse of the Claude plugin's.**

- **The Pipeline CLI is mandatory here, not an upgrade.** On Claude Code the CLI
  adds ports, submodule worktrees and an arbitrary base branch on top of a
  working `native` tier. On Codex there is no tier underneath `toolkit`.
- **`--parallel > 1` requires `toolkit` or `pipeline`.** Two Codex subagents
  working the same repository without CLI-provisioned slots collide on the same
  files, the same index and the same `HEAD` — with no host mechanism preventing
  it and no error when it happens.
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
redirect through. What Codex lacks is a boundary **between workers** — and that
is the only boundary the `native` tier is defined by.

| | Claude Code | Codex 0.147.0 |
|---|---|---|
| Worktree per worker | Yes, host-created | **No** — one shared tree |
| Tool-path write outside the boundary | Blocked | Blocked |
| Shell-path write outside the boundary | **Not blocked** | Blocked |
| Boundary between two workers | Yes | **None** |

The two hosts fail in opposite directions and neither is strictly safer. That
asymmetry is why this plugin is not a mechanical copy of the Claude one, and why
the CLI is optional on one host and required on the other.

### Why the minimum is 0.17.0

`--engine=auto` reads `pipeline --version` and compares it **numerically**
against `0.17.0` — never by checking that the binary exists, and never by probing
the subcommand. At or above it, `auto` resolves to `toolkit`. Below it, absent,
or unparseable, the run states the reason once and continues sequentially. A CLI
that is present but older resolves the same way, because a presence check would
resolve it to `toolkit` and then fail on first use — a silent misdetection
instead of an announced degradation.

**0.17.0 is the first published release whose `pipeline worktree list --json`
reports a hook-provisioned slot's `submodule_slots[].dir`.** That property is
what this plugin depends on, and it is *not* the same as "the first release
shipping `pipeline worktree`" — that derivation yields 0.16.0, and 0.16.0 is
unsafe. On released 0.16.0 the array is empty for every hook-provisioned slot, so
a resumed run enumerates the repositories a slot spans from an empty list and
concludes that a submodule slot holding uncommitted work is an empty shell. That
verdict destroyed 21,880 bytes of finished implementation in this design's own
proving run.

### What a sequential run withholds

Without the CLI, three kinds of task cannot run, and only these three:

- a task that needs a bound **port** — nothing hands out a free port block;
- a task whose `repo:` is a **submodule** — the session checkout's submodules are
  the shared ones, and a worker committing in them writes the checkout every
  other agent is using;
- a task that must integrate on a **base branch other than the repository
  default** — there is nowhere to cut a slot from another branch.

A withheld task's row stays pending, not failed. The reason is reported once per
run — naming the state, the gap and the affected task ids — and every other ready
task still runs. Installing `pipeline` at 0.17.0 or above and re-running is
normally all that unblocks them.

## Why `--merge` defaults to `ask`

`--merge=ask` holds each finished task at "verified, merge held" and waits for
you — nothing merges unattended. That is the default because an orchestrator that
merges pull requests by itself, by default, is a large blast radius for a plugin
anyone can install.

`--merge=on-green` (merge once CI is green, no blocking review finding is open,
and the row is behind no approval gate) and `--merge=never` (stop at "verified,
merge held" permanently, and never ask) both exist for when you want something
else — but they are opt-in, and neither bypasses branch protection nor elevates
under any circumstance. `--merge` governs the `toolkit` tier and the sequential
fallback; the `pipeline` tier merges by its own run definition instead.

## Workflow contract

- Artifacts live only in `.taskflow/YYYY-MM-DD-<slug>/`. Prefix every new folder
  with its local creation date; do not rename existing folders.
- `ROADMAP.md` is the sole mutable task-state record. Task specs are immutable
  and never contain `status`.
- Task groups run sequentially by `sequence`; independent groups may run in
  parallel when their `needs` dependencies allow it, `--parallel` is raised above
  its default, and an execution tier is available to place the workers.
- `security_critical` and `production_touching` raise the model-routing tier —
  a different thing from the execution tier above, and the two never interact.
- Production, money, secrets, irreversible effects, and product decisions require
  an explicit owner gate.

## What ships in this repository

```text
.codex-plugin/plugin.json         the plugin manifest
skills/taskflow-plan/             ┐
skills/taskflow-review/           │ the four public skills
skills/taskflow-tasks/            │
skills/taskflow-execute/          ┘ + references/ loaded only when a flag asks
.codex/agents/                    the two agent roles — copy these into your project
docs/taskflow-codex.svg           the animation at the top of this file
docs/2026-08-09-codex-subagent-isolation.md
```

`skills/taskflow-execute/references/` — `parallel-execution.md`,
`code-review.md`, `submodules.md` — are read **only** when the matching flag is
set, so a plain `taskflow-execute <slug>` loads one file and no more.

## License

[MIT](LICENSE) © Ivan Murzak
