# Code review

Load only when `--review` is not `off`. The reviewer must be a different agent
from the implementer and must inspect the actual diff.

Use Codex's native `spawn_agent` and request the registered custom agent whose
`name` is `taskflow-reviewer`. Do not fall back to a generic or external agent
when Codex cannot resolve that name.

The initial reviewer prompt contains only these fields:

```text
task_file: <absolute immutable task path>
depth: <low|medium|high|xhigh>
repository: <absolute task repository path>
head: <worker branch or PR head SHA>
base: <actual PR target ref>
round: 0
```

The reviewer reports zero or more findings as `severity`, `file`, `line`,
`summary`, and `blocking`, plus the reviewed head SHA and anything unverified.
Keep both agent threads available until review closes.

| Depth | Check | Effect |
|---|---|---|
| `low` | DoD and obvious defects in changed files | advisory |
| `medium` | low + reuse, simplicity, tests, adjacent callers | advisory |
| `high` | medium + edge cases, failures, races, security | blocking |
| `xhigh` | high + independent correctness/security/reproducibility lenses | blocking |

The reviewer posts actionable findings with file/line evidence. The implementer
fixes them; the reviewer verifies the fix. Allow at most two fix rounds. After
that, leave blocking work unmerged and record the reason. Never let a worker
review its own diff or let a reviewer implement/merge.

For a fix round, use Codex's native steer operation on the existing implementer
thread, containing the
reviewed head SHA, PR URL, round number, and the reviewer findings verbatim. The
implementer fixes only confirmed findings in its existing worktree, commits,
pushes, and reports the new SHA. Wait for that turn, then steer the existing
reviewer thread with the new SHA and round number and wait for its re-review. Do
not spawn replacement generic agents or lose reviewer/implementer separation.
