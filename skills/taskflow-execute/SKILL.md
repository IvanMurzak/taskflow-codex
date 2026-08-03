---
name: "taskflow-execute"
description: "Orchestrate a completed Taskflow from its ROADMAP status board: compute ready tasks, dispatch within dependency and conflict limits, verify repository and CI evidence, and update the board as its sole writer."
argument-hint: "[<taskflow slug>] [scope: wave, group, or task subset — default: whole board]"
---

# Taskflow execute

Use this skill only after the owner explicitly authorizes execution.

## Preconditions and state

- Default root: `.claude/taskflow/`; use one `<slug>/` folder. Honor a supplied
  slug, resolve ambiguity with the owner, and never read or fall back to
  legacy workflow artifacts.
- Stop unless the frame is locked/reviewed, `tasks/` is populated, and ROADMAP
  has a status board. Reconcile all non-pending rows against available
  forge/CI evidence; if unavailable, inspect branches, commits, merged
  revisions, test evidence, and executor locks.
- ROADMAP is the only mutable task-state record. This orchestrator is its sole
  writer. Implementers do not edit ROADMAP or immutable specs. Commit each
  board change surgically with a progress-log entry where applicable.
- If a workspace planning system exists, maintain one thin pointer to ROADMAP,
  never a mirrored per-task state store.

## Orchestration loop

1. Honor an owner scope or resolve the whole board. The ready set is pending
   rows with completed `needs` and cleared gates. Run a conflict group strictly
   by `sequence`; run only independent groups in parallel.
2. For production, money, secrets, or irreversible effects, request a distinct
   owner GO via the available input mechanism. Offer a safe recommendation
   first and log the confirmed decision before dispatch.
3. Check existing branches, reviews, runs, and locks to avoid duplicate work.
   Use the project's normal execution and forge/CI facilities where available.
   Otherwise give one isolated worktree worker each immutable task spec—Goal,
   Scope & seams, DoD, and taskflow references—and never permission to edit
   ROADMAP.
4. Record dispatch as `🔵 running` with a run reference/date and commit. Track
   with available forge/CI evidence or local branch/commit/test/review evidence;
   do not busy-wait.
5. Record an opened review as `🟣 review`. Merge only with repository-policy and
   explicit owner authorization. Verify every DoD item before recording `✅`
   with a change reference/date and a progress entry, then recompute readiness.
6. On failure record `⛔` with a concise reason; retry, rescope, or escalate
   rather than silently continuing. At each wave boundary report landed,
   running, blocked work, risks, and resource concerns.

When all scoped rows are verified complete, update the taskflow README and
ROADMAP counter, remove a temporary thin pointer if one was created, commit, and
report results and gates. Do not accept a worker report as completion evidence,
run same-group tasks concurrently, edit specs, implement inline, or leave board
updates uncommitted.
