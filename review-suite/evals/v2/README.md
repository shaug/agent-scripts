# v2 planning record

This directory is the planning/definition gate #59 produces. It changes no
review prompt, schema, rubric, orchestration, or caller runtime behavior by
itself — it interprets the frozen `../baseline/v1/` record and turns it into an
implementation-ready decision for #51–#57.

- [`FAILURE-TAXONOMY.md`](FAILURE-TAXONOMY.md) — classifies every material
  outcome in the frozen v1 baseline by the smallest evidenced cause.
- [`DECISION-RECORD.md`](DECISION-RECORD.md) — for each proposed mechanism in
  #51–#57, the baseline evidence, why a smaller change is insufficient, the
  smallest intervention, exact contract/version, fixtures, scored corpus slice,
  proposed thresholds, efficiency bounds, ablation/removal rule, and disposition
  (retain, narrow, split, merge, defer, or close).
- [`gate-manifest.json`](gate-manifest.json) — the preregistered v2 gate
  manifest: corpus/grader versions, runtime/model stratum, executor and suite
  configuration, run count/timeout/retry/cost, deterministic invariants,
  proposed quality/stability/non-regression thresholds, mechanism ablations,
  efficiency bounds, and the rules for invalid runs, missing data, runtime
  drift, and threshold changes. Committed before any scored v2 output exists;
  every numeric threshold is marked as a proposal requiring owner confirmation.
- [`audits/`](audits) — the three independent graph audits #59 requires
  (scope/completeness, dependency/sequencing, shovel-readiness), each recorded
  as its own pass with its own findings, run against the live issue graph after
  the #51–#57 body and native-edge mutations below.

## What this is not

This record does not run any scored v2 evaluation. `gate-manifest.json`
preregisters the configuration a future scored run (owned by #57) must use; no
case in this directory has been executed against a real reviewer. Every
threshold here is explicitly a proposal, not a measured result.

It also does not modify `../baseline/v1/` in any way. That record stays frozen
exactly as merged in #58.
