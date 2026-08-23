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

If a submodule worktree or safe pointer update cannot be established, keep the
task pending; do not fall back to the shared checkout.
