# Grader calibration and adjudication record

## What calibration is, and why it cannot be skipped

The reference grader matches an observed finding to a private root cause when
the finding names the affected surface *and* its prose contains one of the
shipped formulations, after normalisation. Containment is exact, so a
formulation written before any real reviewer prose existed can be a perfectly
reasonable sentence and still recognise nothing. An uncalibrated grader does not
report a conservative score; it reports a meaningless one.

The evaluator that produced this interface said so explicitly: its formulations
were written before any run and were never tuned, which is why its recall was
0.0 while its verdicts were mostly right.

## Calibration is derived from pilot output only

Tuning a formulation after seeing scored output is fitting the grader to the
answer. That is why the pilot corpus is disjoint from every scored stratum — a
test asserts it — and why calibration happened before any scored case exists at
all.

## What was calibrated, from what

Case `rollback-guidance-render`, carried identically by all three pilot strata.

**Source run:** three attempts at corpus version `1.0-pilot-orchestrator`,
target `review-code-change`, closure digest `9b2805f14cdd6158`, model
`claude-opus-4-6[1m]`, suite commit `16560d807c66076fcbf3f00d3a87f543c6ae2458`.
Raw output retained outside git at
`review-suite/evals/artifacts/pilot-orchestrator/`. Spend: 0.2857 USD.

**Observed before calibration:** all three attempts returned `changes_required`
and all three identified the real root cause. All three scored `partial` —
recall 0.0 — because none of the four shipped formulations appeared in the prose
the reviewer actually wrote.

**Two changes, both recorded in the corpus at version `1.1-pilot-*`:**

1. `equivalent_formulations` for `rc.unsupported-emitted-subcommand` were
   replaced with four phrases drawn verbatim from the observed prose, each
   naming the offending subcommand explicitly so a finding about a different
   command cannot match:
   - `` `storectl export` does not exist in the installed CLI ``
   - `` `storectl export`, which is not a registered subcommand ``
   - `` there is no `export` subcommand ``
   - `` the `export` subcommand does not exist ``
2. `surface` was narrowed from `storectl/guidance.py render_rollback_guidance`
   to `render_rollback_guidance`. Surface matching is token-level, so the path
   component `storectl` shared a token with essentially every location in the
   packet, and a deliberately wrong gating finding at an unrelated file scored
   `partial` instead of being charged as a false positive. With a broad surface
   the false-positive rate is not measurable at all.

Formulations for `anf.test-asserts-shape-only` were likewise drawn from observed
prose. Those for `anf.unquoted-store-root` were **not** observed in any run and
remain unvalidated; they are retained because a competent reviewer plausibly
raises the point.

## Validation run

Three fresh attempts per stratum at the calibrated version `1.1-pilot-*`, nine
attempts, zero evaluation failures, 0.6031 USD. On the orchestrator stratum the
calibrated formulations scored **recall 1.0, false-positive rate 0.0, zero
adjudication referrals, verdict stability 1.0 over three attempts** against
prose generated after calibration — so the calibration generalised beyond the
exact sentences it was drawn from. It is not proven to generalise indefinitely;
see limitation 3 in [LIMITATIONS.md](LIMITATIONS.md).

## Calibration cases and how they are enforced

`review-suite/evals/calibration/<case_id>.json` holds the probe reviews.
`review-suite/scripts/tests/test_eval_calibration.py` replays each probe through
the real grader against the real shipped expectation and asserts the exact
classification, matched root causes, recall, false-positive ids, and
adjudication referrals. It runs under `just test-review-suite` and `just test`,
and launches nothing.

The calibration set must probe every grading boundary; a set that omits one
fails the test rather than passing quietly. Current probes for
`rollback-guidance-render`:

| probe                               | kind                       | asserts                                                                                                  |
| ----------------------------------- | -------------------------- | -------------------------------------------------------------------------------------------------------- |
| `probe.observed-root-cause`         | `observed`                 | the prose a real reviewer returned is `matched`, recall 1.0                                              |
| `probe.paraphrase`                  | `paraphrase`               | a differently worded equivalent claim is also `matched`                                                  |
| `probe.overlapping-symptom`         | `overlapping_symptom`      | the same symptom without the cause is `partial`, earns no recall, and is not charged as a false positive |
| `probe.duplicate-report`            | `duplicate_report`         | one root cause reported twice earns recall once; the second is `duplicate`                               |
| `probe.partial-claim-wrong-surface` | `partial_claim`            | the right cause at the wrong surface is `partial`, neither credited nor punished                         |
| `probe.plausible-false-positive`    | `plausible_false_positive` | a plausible but unevidenced gating finding is `unexpected` and **is** charged as a false positive        |
| `probe.accepted-non-finding`        | `accepted_non_finding`     | a real but non-material observation is `accepted`, not a false positive                                  |

## Independent adjudication: not satisfied

Every expectation shipped here was authored by **one** context. The requirement
is two independent adjudications for each material root cause, accepted
non-finding, severity, and allowed formulation, from genuinely separate parties,
with disagreements resolved in a recorded note.

One context generating both sides is not independence, and nothing here pretends
otherwise. No scored run may launch until this is satisfied.

What an adjudicator needs to decide, per root cause:

1. Is the stated root cause the material one, or a symptom of a different one?
2. Is the severity right?
3. Is each accepted formulation genuinely equivalent, and is any of them loose
   enough to match a wrong finding?
4. Is each accepted non-finding genuinely non-material, rather than a second
   root cause being tolerated away?
5. Is the surface the smallest identifying symbol?

Disagreements are recorded here. A disagreement that cannot be resolved excludes
the case or marks it unscorable; it is never recorded as a reviewer miss.

### Adjudication status

| case                       | root cause                          | adjudications | status                                                                         |
| -------------------------- | ----------------------------------- | ------------- | ------------------------------------------------------------------------------ |
| `rollback-guidance-render` | `rc.unsupported-emitted-subcommand` | 1             | **awaiting second party**                                                      |
| `rollback-guidance-render` | `anf.test-asserts-shape-only`       | 1             | **awaiting second party**                                                      |
| `rollback-guidance-render` | `anf.unquoted-store-root`           | 1             | **awaiting second party**; formulations unvalidated against any observed prose |

This case is a pilot case and is never scored, so its adjudication gap does not
affect a baseline figure. It is listed because the same gap will apply to every
scored case, and the procedure above is the one the scored strata will use.
