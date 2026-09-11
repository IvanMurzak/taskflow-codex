# Parallel execution on Codex

Codex provides concurrent agents but no per-agent cwd. The scheduler must create
one git worktree per task before spawning workers. The root repository is a valid
task repository; `repo: "."` means create the worktree from that repository.

## Capacity and dispatch

Select at most `min(--parallel, available worker slots, ready conflict groups)`.
Issue every `spawn_agent` call before the first wait. Use
`fork_turns: "none"`; each message is only the absolute task-file path. A worker
finds its slot by `worktree-<task-id>` in the repository named by the spec.
Request the registered custom agent by its `name`, `taskflow-implementer`. If
Codex cannot resolve that name, stop before dispatch. Keep the inherited sandbox
and permission policy; a custom-agent file is not authority to weaken live
runtime restrictions.

After dispatch, wait with `wait_agent` using a long timeout. Do not alternate
short sleeps with status polls. If a bounded wait expires, take one status
snapshot and then issue another long blocking wait only when work is still live.

## Native isolation

Resolve the task repository and base without reading the task body. Create a
branch/worktree named `worktree-<task-id>` in a writable sibling/temp worktree
root. Verify its toplevel differs from the shared checkout before dispatch.
Never reuse one worktree for two tasks. Native mode needs no Pipeline CLI.

Preflight that the selected root is writable under the current Codex sandbox.
If a sibling or temporary root is outside the authorized workspace, stop and
tell the owner to restart Codex with `--add-dir <worktree-root>` or select an
already-authorized root. Never weaken the sandbox and never use the shared
checkout as a fallback.

On resume, reconcile the board against `git worktree list --porcelain`, branch,
PR, and CI state. Remove a worktree only after its worker has ended and its work
is committed or merged. Never delete unknown, dirty, locked, or unmerged slots.

## Toolkit isolation

Use toolkit when installed and compatible, or when ports/submodule automation is
needed. Run from the project root and require `status: created`; a reused slot
must be reconciled before dispatch.

```text
pipeline worktree create --name <task-id> --base <base> --submodules <paths> --ports <n> --json
pipeline worktree finalize --name <task-id> --base <base> --submodules <paths> --json
pipeline worktree destroy --name <task-id> --outcome completed --json
pipeline worktree list --json
pipeline ci-wait --pr <n> --repo <owner/repo> --timeout <seconds> --json
pipeline submodule bump --project-root <root> --base <superproject-target-ref> --source-worktree <superproject-pointer-source-worktree> --no-admin
pipeline gc --project <root> --clean --json
```

The worktree root must be writable by the Codex session. If toolkit fails,
`auto` may use native git worktrees; never fall back to the shared checkout.

## Merge

`on-green` merges only when DoD, required review, and required CI are green.
`ask` and `never` leave the row `🟣`. Workers and reviewers never merge. Never
bypass protection or delete branches/worktrees whose ownership is uncertain.

## Integration branch

With `--integration-branch`, create or adopt the ref in each repository on the
board before dispatch, and pass it as the base when provisioning each slot.
For toolkit provisioning, set
`PIPELINE_WT_INTEGRATION_BRANCH=<integration-ref>` in every worktree-create
command's environment as well as passing the base explicitly.
Then verify: read back the slot's ACTUAL position per repository and refuse the
dispatch if it is not the integration ref. A provisioner may honour a base for
the superproject and silently ignore it for submodules, and a reused slot may
report the base its ORIGINAL create used rather than the one requested now — a
success return is not placement evidence. Task PRs target the integration ref;
one final PR merges it into `base_branch`.

After verifying placement, set and read back the branch-scoped PR target:

```text
git config branch.worktree-<task-id>.taskflow-pr-base <integration-ref>
```

The implementer reads this key and otherwise falls back to the immutable task's
`base_branch`. This preserves the path-only spawn contract.

For a submodule pointer bump, use the superproject's immutable base branch when
integration is off and its integration ref when integration is active. The
`--source-worktree` is a dedicated scheduler-owned **superproject** worktree on
that target ref, never the submodule worker slot. In it, check out the exact
verified submodule commit in only the affected submodule, stage its gitlink, and
verify that the staged diff contains the expected `160000` entry and no
unrelated paths. Pass that superproject worktree to the bump command. Land or
otherwise make the submodule commit reachable on its target ref before landing
the superproject pointer PR. This is an ordered cross-repository operation, not
an atomic merge guarantee.
