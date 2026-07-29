# v2 planning record and scored closeout

This directory holds both the planning/definition gate #59 produces and #57's
own scored closeout that executes against it. The planning documents change no
review prompt, schema, rubric, orchestration, or caller runtime behavior by
themselves — they interpret the frozen `../baseline/v1/` record and turn it into
an implementation-ready decision for #51–#57. #57's own documents (listed under
"Scored closeout (#57)" below) run the preregistered scored comparison and
report a pass/fail verdict per mechanism as a recommendation, not a removal
decision.

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
- [`audits/scope-completeness-audit.md`](audits/scope-completeness-audit.md),
  [`audits/dependency-sequencing-audit.md`](audits/dependency-sequencing-audit.md),
  [`audits/shovel-readiness-audit.md`](audits/shovel-readiness-audit.md) — the
  three required graph audits, each run as its own independent pass against the
  live `#51`–`#57` graph after the body and native-edge mutations described
  above, with findings and fixes recorded separately per pass.

## Scored closeout (#57)

- [`FROZEN-V2-CONFIGURATION.md`](FROZEN-V2-CONFIGURATION.md) — the exact scored
  configuration #57 ran: the reviewed grader-version transition (`1.0` → `1.1`,
  owner-authorized), the verified runtime/model stratum, suite commits, and the
  ablation mechanism (a `--skill-root` override in `runner.py`) used to isolate
  each `review-correctness` pass without editing the shipped skill.
- [`S1-ABLATION-MATRIX.md`](S1-ABLATION-MATRIX.md) — the three-configuration
  `s1-correctness-orchestrator` ablation (traversal-only,
  verification-sufficiency-only, both together), each scored independently, plus
  the reused `s2`/`s3` non-regression check, against the settled per-case gate.
- [`DETERMINISTIC-AND-INTEGRATION-EVIDENCE.md`](DETERMINISTIC-AND-INTEGRATION-EVIDENCE.md)
  — every required deterministic gate and caller-integration scenario, cited
  against the exact existing #51–#56 test that proves it.
- [`CLOSEOUT-REPORT.md`](CLOSEOUT-REPORT.md) — the full synthesis: mechanism
  verdicts (recommendation only, not a removal decision), residual risks, spend
  against the $20 ceiling, and every acceptance criterion checked explicitly.
- `s1-correctness-orchestrator-ablation-{traversal,verification}-only.report.json`
  — the two new machine-readable aggregate reports this ticket produced.
  `s1-correctness-orchestrator.report.json`,
  `s2-solution-simplicity-lens.report.json`, and
  `s3-code-simplicity-lens.report.json` are reused from predecessor measurement
  tasks in this epic, not re-run.

## What the planning documents above are not

They do not run any scored v2 evaluation themselves. `gate-manifest.json`
preregisters the configuration the scored run above uses; every threshold in it
remained a proposal, never tuned after any scored output was examined.

Neither the planning documents nor #57's own closeout documents modify
`../baseline/v1/` in any way. That record stays frozen exactly as merged in #58.
