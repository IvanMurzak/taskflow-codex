---
name: "taskflow-plan"
description: "Plan a structural change from repository evidence and owner decisions, then create a Taskflow architecture set and ROADMAP."
---

# Taskflow plan

Create one `.taskflow/YYYY-MM-DD-<slug>/` folder. Reuse it if it exists; never
write Taskflow artifacts elsewhere or implement the change.

1. Inspect every affected repository. Cite current-code claims as `file:line`.
2. Ask only owner decisions that materially affect product scope, compatibility,
   UX, deployment, money, secrets, or irreversible behavior. Recommend an option
   and record each answer as dated D1, D2, …; mark later changes `REVISED`.
3. Write a self-contained set:
   - `README.md`: problem, status, decisions, summary, document map.
   - `ROADMAP.md`: implementation ledger, waves, gates, progress log, and board.
   - `01-current-architecture.md`: verified behavior and change seams.
   - `02-target-architecture.md`: target design, decisions, trade-offs.
   - Add focused flow, subsystem, infrastructure, migration, security, or UX
     documents only when the change needs them.
4. Use this board schema:

   `| Task (spec) | needs | repo/base | imp/cx | model | Status | Run / PR | Updated |`

`ROADMAP.md` is the only live task-state record. Commit only the Taskflow folder
when a commit is appropriate. Continue with `taskflow-review` when decisions are
locked.
