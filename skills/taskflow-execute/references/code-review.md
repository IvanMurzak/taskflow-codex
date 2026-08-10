# Code review — depths, gating, and the fix loop

This file is loaded by `taskflow-execute`'s orchestrator conditionally,
whenever `--review` is anything other than `off` (`--review=` accepts
`off · low · medium · high · xhigh`, default `off`). If you are reading this,
a review at one of the four non-`off` depths is about to happen, or is in
progress, for one task's diff.

This document is the **single home of the review rubric** for the whole
taskflow system: both execution tiers and **both host plugins** (Claude Code and
Codex) resolve "what does `--review=high` mean" by reading this file and only
this file. Nothing about depths, gating, or the fix loop is redefined anywhere
else — if you find a second definition, this one is authoritative.

**This file is therefore the least host-specific of the three modules**, and it
is meant to stay that way. Two paragraphs below are marked as Codex-specific —
the reviewer's dispatch mechanism, and the third of the three `effort`-shaped
vocabularies. Everything else is identical to the Claude plugin's copy on
purpose. A change to the rubric that lands in only one of the two is drift,
whichever side it lands on.

This file does not describe how workers are dispatched, how worktrees or
slots are created, how PRs are opened, or how merges happen. Those are
orchestration mechanics owned by a sibling reference file. Assume only that,
by the time review starts, a worker has produced a diff on its own branch and
a PR exists for it (or is about to).

## The four depths

Depth is requested once per run (`--review=<depth>`) and applies to every
reviewed task in that run. Each depth is **strictly additive** over the one
before it — `medium` does everything `low` does, plus more; `xhigh` does
everything `high` does, plus more. A reviewer at a given depth never skips the
lower tiers' checks to make room for its own.

| Depth | Scope |
|---|---|
| `low` | DoD conformance and obvious defects. Changed files only. One pass. |
| `medium` | Everything in `low`, plus: reuse, simplification, efficiency, whether the tests are actually meaningful (not just present), and adjacent call sites the diff affects. |
| `high` | Everything in `medium`, plus: adversarial correctness reasoning that goes beyond the diff as presented — edge cases the diff doesn't visibly handle, error paths, concurrency/race conditions. |
| `xhigh` | Everything in `high`, plus: independent multi-lens verification. The review is run through separate lenses — correctness, security, reproducibility — and each lens's findings are challenged (argued against, not just double-checked) before any of them is reported. |

Concretely:

- **`low`** is a conformance pass: does the diff satisfy its own Definition of
  Done, and does anything in it look obviously broken (typo-level bugs,
  missing null checks the code itself implies, a DoD item silently skipped)?
  It reads only the files the diff touches, once.
- **`medium`** adds a quality pass on top: could this be simpler, does it
  duplicate something that already exists elsewhere in the repo, is there an
  obvious efficiency problem, do the new/changed tests actually exercise the
  behavior they claim to (not just execute without asserting), and does
  anything just outside the diff — a caller, a sibling implementation — now
  disagree with it.
- **`high`** adds adversarial reasoning: reviewing as someone trying to break
  the change, not just read it. This means constructing edge cases the diff's
  own tests don't cover, tracing error paths to see where they actually go,
  and checking for concurrency hazards (races, non-atomic read-modify-write,
  ordering assumptions) even when the diff never mentions concurrency.
