# Submodules

Load only when `git submodule status` is non-empty and `--submodules != off`.

- `repo: "."` is the root repository; any other `repo` must match a declared
  submodule path.
- Give a submodule task a worktree created by that submodule repository. Never
  let it edit the shared submodule checkout.
- Use the task's declared `base_branch`; do not assume `main`.
- Workers never update superproject pointers.
- After a round, sync only submodules whose PRs merged in that round, verify the
  expected commit, then make one pointer-bump commit. Do not absorb unrelated
  dirty or drifted submodules.
- With `--submodules=off`, leave pointers unchanged and report that once.
- With `--integration-branch`, a submodule task's worktree must be cut from that
  submodule's own copy of the integration ref, created from that submodule's own
  `base_branch`. A superproject ref does not reach a submodule, and a stale local
  ref is not the remote's — prefer the remote-tracking ref.
- A provisioner may accept a requested base for the superproject and silently
  ignore it for submodules, or replay an earlier create's answer on a resumed
  worktree. Confirm each submodule worktree's ACTUAL position before dispatch and
  fail the task if it is not on the integration ref; a provisioning call that
  returned success is not evidence of placement.

If a submodule worktree or safe pointer update cannot be established, keep the
task pending; do not fall back to the shared checkout.
