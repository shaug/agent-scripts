# Verification-sufficiency pass removal (#93)

This records the repository owner's removal decision for the verification-
sufficiency pass and its mandatory `verification_sufficiency_evidence` schema
field, both added by #52/#53, and the evidentiary basis the owner approved it
against on 2026-07-29. It does not modify `S1-ABLATION-MATRIX.md`,
`discriminating-case-validation.md`, `FROZEN-V2-CONFIGURATION.md`,
`CLOSEOUT-REPORT.md`, `gate-manifest.json`, `DECISION-RECORD.md`,
`FAILURE-TAXONOMY.md`, `audits/`, or `review-suite/evals/baseline/v1/` - all
remain exactly as prior tickets delivered them. This is the sole new file this
ticket adds under `review-suite/evals/v2/`.

## Decision

Remove the verification-sufficiency pass from
`skills/review-correctness/ SKILL.md` and remove
`verification_sufficiency_evidence` entirely from the shared review-result
contract, advancing `schema_version` `1.3 -> 1.4`. The traversal
(consumer/impact) pass and `consumer_impact_evidence` are unchanged,
byte-for-byte, from their #52/#53-shipped state - they are not in scope for this
decision and were not touched by this ticket.

**Full removal, not an optional non-gating field.** #93's body states full
removal is preferred unless a concrete reason favors keeping an optional,
non-gating field. No such reason exists here: the field never had demonstrated
value (below), and it carried a confirmed, twice-reproduced cost. Retaining it
as optional would keep exactly the mechanism responsible for that regression
available for a reviewer to invoke, for no offsetting benefit ever measured in
this corpus.

## Evidentiary basis

Two independent, honestly-sourced measurements found no demonstrated value for
this pass:

- **`stale-claim-release-guard`** (the original justifying case, #53's own
  target): `S1-ABLATION-MATRIX.md`'s target-case gate table shows
  `mean_recall 0.0`, `combined 1.0` -> **PASS** identically across all three
  configurations (both passes together, traversal-only, verification-only). The
  case resolves whether or not the verification-sufficiency pass runs at all -
  its own "Settled verdict per mechanism" table states this plainly: "**No** -
  case also passes with this pass disabled."
- **`audit-log-flush-keyword-probe`** (a new, deliberately harder case sourced
  specifically to test this, #89): `discriminating-case-validation.md`'s
  per-case results show `mean_combined_recall 1.0` in both the "both passes
  together" and "traversal-only" (verification-sufficiency disabled)
  configurations, 5 runs each, zero false positives or evaluation failures
  either way. Its own conclusion: "This candidate does not discriminate, even
  after a genuine, disguised-mock construction and a full validation pass."

On top of the absence of demonstrated value, the pass carries a confirmed,
twice-reproduced cost: `S1-ABLATION-MATRIX.md`'s non-regression floor table
shows `session-continuation-summary` - a previously clean control with
`expected_root_cause_ids: []` - regressing to **3/5 false positives** under the
verification-only configuration (traversal pass disabled), a result
independently reconfirmed in `session-continuation-summary-confirming-rerun.md`.
No comparable regression appears under traversal-only, and none appears in the
"both passes together" (as-shipped) configuration - so this is evidence against
running the verification-sufficiency pass *in isolation*, not evidence against
whatever the already-shipped combined configuration produced.

`discriminating-case-validation.md`'s own summary states the resulting position
directly: "the evidentiary case for this specific pass, as currently instructed,
is weaker after this validation than before it - a candidate built to be more
likely to need it did not need it." Both documents explicitly defer the
keep/remove decision itself to the repository owner; this record reflects that
the owner made it, approving removal on 2026-07-29.

By contrast, and precisely because this decision must not blur the two
mechanisms together: the traversal pass **does** have demonstrated value in the
same body of evidence. `discriminating-case-validation.md` reports
`artifact-promotion-environment-shortcut` at `mean_combined_recall` 1.0 with the
traversal pass enabled vs. 0.4 disabled - a real, reproducible gap, "the first
evidence anywhere in this epic that the traversal (consumer/impact) pass changes
reviewer behavior on a case built to need it." That pass and its
`consumer_impact_evidence` schema field are unaffected by this removal.

## What changed

- `skills/review-correctness/SKILL.md`: removed the verification-sufficiency
  pass instruction and its result-field requirement. The underlying correctness
  question - whether a claimed test actually exercises the triggering condition
  a risky change addresses, rather than merely passing - remains part of
  ordinary correctness review (see "Review in priority order" item 6), just
  without a separately mandated pass or required evidence field. The traversal
  pass instruction is preserved exactly as shipped.
- `review-suite/contracts/review-result.schema.json`: `schema_version`
  `1.3 -> 1.4`; the `verification_sufficiency_evidence` property is removed from
  the schema entirely (not merely made optional - it was already optional at the
  top level; the removal eliminates the property and its dedicated cross-field
  validation).
- `review-suite/scripts/validate.py`: removed
  `_check_verification_sufficiency_evidence` and its call site; extended
  `STALE_RESULT_SCHEMA_VERSIONS` so a `1.3` result is rejected with a clear
  migration-to-`1.4` error rather than silently accepted or misread.
- `review-suite/CONTRACT.md`: removed the "Verification-sufficiency evidence"
  section. The "Consumer/impact evidence" section is unchanged.
- Canonical fixtures (`review-suite/fixtures/*/expected.json`): migrated
  `schema_version` `1.3 -> 1.4` across every fixture. The
  `verification-sufficiency-guard` fixture, whose entire purpose was exercising
  the removed field's `clean`-pairing behavior, was retired (removed from
  `review-suite/fixtures/manifest.json` and deleted) rather than adapted, since
  nothing about its schema-conformance purpose survives the field's removal.