- **`xhigh`** adds structural rigor to the review process itself: instead of
  one reviewer producing one list of findings, the review runs multiple
  independent lenses (at minimum correctness, security, and reproducibility —
  "can this be reliably reproduced/verified by someone else, not just
  asserted"), and every finding from every lens is challenged — argued
  against on purpose — before it survives to be reported. A finding that
  cannot survive its own challenge is dropped rather than reported as noise.

## Gating is fixed by depth — not a flag

| Depth | Gating |
|---|---|
| `low` | advisory |
| `medium` | advisory |
| `high` | block |
| `xhigh` | block |

This mapping is **deliberately not configurable**. There is no flag, no
override, no per-task exception that turns a `high`/`xhigh` finding into
advisory-only, or a `low`/`medium` finding into a blocker. If you need
different gating, request a different `--review` depth — the depth itself is
the only lever.

- **Advisory** findings (from `low`/`medium`) never block a merge. They are
  recorded in the completion report and posted to the PR, and the run
  proceeds regardless of how many advisory findings exist.
- **Blocking** findings (from `high`/`xhigh`) must be resolved — via the fix
  loop below — before the row is allowed to proceed toward merge.

## The fix loop (K = 2, fixed)

When a `high`/`xhigh` review produces at least one blocking finding:

1. The finding returns to **the same worker** that produced the diff — not a
   fresh worker, not the reviewer. The same worker still holds its context
   and its slot from the original implementation, which is why it is the one
   asked to fix it rather than re-briefing someone new.
2. The worker addresses the finding and reports back.
3. **The reviewer re-reviews the fix.** A round does not close because the
   worker says it fixed something — it closes only when the reviewer verifies
   the fix against the actual diff. The worker's own assertion is never
   sufficient.
4. This can repeat for at most **K = 2 rounds**, also fixed and not
   configurable — there is no flag to raise or lower it.
5. If the finding is **still blocking after K rounds**, the row moves to
   `⛔` with the reason recorded. The slot is **preserved**, not torn
   down, so it can be inspected — and its path is recorded alongside the
   reason. This is the one case in the review flow where a failure to
   converge does not get silently retried further; it stops and surfaces for
   a human.

Advisory findings never enter this loop — there is nothing to fix before
proceeding, by definition of "advisory".

## The reviewer is never the implementer

The agent that reviews a diff is always a **different** agent from the one
that produced it, at every depth this file governs and in every tier. An
implementer reviewing its own diff is self-approval — it defeats the purpose
of having a review step at all, because the one perspective a reviewer exists
to add (an outside read of the change) is exactly the one a self-review
cannot supply. This holds through every round of the fix loop too: the
worker that applies a fix in round 2 is still not the one who verifies it in
round 2 — that is still the reviewer.

**Codex-specific — how that separation is actually obtained here.** The
orchestrator spawns a subagent whose `agent_type` is the `taskflow-reviewer`
role from the project's `.codex/agents/`, and it spawns it with
`fork_turns: "none"` so the reviewer receives its brief and not the
orchestrator's history. Two failure modes are worth naming because neither
announces itself:

- **A generic agent type is not a reviewer.** Spawning `default` and telling it
  to review carries neither the never-review-your-own-diff rule nor the
  never-implement rule. Once its output is posted to a pull request it is
  indistinguishable from a contract review, and it is not one. If the role file
  is unavailable, inline the reviewer's rules into its brief **and say in the run
  report that the role was absent** — do not silently substitute.
- **Re-using the implementer's agent is not a review**, even for a re-review in
  the fix loop, and even though it is the cheapest thing to do because that agent
  already has the context. That cheapness is precisely the self-approval this
  section forbids. Spawn a reviewer.

## Findings are posted, not left in the terminal

Every review's findings — from every depth — are **posted as a PR comment**.
They are not left in agent transcript or terminal scrollback, where nobody
but the person watching that one session would ever see them.

- **Blocking findings** (from `high`/`xhigh`) are posted and drive the fix
  loop above.
- **Advisory findings** (from `low`/`medium`) are posted to the PR *and*
  recorded in the run's completion report. They never block, but they are
  never silently dropped either — an owner reading either the PR or the
  final report sees the same list.

## Three `effort`-shaped vocabularies — do not confuse them

There are three separate places in this system where a value that looks like
"how hard should this try" appears, and they are **not the same thing**,
despite overlapping names. Getting this wrong looks like expecting a flag
that does not exist.

1. **The Pipeline CLI's `--effort` flag** (`pipeline plan --effort
   <step_id>=<level>`, and equivalents on `drive`/`next`/`step run`) accepts
   six values: `low | medium | high | xhigh | max | inherit`. This is the CLI's
   own general-purpose reasoning-effort control, usable on *any* pipeline
   step, not specific to review.
2. **This skill's `--review` flag** adopts only the **four-level subset** of
   that vocabulary — `off · low · medium · high · xhigh` — and is specific to
   the review step. **`max` and `inherit` are deliberately not exposed** on
   `--review`. There is no `--review=max` and there is no `--review=inherit`;
   requesting either is a usage error, not a lesser-known alias for something
   this document defines.
3. **The host's own reasoning-effort setting** is a **separate, unrelated**
   mechanism with some overlapping value names. On Codex it is the
   `reasoning_effort` argument of a spawn (paired with `model`, and settable
   only when `fork_turns` is `"none"` or a positive integer); on Claude Code it
   is the `effort` frontmatter field of an agent or skill definition. Either
   way it controls that agent's own reasoning as a host-level setting. It is
   not this skill's `--review` flag and does not get resolved through this
   file. Note the consequence on Codex specifically: a reviewer's
   `reasoning_effort` and its `--review` depth are two different dials, and
   raising one does not raise the other.

When this document, or `SKILL.md`, or a brief says "depth" or "`--review`",
it always means vocabulary #2. When the `pipeline` tier mapping below
mentions `--effort code-review=high`, that `--effort` is vocabulary #1's
flag, being handed one of the four values that #2 and #1 happen to share —
the two vocabularies are being *composed* there, not confused.

## Tier mapping — one rubric, two mechanisms

The depths and rules above are written **once, in this file**, and both
execution tiers implement the same meaning of "high" against it — they differ
only in *mechanism*, not in *rubric*.

- **`pipeline` tier.** `--review=<depth>` is translated to
  `--effort code-review=<depth>` and handed to the pipeline (e.g.
  `--review=high` becomes `--effort code-review=high`). The pipeline's own
  `code-review` step — a step distinct from whichever step implemented the
  task, satisfying the reviewer-is-not-implementer rule structurally — runs
  at that effort level. The depth's scope, its gating, and the fix loop all
  still apply; the pipeline's `implement → code-review → …` lifecycle is
  simply the mechanism that carries them out.
- **`toolkit` tier, and the sequential fallback.** The orchestrator itself
  spawns a separate **reviewer subagent** — never the task's implementer —
  against the worker's diff, instructed to review at the requested depth using
  the scope table above. This reviewer subagent is what posts findings to the
  PR and what re-reviews each round of the fix loop.

Because the rubric lives here rather than being redefined per tier, a `high`
review means the same set of checks whether it runs as a pipeline step or as
a dispatched subagent — and whether it runs on Codex or on Claude Code.

## `--review=off` and the `pipeline` tier (recorded safe default)

There is one asymmetry worth stating plainly, because it is easy to assume
`--review=off` means "no review step runs anywhere" — it does not, in one
tier.

In the `pipeline` tier, the `implement-task` pipeline declares its
`code-review` step **unconditionally** — the step exists in the pipeline
regardless of what `--review` was passed. Consequently:

- **`--review=off` keeps the `code-review` step** when running under the
  `pipeline` tier. The pipeline still reviews the diff; `off` does not
  suppress it.
- **`off` only suppresses review in the `toolkit` tier and the sequential
  fallback** — there, `off` means the orchestrator does not spawn a reviewer
  subagent at all, and this file is not even loaded (per the loading condition
  stated at the top: `--review != off`).

This is the recorded safe default for this open question, not a workaround —
if you are ever unsure whether a `pipeline`-tier run reviewed a task despite
`--review=off`, the answer is yes, because the step's presence in that
pipeline does not depend on this flag.
