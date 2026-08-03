---
name: "taskflow-tasks"
description: "Decompose a reviewed Taskflow folder into immutable implementation-ready task specifications, conflict-safe groups, dependencies, model tiers, and ROADMAP execution waves."
argument-hint: "[<taskflow slug> — default: the single taskflow under .claude/taskflow/]"
---

# Taskflow tasks

Use this skill only when the owner explicitly asks to specify work for a locked,
reviewed taskflow with no unresolved product question.

## Location and outputs

- Default root: `.claude/taskflow/`; use one `<slug>/` folder. Honor a supplied
  slug and resolve ambiguity with the owner. Never use legacy workflow
  artifacts.
- Write `<slug>/tasks/README.md` with the coefficient legend, model rubric,
  group table, and a pointer to `../ROADMAP.md`.
- Write one immutable `<slug>/tasks/<id>-<slug>.md` per PR-able task:

  ```markdown
  ---
  id: "b3-pairing-plane"
  title: "One-line task title"
  group: "B"
  sequence: 3
  repo: "repo-or-submodule-path"
  depends_on: ["a2-library-gate"]
  importance: 1
  complexity: 1
  security_critical: false
  production_touching: false
  model_hint: "fast"
  taskflow_refs: ["02-target-architecture.md", "04-protocol.md"]
  ---

  ## Goal
  ## Scope & seams
  ## Definition of Done
  ```

`sequence` increases strictly within its group. Never include `status`: specs
are immutable and all live task state belongs solely to `ROADMAP.md`.

## ROADMAP update

Populate execution waves and its single status board:

```text
| Task (spec) | needs | imp/cx | model | Status | Run / PR | Updated |
| [b3-pairing-plane](tasks/b3-pairing-plane.md) | a2 | 9/7 | top | ⬜ pending | | |
```

State explicitly that the board is the only task-state record, that the ready
set is computed from `needs` and completed rows, and that only
`taskflow-execute` updates board rows/progress after evidence verification. A
workspace planning facility gets at most one thin pointer to this ROADMAP;
never duplicate every task's state. Add explicit owner gates for production,
money, secrets, and irreversible effects.

## Routing and safe parallelism

- Importance measures impact of a missing/incorrect task. Complexity measures
  depth, surface, risk, and correctness cliffs.
- Complexity ≥8 maps to `top`, 5–7 to `mid`, and ≤4 to `fast`.
  `security_critical` or `production_touching` raises one tier, with `top`
  remaining top. These are consumer-project-approved model tiers, not pinned
  model names.
- A group is one merge-conflict domain. Run one group strictly by ascending
  `sequence`; if overlap is uncertain, keep the tasks in one group.
- Independent groups may run in parallel only when `depends_on` permits it.
  End an artifact-producing group with an integration/publish gate that
  downstream groups depend on.

Update the taskflow README, commit only this taskflow folder when appropriate,
and wait for an explicit owner GO before `taskflow-execute`.