- `review-suite/scripts/tests/test_contracts.py`: removed
  `VerificationSufficiencyEvidenceTests`; added a test proving the field is no
  longer part of the schema and is rejected as an unknown property, and added
  `test_stale_v1_3_aggregate_result_is_rejected_with_a_useful_error` alongside
  the existing `1.0`/`1.1`/`1.2` stale-version regression tests.
- `skills/review-correctness/evals/standalone-verification-sufficiency-gap/` and
  its expected result: **adapted, not deleted**, per #93's own instruction. Its
  diff and ticket describe a genuine correctness defect pattern (a claimed test
  that exercises an already-safe branch instead of the actual owner-absent
  triggering condition) independent of the removed mechanism -
  `review-suite/fixtures/missing-test/` already demonstrates that ordinary
  correctness review catches an analogous insufficient-test-coverage gap without
  any dedicated pass or evidence field. The expected result keeps its
  `changes_required` verdict and blocking finding; only
  `verification_sufficiency_evidence` and the stale `schema_version` were
  removed/migrated.
- Every other schema-`1.3` expected result across the bundled review skills
  (`review-code-change`, `review-code-simplicity`,
  `review-solution- simplicity`, `babysit-pr`, `implement-ticket`, in addition
  to `review-correctness`) and the shared eval/protocol test harnesses were
  migrated to `1.4` atomically, since `schema_version` is one contract shared
  across every lens and caller.
- `just sync-contracts` was run after every canonical edit so all six bundled
  `references/review-suite/` copies (and, for `implement-ticket`/`babysit-pr`,
  `scripts/review_gate.py` and its test) stay byte-identical to the canonical
  source.

## What did not change

- The consumer/impact-traversal pass instruction in
  `skills/review-correctness/SKILL.md`.
- `consumer_impact_evidence` anywhere in the schema, `CONTRACT.md`, or
  `validate.py`.
- The `stale-claim-release-guard` and `audit-log-flush-keyword-probe` corpus
  cases in `review-suite/evals/strata/s1-correctness-orchestrator/` - both
  remain in the corpus as general correctness cases; only the requirement that a
  `clean` verdict include `verification_sufficiency_evidence` is gone.
- `review-suite/evals/baseline/v1/`, `gate-manifest.json`, `DECISION-RECORD.md`,
  `FAILURE-TAXONOMY.md`, `audits/`, and every existing `review-suite/evals/v2/`
  measurement document, including the ablation skill-root snapshots under
  `ablation-skill-roots/` used to reproduce the measurements cited above.
