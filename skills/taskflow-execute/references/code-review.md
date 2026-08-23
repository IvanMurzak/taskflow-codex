# Code review

Load only when `--review` is not `off`. The reviewer must be a different agent
from the implementer and must inspect the actual diff.

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
