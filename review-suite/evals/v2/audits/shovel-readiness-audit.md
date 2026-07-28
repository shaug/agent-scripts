# Shovel-readiness audit

Run against the live, revised bodies of every retained child (`#51`, `#52`,
`#53`, `#56`) after the approved edits. Requirement (#59's own text): every
actionable/retained child has a settled observable outcome, change surface,
compatibility/failure behavior, positive and negative tests, validation, and
non-goals, plus a one-PR boundary. Independent of `scope-completeness-audit.md`
and `dependency-sequencing-audit.md`. Deferred children (#54, #55, #57) are
excluded from this requirement by design — their own gate condition is
explicitly not yet satisfied, so they are not expected to be shovel-ready yet,
and #59's own acceptance criteria only require provisional markers to be removed
"before they become unblocked," not before this ticket closes.

## #51 — Make clean verdicts require passing validation and current-head lens evidence

| requirement                    | present? | evidence                                                                                                                      |
| ------------------------------ | -------- | ----------------------------------------------------------------------------------------------------------------------------- |
| settled observable outcome     | yes      | `clean` impossible without passing validation + fresh 3-lens evidence for the exact candidate                                 |
| change surface                 | yes      | contracts, `validate.py`, `CONTRACT.md`, `review-code-change/SKILL.md`, orchestration cases, bundled copies, README/CHANGELOG |
| compatibility/failure behavior | yes      | schema `1.0 → 1.1`, additive, atomic migration via `just sync-contracts`, stale v1.0 rejected with a clear error              |
| positive and negative tests    | yes      | 11 enumerated regression cases covering every required behavior and every stale/invalid input                                 |
| validation                     | yes      | `just format`, `just lint`, `just test`; non-regression requirement that the 15 frozen v1 cases replay byte-identically       |
| non-goals                      | yes      | explicit list (no coverage ledgers, no new lenses, no selective-reuse exception, no caller changes)                           |
| one-PR boundary                | yes      | single schema/validator/orchestration change with a bounded fixture set; no architectural fan-out                             |

**Shovel-ready.**

## #52 — Evaluate compact review coverage, impact, and risk evidence (narrowed)

| requirement                    | present? | evidence                                                                                                                                                  |
| ------------------------------ | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| settled observable outcome     | yes      | one additive `consumer_impact_evidence` array + validator non-emptiness rule, scoped to consumer/impact traversal only                                    |
| change surface                 | yes      | `review-result.schema.json`, `validate.py`, `CONTRACT.md`, fixtures, bundled copies, README/CHANGELOG                                                     |
| compatibility/failure behavior | yes      | schema `1.1 → 1.2`, additive, atomic migration, stale-1.1-only aggregate fails with a useful error                                                        |
| positive and negative tests    | yes      | 5 enumerated fixtures covering the sibling-call-site case, the omission case, the no-other-consumers case, and its own negative (missing search evidence) |
| validation                     | yes      | `just format`, `just lint`, `just test`                                                                                                                   |
| non-goals                      | yes      | explicit list, including the dropped changed-surface ledger, acceptance trace, and risk profile named directly                                            |
| one-PR boundary                | yes      | this is now a single small schema addition — smaller in scope than #51, clearly one-PR-sized                                                              |

**Shovel-ready.** This is the child the scope/completeness audit found
cross-referenced by a now-corrected stale line in #56; that correction did not
require any change to #52's own body.

## #53 — Evaluate correctness traversal and verification sufficiency (specialist routing dropped)

| requirement                    | present?         | evidence                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| ------------------------------ | ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| settled observable outcome     | yes              | exactly two required passes (traversal, verification-sufficiency); specialist routing named as explicitly absent                                                                                                                                                                                                                                                                                                                                                     |
| change surface                 | yes              | `skills/review-correctness/SKILL.md` and references, `review-result.schema.json`, `validate.py`, `CONTRACT.md`, fixtures, bundled copies                                                                                                                                                                                                                                                                                                                             |
| compatibility/failure behavior | yes              | schema `1.2 → 1.3`, additive, atomic migration                                                                                                                                                                                                                                                                                                                                                                                                                       |
| positive and negative tests    | yes              | two fixture pairs directly shaped from the two confident-miss baseline cases, each with a positive and negative variant, plus a non-regression check on clean controls and rejected connector findings                                                                                                                                                                                                                                                               |
| validation                     | yes              | `just format`, `just lint`, `just test`                                                                                                                                                                                                                                                                                                                                                                                                                              |
| non-goals                      | yes              | explicit list, including "no specialist module of any kind," directly traceable to the dropped mechanism                                                                                                                                                                                                                                                                                                                                                             |
| one-PR boundary                | yes, with a note | this ticket lands two passes plus one schema bump in one PR — larger than #51/#52 but still a single coherent skill-prompt-plus-schema change, not a fan-out across multiple skills or subsystems. If implementation reveals it is materially larger than predicted, the standard `implement-ticket` size gate and `carve-changesets` remain available as the existing safety valve; no change to this ticket's own scope is needed to accommodate that possibility. |

**Shovel-ready**, with the one-PR-boundary note above recorded rather than
silently assumed.

## #56 — Operationalize adjudicated connector outcomes as review regressions

| requirement                    | present?         | evidence                                                                                                                                                                                                                                                                                                                       |
| ------------------------------ | ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| settled observable outcome     | yes              | intake/curation workflow, promotion steps, and the new mechanical disclosure guardrail                                                                                                                                                                                                                                         |
| change surface                 | yes              | corpus-compatible intake schema/validator, fixtures including the new guardrail fixture, docs, README/CHANGELOG                                                                                                                                                                                                                |
| compatibility/failure behavior | yes              | fail-closed intake validation for every disposition class, including the new source-description guardrail                                                                                                                                                                                                                      |
| positive and negative tests    | yes              | full disposition matrix (accepted/rejected/deferred/duplicate/unresolved/restricted-data/promotion-decision) plus the new disallowed-`source_description` negative fixture                                                                                                                                                     |
| validation                     | yes              | `just format`, `just lint`, `just test`                                                                                                                                                                                                                                                                                        |
| non-goals                      | yes              | explicit list, extended with "populate, rescore, or otherwise touch #58's frozen v1 baseline or its `connector-escape` stratum entry"                                                                                                                                                                                          |
| one-PR boundary                | yes, with a note | this ticket's surface (intake schema, validator, six-plus fixture classes, documentation) was already the largest of the four retained children before this ticket's edits, and the one small guardrail addition here does not materially change that. Same safety valve as #53 applies if implementation proves it oversized. |

**Shovel-ready**, with the same one-PR-boundary note as #53.

Also confirmed: the disclosure boundary itself (never name the source
repository) is stated as an acceptance criterion ("The source repository named
in "Definition status" above is never written into any commit, code comment, or
generated artifact by this ticket's own tooling or tests"), not left as prose
alone — this makes the hard constraint independently checkable by whoever
implements and reviews #56, rather than resting on discipline only.

## Result

**Clean pass, no material findings.** All four retained children (#51, #52, #53,
#56) have a settled observable outcome, an explicit change surface, stated
compatibility/failure behavior, enumerated positive and negative tests, a
validation gate, explicit non-goals, and a plausible one-PR boundary (two of the
four carry an explicit note about that boundary rather than an unstated
assumption, which is itself the point of running this audit as its own pass).
The three deferred children (#54, #55, #57) are correctly excluded from this
requirement, consistent with #59's own text that provisional markers persist on
children that do not become unblocked in this round.
