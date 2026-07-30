# Reviewer isolation and complete-review orchestration

This document implements
[`design/review-fix-loop.md`](../../../design/review-fix-loop.md)'s "Review
execution" and "Reviewer write prevention" sections (under "Invocation
contract") and workflow step 3 ("Review"), for the executing agent that follows
[`SKILL.md`](../SKILL.md). It does not define locking, isolated attempts,
worktree management, or publication — those belong to the sibling children this
document links to below. It also does not define the "Decide" (step 4) or "Fix"
(step 5) workflow steps: choosing which finding to accept, reject, or defer, and
applying the resulting edit, remain a later child's responsibility (see design's
"Compatibility and rollout").

Load [`scripts/reviewer_orchestration.py`](../scripts/reviewer_orchestration.py)
for the deterministic decisions and data transformations this document
describes; it is dependency-free like every other script in this skill, and its
docstrings cross-reference the specific acceptance criterion or design
requirement each function satisfies.

## Lens resolution

`review-fix-loop` has no selectable lens subset. The complete repository review
suite — `review-code-change`, which in turn sequences
`review-solution-simplicity`, `review-correctness`, and `review-code-simplicity`
— is the sole initial review mode for every cycle. Do not invoke an individual
lens directly, and do not accept an invocation field that tries to request a
narrower set; the invocation schema has none, and
`scripts/reviewer_orchestration.py`'s `resolve_review_lenses()` returns this
fixed set from the same constant the bundled review-suite contract uses to
enforce it (`REQUIRED_AGGREGATE_LENSES`), so no caller or test hand-copies the
three lens names and risks drifting from the contract that actually enforces
them.

"Resolving" a review therefore means: confirm `review-code-change` and its three
lens skills are available (fail closed per its own `SKILL.md` if not), and
require every review pass's result to demonstrate it actually covered all three
— see "Rejecting an incomplete result" below.

## Review execution

The default execution mode is `fresh_subagent`. Every review pass:

