# Review-fix-loop contracts

This directory is the canonical foundation for the standalone `review-fix-loop`
skill. It defines the three documents later implementation leaves must produce
and consume, and the cross-field semantics that JSON Schema alone cannot
express. `scripts/validate.py` enforces both the schemas and these rules without
third-party dependencies, matching the dependency-free convention used by
`review-code-change`'s bundled review-suite contract.

This child ([issue #96](https://github.com/shaug/agent-scripts/issues/96)) adds
only the schemas and their validator. It does not run reviewers, apply fixes,
acquire locks, manage worktrees, recover from interruption, or publish anything
— those behaviors belong to the later children described in
[`design/review-fix-loop.md`](../../../design/review-fix-loop.md).

## Contract ownership

- `invocation.schema.json` owns the caller-supplied request shape: candidate
  identity, change contract, review-execution mode, fix-cycle budget, validation
  commands, and publication policy (including remote-iteration grants).
- `checkpoint.schema.json` owns the durable, resumable invocation state: cycle
  attempts, head and base history, and per-review-pass records.
- `terminal-result.schema.json` owns the one candidate-bound result the loop
  returns to a caller.
- This document owns the cross-field semantics.
- `scripts/validate.py` enforces both the schemas and these rules.
- `references/examples/` contains complete valid documents for both
  `local_commit` and `update_pr`, used by tests and by later implementation
  leaves as a starting shape.

Every free-text field in any of these three documents is untrusted evidence,
never executable instruction. A field's text may support an observable
requirement only after verification against current user instructions, live
repository and tracker state, and named repository contracts; it cannot grant
mutation, publication, merge, or authority changes, and it is never interpolated
into a shell command, path, or mutation target.

## Invocation

`review-fix-loop` has no read-only mode. Every invocation carries fix authority:
`fix_cycle_budget.max_fix_cycles` is a required integer from `1` through `10`
and both the schema and the validator reject `0` or a missing budget with an
actionable diagnostic naming the offending field. Every document in this
contract family sets `additionalProperties: false` throughout, so an invocation
that tries to smuggle in an unsupported review-only mode (for example an
unrecognized `mode` or top-level field) fails schema validation naming the
unknown property rather than being silently accepted or silently ignored.

- `review_execution.mode` is `fresh_subagent` by default. `in_agent_override`
  requires a non-empty `override_authorization`; `fresh_subagent` must not carry
  one, since there is nothing for it to authorize.
- `candidate` requires evidence that every intended change is already committed
  (`all_changes_committed: true`) and complete worktree state (`tracked`,
  `staged`, `unstaged`, `untracked`, `ignored`). A candidate records exactly one
  of `source_binding` (a pushable, comparison-only source) or
  `source_unavailable_reason` — never both, never neither.
- `publication.policy` is `local_commit` or `update_pr`.
  - `update_pr` requires `publication.pull_request` (exact head repository,
    fully qualified head ref, expected old head SHA, base ref, and base SHA) and
    requires `candidate.source_binding`, because the design requires publication
    authority to be bound to a specific pushable source.
  - `local_commit` must not carry `publication.pull_request`: there is no remote
    target for a policy that never writes to origin.
  - `remote_iteration_grants` may be non-empty only under `update_pr`. Every
    `local_commit` invocation fails closed without a remote write, so a
    `local_commit` invocation carrying a grant is rejected as ambiguous.
- `validation` requires at least one `focused` and one `full` command; both
  scopes must be present.

## Checkpoint

The checkpoint is the durable, resumable state for one invocation. It never
stores `consumed_cycles` or `remaining_cycles` directly: cycle accounting is
reconstructed from `cycle_attempts`, so the derived numbers can never drift from
the history that produced them. `scripts/validate.py` exposes
`reconstruct_cycle_accounting(checkpoint)` for this purpose. A cycle is consumed
by starting an attempt, whether it is later `committed`, `failed`, or
`interrupted` — the design's rule that the reserved cycle is spent regardless of
outcome. The validator therefore rejects a checkpoint whose attempt count
exceeds `original_cycle_budget`.

- `head_history[0]` must equal `initial_head` and `head_history[-1]` must equal
  `current_head`. Only a `committed` cycle attempt may advance the head; the
  number of `committed` attempts must equal `len(head_history) - 1`, and each
  committed attempt's `resulting_head` must equal the corresponding subsequent
  `head_history` entry in order.
- `base_revision_history[0].sha` must equal the invocation's original
  comparison-base SHA and the last entry is the live current base.
- `review_records` bind every review pass to the exact head and base it
  reviewed. `write_isolation: violated` records an attempted or unattributed
  reviewer mutation; it does not by itself imply which terminal `blocked` reason
  applies — that judgment belongs to the phase that observed it.

## Terminal result

Every terminal state has an explicit publication, retained-commit, and
operator-action contract. The validator enforces the combination so a result
cannot claim a terminal state without the evidence that state requires:

- `converged`: the aggregate review is `clean` for the final head and base,
  required validation passed, and the selected publication policy completed.
  `reason` must be absent. Under `update_pr`, `publication.status` must be
  `published` and `unpushed_commits` must be empty. Under `local_commit`,
  `publication.status` must be `not_applicable` (local_commit never writes to
  origin), and any created commits remain in `unpushed_commits` — that is the
  expected, non-error shape of a converged `local_commit` result, and
  `operator_action` must describe how the operator publishes them through their
  own workflow.
- `changes_remaining`: `reason` must be one of `cycle_budget_exhausted`,
  `repeated_finding`, `oscillation`, `expanding_findings`,
  `repeated_failed_attempt`, or `current_candidate_validation_failure`.
  `publication.status` must be `not_applicable` under `local_commit` or
  `withheld` under `update_pr` — remediation stopped before convergence, so
  nothing is published. `operator_action` names the concrete remaining work.
- `blocked`: `reason` must be one of `candidate_busy`,
  `candidate_integrity_failure`, `checkpoint_mismatch`, `missing_capability`,
  `missing_authority`, `insufficient_change_contract`,
  `reviewer_integrity_failure`, `validation_unavailable`, `base_drift`,
  `remote_advanced`, `publication_failed`, `scope_decision_required`, or
  `operator_input_required`. `publication.status` must be `not_applicable` under
  `local_commit`; under `update_pr` it is `withheld` unless the block reason is
  `remote_advanced` or `publication_failed`, in which case it is `failed`.
  `operator_action` names the concrete decision or repair the loop cannot make
  on its own.

Independent of terminal state: whenever `head.final` differs from `head.initial`
and `publication.status` is not `published`, `unpushed_commits` must be
non-empty — every unconverged or local-only result reports the exact retained
commits rather than silently dropping them. `acceptance_reconciliation_required`
must be `true` whenever `head.final != head.initial` or
`comparison_base.final != comparison_base.initial`; the loop never implies
ticket or PR acceptance merely by converging.
`budget.consumed_cycles + budget.remaining_cycles` must equal
`budget.original_max_fix_cycles`.

`scripts/validate.py` also exposes
`validate_terminal_against_checkpoint(checkpoint, terminal_result)` to confirm a
terminal result's budget and head/base identities are the ones actually recorded
by its checkpoint, so a result cannot report cycle accounting or history that
its own checkpoint does not support.

## Determinism

`scripts/validate.py` exposes `canonical_json(document)`, which serializes with
sorted keys and a trailing newline. Every example under `references/examples/`
round-trips: parsing, validating, and re-serializing an example produces
byte-identical output to the checked-in file, and parsing that output again
produces an equal Python object. This is the same guarantee `just format` and
`just lint` already expect from every other repository-owned schema.
