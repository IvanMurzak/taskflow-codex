---
name: "taskflow-review"
description: "Adversarially verify a Taskflow against repository truth, authoritative specifications, and internal consistency, then correct confirmed non-product defects."
---

# Taskflow review

Select the named `.taskflow/YYYY-MM-DD-<slug>/`; use the only candidate when
unambiguous. Read the complete folder.

Verify three lenses, concurrently when useful:

- repository claims and feasibility, with `file:line` evidence;
- current authoritative external requirements, with citations;
- cross-document decisions, dependencies, migration, security, UX, and ROADMAP
  consistency.

Classify confirmed findings P0 (broken guarantee), P1 (material gap), or P2
(clarity/staleness). Challenge each finding, deduplicate, then apply factual and
mechanical corrections in one batch. Never change a product decision: present
the evidence and recommendation, obtain the owner choice, and record it as
dated `REVISED`.

Check that `ROADMAP.md` is the sole live task-state record; task specs contain no
`status`; waves, gates, dependencies, and specs agree; execution has an isolated
worktree path. Update the README and ROADMAP log, then commit only the Taskflow
folder when appropriate. Continue with `taskflow-tasks` when no finding or owner
question remains.
