---
name: "taskflow-execute"
description: "Execute ready Taskflow tasks through isolated workers, verify evidence, merge per policy, and update ROADMAP as its sole writer."
---

# Taskflow execute

You are the scheduler, never the implementer. Delegate every task. `ROADMAP.md`
is the only live state and only you may edit it.

## Defaults

`--parallel=1`, `--review=off`, `--merge=on-green`, `--engine=auto`,
`--submodules=auto`, `--integration-branch=auto`. Reject unknown or conflicting values. `auto` parallelism is
bounded by ready work, one task per conflict group, a fixed ceiling of 8, and
available worker slots excluding the scheduler.

Accepted options: `--scope=all|wave:N|group:X|<ids>`, `--parallel=N|auto`,
`--review=off|low|medium|high|xhigh`, `--merge=ask|on-green|never`,
`--engine=auto|native|toolkit|pipeline`, `--pipeline=<name>` (pipeline engine
only), `--submodules=auto|off`, `--solo=<ids>`,
`--on-fail=continue|stop`, `--integration-branch=auto|off|<name>`, and
`--dry-run`.

`--solo=<ids>` forces each named task into a one-task batch even when other
groups are ready. With `--on-fail=continue`, drain the current batch, record all
outcomes, and continue with other ready groups; with `stop`, drain and record the
batch but dispatch nothing else. Outside the `pipeline` engine, reject
`--merge=never` together with an active integration branch; use
`--integration-branch=off` when every task PR must stay open.
`--parallel=auto` requests 8, while an explicit larger value is capped at 8 and
reported.

For the `pipeline` engine, Taskflow's merge and integration lifecycle does not
run: resolve an omitted `--integration-branch` to `off`, require an explicitly
provided value to be `off`, and report that `--merge` is owned by the pipeline.

Load references only when needed:

- parallelism, isolation, merge, or cleanup: `references/parallel-execution.md`;
- review enabled: `references/code-review.md`;
- detected submodules and sync enabled: `references/submodules.md`.

## Model routing

ROADMAP's `model` column is an execution hint. Resolve `fast` to `gpt-5.6-luna`
with low effort, `mid` to `gpt-5.6-terra` with medium effort, and `top` to `gpt-5.6-sol`
with high effort. Pass the resolved model and reasoning
effort as explicit spawn values when the current Codex spawn interface supports
them. The bundled custom-agent TOMLs intentionally do not pin a model, so the
task choice can apply. If a named model or effort is unavailable, inherit the
parent values and record once that the hint was not applied; never invent an
unavailable model id.

## Preflight and scheduling

1. Resolve one `.taskflow/YYYY-MM-DD-<slug>/`; read its README and ROADMAP, not
   task bodies. Reconcile `🔵`/`🟣` rows with branches, worktrees, PRs, and CI.
2. A task is ready when all `needs` are `✅`, its group has no earlier unfinished
   sequence, its owner gates are satisfied, and no selected task shares its
   declared conflict group or an overlapping path/resource domain.
3. Obtain `id`, `group`, `seq`, `repo`, and `base_branch` from ROADMAP. For
   legacy boards lacking these columns, parse only task frontmatter
   mechanically; never load the task body into scheduler context.
4. Reconcile the ROADMAP integration-landings table against final PRs and
   remote refs. A final landing is live state, not an implicit consequence of
   task rows.
5. `--dry-run` prints resolved options, ready/withheld tasks, planned slots,
   and the integration ref per repository, then exits without writes, workers,
   or refs.

## Isolation on Codex

Codex subagents share the caller's cwd. Therefore every dispatched task needs a
real git worktree created before spawn. `--engine=auto` uses a compatible
Pipeline CLI when available, otherwise native `git worktree`; the CLI is not
required for ordinary repositories.

Compatibility means `pipeline --version >= 0.17.0`, compared numerically as
semver. In `auto`, an absent, unparseable, or older CLI resolves to `native` and
the scheduler reports the reason once. Explicit `toolkit` with an incompatible
CLI stops before dispatch.

- `repo: "."` means the root git repository. Create one root-repository worktree
  per task; never force root tasks into the shared checkout.
- A submodule task gets a worktree from that submodule repository.
- The shared checkout is scheduler-only during parallel work. Workers write only
  their task worktree.
- `toolkit` uses the Pipeline CLI; `pipeline` delegates the lifecycle to a named
  pipeline through the installed Codex Pipeline skill; `native` uses git worktrees.
  Stop if isolation cannot be established.

See `references/parallel-execution.md` for lifecycle commands and constraints.

## Pipeline engine

With `--engine=pipeline`, require the Codex Pipeline plugin and the explicit
`--pipeline=<name>`. Invoke `$pipeline:run ./.pipeline/<name>` in the current Codex session
and require `manager` mode. In manager mode, the Pipeline skill spawns the
registered custom agent whose `name` is `pipeline-manager`. Never shell out to
another model or agent CLI and never launch a process-based driver. If the
pipeline explicitly declares another runner, stop before dispatch.

The named pipeline owns task isolation, implementation, review, PR, CI, merge,
integration, and cleanup. Do not also provision a Taskflow worktree or spawn a
`taskflow-implementer` for the same row. Supply the immutable task-file path
through the named pipeline's documented task-input contract. If the Pipeline
skill, requested runner, registered manager role, or task-input contract is not
available, stop before dispatch rather than changing execution hosts or modes.

## Dispatch contract

