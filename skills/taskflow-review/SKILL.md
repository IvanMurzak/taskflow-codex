---
name: "taskflow-review"
description: "Adversarially verify a Taskflow folder against repository code, authoritative external specifications, and internal consistency, then apply confirmed non-product corrections in one batch."
argument-hint: "[<taskflow slug> — default: the single YYYY-MM-DD-<slug> folder under .taskflow/]"
---

# Taskflow review

Any user or agent may invoke this skill to review an existing taskflow. It
verifies rather than summarizes.

## Select and read artifacts

- Default root: `.taskflow/`; select one `YYYY-MM-DD-<slug>/` folder. Honor a
  supplied slug; if more than one folder could apply, ask the owner.
- Read the complete folder: README, ROADMAP, numbered documents, and `tasks/`
  when present. Never use legacy workflow artifacts as input or fallback.

## Adversarial process

1. Independently investigate three areas, using available repository search,
   web research, and delegation where useful:

   - **Repository truth:** verify factual and feasibility claims against source
     with `file:line` evidence, including byte-level and cross-language parity.
   - **External conformance:** consult current authoritative standards, protocol
     specifications, vendor behavior, and SDK source. Cite MUST/SHOULD issues.
   - **Consistency and completeness:** test decisions, requirements,
     dependencies, migration, gates, threat coverage, UX budgets, stale text,
     and ROADMAP/task-spec state ownership against one another.

   Classify P0 (broken guarantee/material falsehood), P1 (gap/risk), and P2
   (wording/stale text). Each investigation also lists what it verified sound.
2. Wait for all investigations, deduplicate their evidence, and correct only
   confirmed factual or mechanical issues in one coherent batch.
3. Never override an owner product decision. For deployment, compatibility,
   identity, UX, monetization, scope, production effects, money, secrets, or
   irreversibility, present evidence and a safe recommendation, obtain the
   owner decision, then write `REVISED` with date and rationale in the ledger.
4. Sweep the entire taskflow folder for every replaced term, parameter, number,
   and path. Update README status and ROADMAP's progress log, then commit only
   the taskflow folder when a commit is appropriate.

## Required checks

- `ROADMAP.md` is the only mutable task-state record and its executing
  orchestrator is its only writer after evidence verification.
- Specs never contain `status`; they contain `sequence`,
  `security_critical`, and `production_touching` when tasks exist.
- Waves, dependency edges, migration phases, and gates agree.
- The execution plan uses available forge/CI capabilities or, if absent,
  isolated worktrees with local repository evidence.

The next stage is `taskflow-tasks`; a user or agent may invoke it when the
review is complete.
