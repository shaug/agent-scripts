# Connector-outcome curation and promotion

This directory operationalizes future learning from adjudicated connector review
outcomes: it turns a newly adjudicated connector finding into a versioned
curation record, and turns a group of curation records into a conservative,
evidence-backed promotion decision. It does not itself curate any real connector
history. See
[`../contracts/curation-record.schema.json`](../contracts/curation-record.schema.json)
and
[`../contracts/promotion-decision.schema.json`](../contracts/promotion-decision.schema.json)
for the normative schemas, and
[`../../scripts/evals/curation.py`](../../scripts/evals/curation.py) for the
loader and every cross-field rule the schema-subset validator cannot express.

This is infrastructure, proven with synthetic fixtures. It must never be used to
recreate or re-adjudicate the `baseline/v1/` corpus, and it never touches
`baseline/v1/` or `v2/`, which stay exactly as #58/#59 froze them.

## Layout

```text
review-suite/evals/curation/
├── README.md                      this file
├── records/<record_id>.json       one curation record per adjudicated claim
├── promotions/<decision_id>.json  one promotion decision per record group
└── fixtures/invalid/*.json        fixtures that must fail validation, read
                                   directly by tests rather than by the audit
                                   command's normal directory scan
```

`just audit-review-curation` loads and validates every record under `records/`,
then every promotion decision under `promotions/` against that loaded set. It
never scrapes GitHub, never mutates a review thread, and never launches a model.

## Adjudicate first

A curation record's `disposition` is the actual outcome of adjudication, never a
restatement of the connector's own claim. Eight dispositions validate
distinctly:

- `accepted_material_defect`, `accepted_acceptance_miss`,
  `accepted_validation_gap` - the claim was materially real. Each requires a
  private `expected_root_cause`, and only these may support a promotion
  decision's `positive_case_ids`.
- `rejected_false_positive`, `rejected_non_causal`, `deferred_hardening` - the
  claim was not material, or is deferred tuning evidence. Each requires a
  private `accepted_non_finding`, and only these may support
  `negative_control_case_ids`.
- `duplicate` - the claim restates another record's root cause. It requires
  `duplicate_of`, and can only be promoted if it also declares
  `distinct_contribution`: the genuinely distinct trigger, surface, or negative
  control that keeps it from double-counting the shared root cause. A plain
  duplicate with no distinct contribution can never appear in any promotion
  decision.
- `unresolved` - adjudication has not settled. An unresolved claim can never
  enter grading expectations or modify active review guidance; it can never
  appear in any promotion decision either.

`record_id` must equal its filename, and `duplicate_of` must reference another
record actually present in the same load.

## The mechanical disclosure guardrail

When a record's `public.provenance.source_class` is `private_authorized`, its
`source_description` must be one of the generic phrases in
[`../contracts/disclosure-guardrail.json`](../contracts/disclosure-guardrail.json)'s
`allowed_source_descriptions`, and validation fails closed if it contains a
path-like token (`/`), a bare hostname-shaped token, or any string matching that
file's `denylisted_identifiers`. `denylisted_identifiers` ships empty: this
repository's implementing tooling must never learn, guess, or record the
identity of any private, owner-authorized source, so no real identifier is
shipped here. The repository owner adds a real one directly, without a code
change, if a specific identifier ever needs guarding against.

`fixtures/invalid/disclosure-path-token.json`,
`fixtures/invalid/disclosure-bare-hostname.json`, and
`fixtures/invalid/disclosure-denylisted-identifier.json` each prove one of these
three failure modes fails closed; see
`review-suite/scripts/tests/test_eval_curation.py`.

## Reviewer/private separation and restricted data

A curation record keeps `public` and `private` in one file, because it is
reviewed by a human curator through an ordinary pull request rather than shipped
to an executor - but separation is still enforced:
`curation.reviewer_private_separation_errors` rejects a record whose private
text (retention authority, owner, source identity, expected root cause, accepted
non-finding) appears verbatim in its own public section.

Private code, secrets, customer data, hidden reasoning, and connector-only
metadata are forbidden everywhere in a curation record. Every object in the
schema sets `additionalProperties: false`, so there is no slot for any of those
categories of data to occupy in the first place;
`fixtures/invalid/restricted-data-forbidden-field.json` proves an attempt to add
one fails closed as an unknown property.

## Promotion workflow

1. **Adjudicate first.** An unresolved or plain-duplicate record cannot support
   a promotion decision (`curation._promotable_errors`).
2. **Add a regression case.** An accepted material outcome becomes a positive
   case; a rejected or deferred tuning outcome becomes a negative control. This
   directory never itself creates a `review-suite/evals/corpus/` or `strata/`
   case - that population step is separate, later, evidence-backed work.
3. **Measure before changing guidance.** Every promotion decision requires
   `evidence.before` and `evidence.after`: recall, false-positive rate,
   stability, latency, and either a reported cost or an explicit `unavailable`
   reason. This is required even for `no_promotion` and `corpus_case_only`,
   because the measurement is what justifies not changing guidance just as much
   as it justifies changing it.
4. **Choose the narrowest owner** (`decision`):
   - `global_rubric_update` - only for a repository-independent invariant.
     Requires at least two positive cases across distinct affected surfaces plus
     at least one negative control, and a `target.kind` of `global_rubric`.
   - `repository_instruction_update` - for a repository/path-local invariant.
     Requires `target.kind` of `repository_instruction`, and `target.path` must
     name an existing repository-owned instruction file (`AGENTS.md` or
     `CLAUDE.md`) - this workflow ships no new shared path-rule subsystem, with
     or without a target file existing yet.
   - `corpus_case_only` / `no_promotion` - when no reusable rule is justified.
     No `target` is permitted.
5. **Revalidate.** Out of scope for this tooling: a promoted change's actual
   preregistered target and non-regression gates are #59/#57's, not this
   directory's.

`records/` and `promotions/` here are worked synthetic examples proving every
rule above is real, tested, and fails closed - not real curated history.
