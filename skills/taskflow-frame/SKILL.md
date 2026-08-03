---
name: "taskflow-frame"
description: "Frame a system or feature change from verified repository evidence and owner decisions, then write a self-contained Taskflow architecture set and ROADMAP. Use for structural features and architectural changes."
argument-hint: "<what to frame> [taskflow slug — writes .claude/taskflow/<slug>]"
---

# Taskflow frame

Use this skill only when the owner explicitly asks to start the Taskflow
lifecycle. It establishes the durable architecture frame; it does not begin
implementation.

## Artifact contract

- Create exactly one `.claude/taskflow/<kebab-slug>/` folder per taskflow. A
  caller may select the slug but cannot redirect artifacts outside
  `.claude/taskflow/`. If the folder exists, read it before extending it.
- Legacy workflow artifacts are archives: do not read, migrate, or use them as
  fallback.

## Frame from evidence

1. Resolve the slug and report the intended folder. Extract the problem and ask
   2–4 owner questions that materially change the result. Product decisions—
   deployment target, compatibility, identity, UX, monetization, scope, and
   irreversible behavior—belong to the owner. Offer a safe recommendation
   first, then record the confirmed answer.
2. Use available filesystem search and delegated investigation to explore each
   affected repository or subsystem. Every factual code claim must cite the
   source as `file:line` found in this session. Capture existing behavior,
   concrete change seams, risks, and unanswered assumptions.
3. Write a self-contained artifact set in `<slug>/`:

   | File | Content |
   |---|---|
   | `README.md` | Status, problem, locked decisions, summary, document map, glossary. |
   | `ROADMAP.md` | Implementation ledger: status, waves, gates, board skeleton, progress log. |
   | `01-current-architecture.md` | Evidence-only behavior, edge cases, and seam index. |
   | `02-target-architecture.md` | Principles, roles/models, D1..Dn decision ledger, trade-offs, open questions. |
   | `03-*.md` | Actor flows including failure, expiry, and offline paths where relevant. |
   | `04-*.md` | Subsystem rules, data structures, precedence, and test approach. |
   | `05-infrastructure.md` | Deployment/secrets delta and rollback when applicable. |
   | `06-migration-rollout.md` | Phases, dependencies, gates, legacy disposition, risks, rollback. |
   | `07-security.md` | Credential inventory, threat-to-control table, handling, security gates. |
   | `08-user-workflows.md` | Persona journeys with counted UX budgets as release gates. |

4. Put in `ROADMAP.md` a clear banner that it is this taskflow's implementation
   ledger, not a workspace-wide roadmap. Include status, last update, timeline,
   human gates, progress log, and this board skeleton:

   ```text
   | Task (spec) | needs | imp/cx | model | Status | Run / PR | Updated |
   ```

   The board is the sole task-state record. It may remain empty until
   `taskflow-tasks`; only `taskflow-execute` later changes it after verification.
5. Record each owner answer as a dated D1, D2, and so on in both the README and
   target ledger. Mark amendments `REVISED` with a date and rationale.

Commit only the taskflow folder when a commit is appropriate. When the frame is
stable, the next owner-invoked stage is `taskflow-review`.
