---
name: "taskflow-execute"
description: "Execute ready Taskflow tasks through isolated workers, verify evidence, merge per policy, and update ROADMAP as its sole writer."
---

# Taskflow execute

You are the scheduler, never the implementer. Delegate every task. `ROADMAP.md`
is the only live state and only you may edit it.

## Defaults

`--parallel=1`, `--review=off`, `--merge=on-green`, `--engine=auto`,
`--submodules=auto`. Reject unknown or conflicting values. `auto` parallelism is
bounded by ready work, one task per conflict group, and available worker slots.

Accepted options: `--scope=all|wave:N|group:X|<ids>`, `--parallel=N|auto`,
`--review=off|low|medium|high|xhigh`, `--merge=ask|on-green|never`,
`--engine=auto|native|toolkit|pipeline`, `--pipeline=<name>` (pipeline engine
only), `--submodules=auto|off`, `--solo=<ids>`,
`--on-fail=continue|stop`, and `--dry-run`.

Load references only when needed:

- parallelism, isolation, merge, or cleanup: `references/parallel-execution.md`;
- review enabled: `references/code-review.md`;
- detected submodules and sync enabled: `references/submodules.md`.

## Preflight and scheduling

1. Resolve one `.taskflow/YYYY-MM-DD-<slug>/`; read its README and ROADMAP, not
   task bodies. Reconcile `🔵`/`🟣` rows with branches, worktrees, PRs, and CI.
2. A task is ready when all `needs` are `✅`, its group has no earlier unfinished
   sequence, its owner gates are satisfied, and its repository does not conflict
   with another selected task.
3. Obtain `repo`, `base_branch`, and `id` from ROADMAP. For legacy boards, parse
   only task frontmatter mechanically; never load the task body into scheduler
   context.
4. `--dry-run` prints resolved options, ready/withheld tasks, and planned slots,
   then exits without writes or workers.

## Isolation on Codex

Codex subagents share the caller's cwd. Therefore every dispatched task needs a
real git worktree created before spawn. `--engine=auto` uses a compatible
Pipeline CLI when available, otherwise native `git worktree`; the CLI is not
required for ordinary repositories.

- `repo: "."` means the root git repository. Create one root-repository worktree
  per task; never force root tasks into the shared checkout.
- A submodule task gets a worktree from that submodule repository.
- The shared checkout is scheduler-only during parallel work. Workers write only
  their task worktree.
- `toolkit` uses the Pipeline CLI; `pipeline` delegates the lifecycle to a named
  pipeline; `native` uses git worktrees. Stop if isolation cannot be established.

See `references/parallel-execution.md` for lifecycle commands and constraints.

## Dispatch contract

For each selected row:

1. Provision `worktree-<task-id>` from its declared base.
2. Mark all selected rows `🔵` and commit the ROADMAP once for the batch.
3. Spawn all implementers before waiting for any of them. Use the
   `taskflow-implementer` role and `fork_turns: "none"`.
   If that role is unavailable, stop before dispatch; never replace it with a
   generic agent plus an inlined brief.
4. The spawn message must contain **exactly one value: the absolute path to the
   immutable task file**. Do not paste, summarize, or pre-read its body; do not
   include the board, sibling tasks, worktree path, or merge permission. The
   worker reads the file and locates its prepared worktree by task id.
5. Wait for every worker in the batch. A round does not end until each outcome
   is verified and recorded. If a spawn is refused, leave that task pending and
   continue tracking already-started workers.

Verify each DoD item from repository/PR/CI evidence, never from the worker's
claim. If review is enabled, use a different reviewer and follow
`references/code-review.md`.

## Merge and state

- `on-green` (default): merge only after DoD verification, required review, and
  required CI pass; never bypass protection.
- `ask`: hold verified work at `🟣` for owner approval.
- `never`: leave verified PRs open at `🟣`.

Record `✅` only after the merge/change is verified; record `⛔` with a concise
cause when execution fails. Commit board outcomes once per round, sync touched
submodules once, clean finished worktrees, recompute readiness, and continue.
Never edit task specs, implement inline, run conflicting group tasks together,
or treat an unverified worker report as completion.

When every row is `✅`, move the Taskflow folder to `.taskflow/archive/` only if
that destination is free, then commit that move.