For each selected row outside the `pipeline` engine:

1. Provision `worktree-<task-id>` from its declared base.
2. Mark all selected rows `🔵` and commit the ROADMAP once for the batch.
3. Spawn all implementers before waiting for any of them. Call Codex's native
   `spawn_agent`, request the registered custom agent whose `name` is
   `taskflow-implementer`, and use `fork_turns: "none"`. If Codex cannot resolve
   that custom-agent name, stop before dispatch; never replace it with a generic
   agent, an inlined brief, or an external agent host. Subagents inherit the
   parent sandbox and live permission overrides; do not weaken them.
4. The spawn message must contain **exactly one value: the absolute path to the
   immutable task file**. Do not paste, summarize, or pre-read its body; do not
   include the board, sibling tasks, worktree path, or merge permission. The
   worker reads the file and locates its prepared worktree by task id.
5. Wait for every worker in the batch with Codex's blocking `wait_agent`
   mechanism and a long timeout. Do not implement a repeated shell-sleep or
   short polling loop. A round does not end until each outcome is verified and
   recorded. If a spawn is refused, leave that task pending and continue
   tracking already-started workers.

Verify each DoD item from repository/PR/CI evidence, never from the worker's
claim. If review is enabled, use a different reviewer and follow
`references/code-review.md`.

## Integration branch

Outside the `pipeline` engine, `--integration-branch=auto|off|<name>` defaults
to `auto`. `auto` derives
`taskflow/<slug>` from the Taskflow folder name. Task PRs then target that ref
instead of `base_branch`, and the whole Taskflow lands as ONE reviewed merge —
so concurrent Taskflows never share a branch, and the default branch sees one
coherent change with one combined CI run.

**It is one ref per landing repository, using the same Taskflow ref name, not
one global ref.** The landing set contains every distinct task `repo` plus the
superproject `.` whenever any task targets a submodule. Thus a submodule-only
board still has a superproject integration ref for its gitlink change. Create
each ref in THAT repository, cut from THAT repository's own `base_branch`.
Resolve the derived superproject base from repository evidence; stop if it is
ambiguous. Never assume one repository's default branch from another's.

Before writes, ensure ROADMAP has one integration-landings row per landing
repository with `repo`, `base_branch`, `integration_ref`, `Final PR`, `Status`,
and `Updated`. Reconcile these rows on resume. Only the scheduler edits them.

1. **Preflight, before any dispatch.** For each repository on the board, create
   the ref if absent, or adopt it unchanged if present — a resumed run must
   reuse the ref it already created, never recreate or reset it. Push the ref
   to `origin`, set upstream tracking, and verify the remote ref resolves to the
   same commit before provisioning any worker; the implementer must never be
   handed a PR target that exists only locally.
2. **Verify the host honoured the base.** Provisioning may accept a requested
   base and silently place the worker somewhere else — in a submodule, or on a
   resumed worktree that replays an earlier create. After provisioning, confirm
   each worker's worktree is actually positioned on the integration ref, and
   treat a mismatch as a failed dispatch: leave the row pending and report it.
   An unverified base is the failure this option exists to prevent, so never
   infer it from the absence of an error.
   After verification, record the PR target in that task repository as
   `branch.worktree-<task-id>.taskflow-pr-base=<integration-ref>` and read it
   back. This branch-scoped git config is how the path-only implementer learns
   the integration target without reading ROADMAP or receiving extra prompt
   text.
3. **Refresh at round boundaries.** Merge `base_branch` into the integration ref
   between rounds so the final merge does not accumulate drift, then push and
   verify the updated remote ref. On conflict, stop and report; never force,
   never rebase a shared ref.
4. **Land once.** When every task row for a repository is `✅` (and, for the
   derived superproject, every required gitlink bump is present), open ONE PR
   from the integration ref to `base_branch`, record it in that repository's
   integration-landings row, and apply `--merge`. Keep the landing row `🟣`
   while approval or CI is pending; mark it `✅` only after the final merge is
   verified. That PR is the combined CI run; independently green task PRs are
   not evidence that their union is green.
5. **Never delete a ref that holds unmerged work**, and keep the board row
   pointing at it so host cleanup spares it.

With `off`, task PRs target `base_branch` directly and none of the above runs.

## Merge and state

- `on-green` (default): merge only after DoD verification, required review, and
  required CI pass; never bypass protection. With an integration branch, this
  governs both the task PRs into that ref and the single PR out of it.
- `ask`: hold verified work at `🟣` for owner approval.
- `never`: leave verified PRs open at `🟣`.

With an integration branch, these policies apply first to each task PR and then
to the final integration PR. Under `ask`, merge and mark a task `✅` only after
its approval; the final PR is created after all task rows reach `✅`, and its
integration-landings row remains `🟣` until the owner approves and the merge is
verified. Under `never`, task rows remain `🟣`, so no final PR is created unless
a later owner-authorized resume changes the merge policy.

Record `✅` only after the merge/change is verified; record `⛔` with a concise
cause when execution fails. Commit board outcomes once per round, sync touched
submodules once, clean finished worktrees, recompute readiness, and continue.
Never edit task specs, implement inline, run conflicting group tasks together,
or treat an unverified worker report as completion.

Move the Taskflow folder to `.taskflow/archive/` only when every task row is
`✅` and, when integration is active outside the pipeline engine, every
integration-landings row is also `✅` with its final merge verified. Require a
free destination, then commit that move.
