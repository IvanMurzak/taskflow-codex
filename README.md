# Taskflow for Codex

Taskflow is a four-stage lifecycle that a user or agent can invoke to turn a fuzzy change
into repository-evidenced architecture, adversarial verification, immutable task
specifications, and ROADMAP-driven execution.

```text
taskflow-frame → taskflow-review → taskflow-tasks → taskflow-execute
```

## Package

This self-contained Codex package has its manifest at
`.codex-plugin/plugin.json` and its four public skills in `skills/`.

## Workflow contract

- New artifacts live only in `.taskflow/YYYY-MM-DD-<slug>/`. Prefix every new
  Taskflow folder with its local creation date; do not rename existing folders.
- `ROADMAP.md` is the sole mutable task-state record. Task specs are immutable
  and never contain `status`.
- Task groups run sequentially by `sequence`; independent groups may run in
  parallel when their `needs` dependencies allow it.
- `security_critical` and `production_touching` raise the model-routing tier.
- Production, money, secrets, irreversible effects, and product decisions
  require an explicit owner gate.

Legacy `.claude/design/` and `.claude/taskflow/` folders are archives and are
not read or migrated.

## License

MIT
