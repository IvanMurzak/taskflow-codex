# Submodules

Load only when `git submodule status` is non-empty and `--submodules != off`.

- `repo: "."` is the root repository; any other `repo` must match a declared
  submodule path.
- Give a submodule task a worktree created by that submodule repository. Never
  let it edit the shared submodule checkout.
- Use the task's declared `base_branch`; do not assume `main`.
- Workers never update superproject pointers.
- After a round, sync only submodules whose PRs merged in that round and verify
  the expected commits are reachable on their target refs. Create a dedicated
  scheduler-owned superproject worktree from the superproject target ref
  (`base_branch`, or its integration ref when active). In that worktree, check
  out each exact verified commit in only its affected submodule and stage the
  resulting gitlink. Verify the staged diff contains only the expected
  `160000` gitlink entries, then make one pointer-bump commit/PR. Never use a
  submodule worker slot as this source and never absorb unrelated dirty or
  drifted submodules.
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
- Treat the superproject as a derived landing repository even when no task row
  has `repo: "."`. Create/push/verify its integration ref, record its final PR
  in the ROADMAP integration-landings table, and do not archive until that
  gitlink landing is merged and verified.

If a submodule worktree or safe pointer update cannot be established, keep the
task pending; do not fall back to the shared checkout.