1. **Creates a new aggregate-review context.** In a runtime that supports
   subagents (for example Claude Code's Agent/Task tool), spawn one new subagent
   scoped to this pass only. Never reuse a subagent from a prior pass, and never
   reuse the implementation/mutation context itself as the reviewer.
2. **Supplies only raw evidence.** Build the shared review-code-change packet
   (goal, acceptance criteria, non-goals, preserved behaviors, sources,
   candidate diff, worktree state, and exact focused/full validation evidence)
   bound to the exact current head and comparison base. Withhold the
   implementation transcript, the intended fix, prior conclusions, suspected
   findings, and the expected result.
3. **Grants no mutation authority.** The reviewer subagent's tool surface must
   exclude file-editing, commit, push, communication, merge, and
   tracker-mutation tools. In Claude Code, restrict it to
   `Read, Grep, Glob, Bash, Agent, Task, Skill` — the same tool set
   `review-code-change` itself declares — never `Edit`, `Write`, `NotebookEdit`,
   or any tool capable of a remote write.
4. **Discards the reviewer context after the result.** Do not carry a reviewer
   subagent's working notes, intermediate reasoning, or session state into the
   next pass or into the fix cycle that follows.

`review-code-change` runs its own complete lens sequence
(`review-solution-simplicity`, `review-correctness`, `review-code-simplicity`)
inside that one aggregate-review subagent. Those nested lens invocations may
share the aggregate-review subagent's context — `review-fix-loop` does not spawn
a second subagent per lens itself, and this sharing does not weaken
completeness: `review-code-change`'s own aggregate `clean` verdict still
requires a fresh, current-head, `clean` execution from each of the three lenses
(enforced independently by the bundled contract's
`_check_aggregate_clean_lens_executions`, which `evaluate_review_result` below
reuses). Sharing a context changes *where* the lenses run, not whether each one
actually ran fresh against the exact candidate.

### The explicit in-agent override

`in_agent_override` runs the same complete aggregate review in the
implementation agent's own context instead of a fresh subagent. Use it only when
the invocation carries a non-empty `review_execution.override_authorization`
(already required by `validate_invocation`); there is no automatic fallback.

- Call
  `resolve_review_execution_mode(mode, override_authorization=..., host_supports_fresh_subagent=...)`
  to resolve what this specific host and invocation actually grant. An explicit
  override is honored regardless of whether the host could have run
  `fresh_subagent` — the override does not require the fresh path to be
  unavailable first.
- When `mode` is `fresh_subagent` and the host cannot spawn an isolated context,
  `resolve_review_execution_mode` returns
  `blocked_reason: "missing_capability"`. Return `blocked/missing_capability`;
  never silently run in-agent instead.
- Record the resolved `independence` (`fresh_subagent` or `in_agent_override`)
  in every `review_records` entry's `review_independence` field — this is what
  makes "in-agent execution occurs only when explicitly requested and is
  recorded in the result" true in the actual checkpoint/terminal-result
  documents, not just in this document's prose.

## Reviewer write prevention

"Read-only" is a capability boundary, not merely prompt language. Apply every
tier the runtime supports, strongest first:

1. **Immutable snapshot or deny-write filesystem boundary**, when the runtime
   can provide one.
2. **A restricted reviewer tool surface** without edit, patch, file-write,
   commit, push, or remote-write operations (see "Review execution" step 3
   above).
3. **Read-only inspection commands only** inside the reviewer context —
   validation and diagnostic commands the invocation already recorded, never an
   ad hoc write.
4. **Before/after state capture**: snapshot HEAD, refs, index, and
   tracked/staged/unstaged/untracked/ignored worktree state immediately before
   spawning the reviewer and immediately after it returns. Pass both snapshots
   to `detect_worktree_mutation(before, after)`.
5. **Tool-trace inspection**, when the runtime exposes one, for an attempted
   mutation that a capability boundary already blocked.

Certification requires enforced write isolation; before/after verification alone
is not sufficient by itself — it is tier 4 of five, not a replacement for tiers
1–3 where the runtime supports them.

An attempted prohibited mutation invalidates the review even when the runtime
blocked it. Feed every mutation description `detect_worktree_mutation` returns
(plus any tool-trace evidence) into `build_review_record`'s `mutation_attempts`.
A non-empty `mutation_attempts` always sets `write_isolation: "violated"`,
regardless of the aggregate verdict, and `scripts/validate.py`'s
`_check_converged_requires_clean_evidence` already rejects `converged` for *any*
`review_records` entry with a non-empty `mutation_attempts` — not only the
final-head-bound one. An unattributed remote-ref advance by itself is not proof
of reviewer misconduct; that is the ordinary `remote_advanced` publication-race
contract (issue #97/#100's scope), not a reviewer-integrity failure.

### The reviewer briefing

Call
`build_reviewer_briefing(independence=..., head_sha=..., comparison_base_sha=...)`
and prepend its return value to the raw evidence handed to the reviewer context,
before the review-code-change invocation itself. It states the exact execution
context, the exact candidate, and the literal prohibitions
(`REVIEWER_PROHIBITIONS`): report findings only; never stage, commit, amend,
rebase, or push any ref; never run a tool or command that writes to the working
tree, index, or any ref; never resolve conflicts, run formatters or codemods, or
apply any proposed fix, including one the reviewer itself proposes. This is the
acceptance criterion "Reviewer instructions explicitly prohibit worktree
mutation and implementation" made literal: the same wording travels with every
review pass instead of living only in this document.

## Rejecting an incomplete result

The acceptance criterion "Reviewer output is rejected if required lenses or
evidence are incomplete" has two distinct halves, and one function each:

- **Lenses**: `evaluate_review_result(result, expected_head, expected_base)`
  validates the raw result alone. An empty return means it is schema-valid,
  cross-field consistent, and bound to the exact head and comparison base this
  cycle captured — including every `lens_executions` entry, not only the
  result's own `candidate`.
  - A `clean` verdict must demonstrate a fresh, current-head, `clean` execution
    for all three required lenses; a result missing one, reusing a stale head,
    or reusing an old base is rejected, not silently treated as complete.
  - A `changes_required` verdict is not required to carry all three lens
    executions: the orchestration protocol stops at the first gating finding, so
    a partial `lens_executions` list there is expected and valid.
  - A `blocked` verdict may omit candidate identity entirely when the caller
    could not establish it; this is not treated as a stale-candidate mismatch.
- **Evidence**:
  `evaluate_review_pair(packet, result, expected_head, expected_base)`
  additionally validates the raw evidence packet review-fix-loop actually handed
  to the reviewer against its result. A single-document check on the result
  alone cannot see this: the shared review-suite contract's "validation must
  back a clean verdict" rule (`_check_clean_requires_passing_validation`) needs
  the packet's own `validation` array, which only `evaluate_review_pair`
  inspects. Prefer this over `evaluate_review_result` whenever the packet is
  still available — which it always is immediately after building it for the
  reviewer.

Treat any non-empty return from either function as a failed review pass: do not
build a `review_records` entry from it. `build_review_record` enforces this
directly — it raises `ReviewIntegrityError` instead of returning a partially
trusted record.

## Building the review record

Once a raw result (and, when available, its packet) passes evaluation, call:

```python
build_review_record(
    sequence=<next cycle_attempts/review sequence number>,
    result=<raw review-code-change aggregate result>,
    expected_head=<exact current head SHA>,
    expected_base=<exact current comparison-base SHA>,
    independence=<"fresh_subagent" or "in_agent_override">,
    reviewer_identity=<generate_reviewer_identity(independence, sequence)>,
    mutation_attempts=<detect_worktree_mutation(before, after) + any tool-trace evidence>,
    packet=<the exact packet handed to the reviewer, when retained>,
)
```

Passing `packet` runs `evaluate_review_pair`; omitting it falls back to
`evaluate_review_result` alone, which cannot catch a `clean` verdict paired with
a packet whose own required validation entry was actually `failed` or
`unavailable`. Always pass it when the packet is still available.

The returned dict matches `checkpoint.schema.json`'s `review_records` item
exactly — append it to the checkpoint's `review_records` array (and, at return
time, the terminal result's own `review_records`). It leaves
`finding_dispositions` empty: disposing a finding as `accepted`, `rejected`, or
`deferred` is workflow step 4 ("Decide"), which this document and its script do
not implement. Populate that field only once a later child (or caller) actually
runs Decide for this exact head/base pair.

## Normalizing findings for deterministic selection

`review-code-change` does not guarantee any particular ordering of findings
across lenses or review passes. Call `normalize_findings(result["findings"])` to
get one deterministic order — sorted by severity (`blocking` before
`strong_recommendation` before `defer`), then lens, then stable finding `id` —
regardless of the input order the raw result happened to produce. This is what
makes finding-to-fix linkage and checkpoint replay reproducible given
byte-identical review evidence, instead of depending on incidental lens or
dict-insertion order.

`select_next_finding(result["findings"])` returns the one finding a fix cycle
would target next: the first gating (`blocking` or `strong_recommendation`)
entry of that canonical order, or `None` when only `defer` findings remain.
Selecting a finding is not disposing or fixing it; a later child's Decide step
still verifies the selected finding's evidence against the candidate, confirms
it is within `change_contract.allowed_remediation_scope`, and only then accepts,
rejects, or defers it.

## Related documents

- [`design/review-fix-loop.md`](../../../design/review-fix-loop.md) — the
  authoritative design this document implements a slice of.
- [`references/CONTRACT.md`](CONTRACT.md) — the invocation, checkpoint, and
  terminal-result schemas' cross-field semantics `build_review_record`'s output
  must satisfy.
- [`skills/review-code-change/references/orchestration-protocol.md`](../../review-code-change/references/orchestration-protocol.md)
  — the lens sequencing and aggregation this document's "aggregate-review
  subagent" invokes; this document does not redefine or duplicate it.
