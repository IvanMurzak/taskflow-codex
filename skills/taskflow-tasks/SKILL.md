---
name: "taskflow-tasks"
description: "Turn a reviewed Taskflow into immutable task specs, dependency-safe groups, model tiers, and ROADMAP execution waves."
---

# Taskflow tasks

Select one reviewed `.taskflow/YYYY-MM-DD-<slug>/`. Stop for unresolved product
questions or unapplied review findings.

Create `tasks/README.md` and one PR-sized immutable spec per task:

```yaml
---
id: "b3-example"
title: "One-line title"
group: "B"
sequence: 3
repo: "."
base_branch: "main"
depends_on: ["a2-example"]
importance: 1
complexity: 1
security_critical: false
production_touching: false
model_hint: "fast"
taskflow_refs: ["02-target-architecture.md"]
---
```

Follow with `## Goal`, `## Scope & seams`, and `## Definition of Done`. Never
add `status`; specs are immutable. `repo: "."` means the root repository and is
fully supported. Use a submodule path only when the task changes that submodule.

Populate ROADMAP waves and rows using:

`| Task (spec) | needs | repo/base | imp/cx | model | Status | Run / PR | Updated |`

Rules: one group is one conflict domain; run it by ascending `sequence`;
independent groups may overlap when dependencies allow. Complexity 1–4 maps to
`fast`, 5–7 to `mid`, 8–10 to `top`; raise one tier for security/production.
Add owner gates for production, money, secrets, and irreversible effects.

The ROADMAP is the only live state and only `taskflow-execute` updates it after
verification. Commit only the Taskflow folder when appropriate.
