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
`claude-opus-4-6[1m]`. Spend: 0.2857 USD. Per-attempt latency 52.7 s, 30.4 s,
39.7 s. It ran from an uncommitted tree, so it is cited by its corpus version
and closure digest rather than by a commit: no commit reproduces it.

> **The source run's raw output is no longer retained.** The runner names an
> artifact `<case>.run-<n>.stdout.json` with no corpus-version component, so the
> validation run below wrote into the same directory and replaced it. The loss
> is recorded rather than papered over: nothing here can now reproduce the exact
> sentences the four formulations were first drawn from.
>
> Two changes stop it recurring. `runner.refuse_to_overwrite_artifacts` fails
> **before any attempt launches** when a run would overwrite retained output, so
> the failure is a refusal that costs nothing rather than a silent replacement.
> And retained output now goes to a version-scoped directory,
> `artifacts/<stratum>/<corpus_version>/`, which is the artifact path recorded
> in the frozen per-stratum invocations.
>
> The committed `observed` probes are therefore verbatim, byte for byte, from
> the **first post-calibration run**, whose output is retained at
> `artifacts/pilot-orchestrator/1.1-pilot-orchestrator/` and has been retained
> under a version-scoped path ever since. For the claim that actually matters
> this is stronger evidence than the lost run would have been: it is prose the
> formulations were *not* fitted to, and it resolves to a file that exists.
>
> Every corpus-version bump since `1.0` changed private data only —
> `equivalent_formulations`, `surface`, `provenance.recorded_at`,
> `expectation.calibrated`, and the addition of a second case — so no bump could
> alter what a reviewer saw for this case. A payload carries only the packet,
> the reviewer prompt, the skill closure, the review contracts, and public run
> metadata. `just audit-review-corpus` proves that separation on every case,
> over the complete payload, before anything launches.

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
   to `render_rollback_guidance`. Surface matching counts one shared normalised
   token as a hit, so the path component `storectl` collided with nearly every
   location in the packet and a deliberately wrong gating finding scored
   `partial` instead of being charged as a false positive.

   Narrowing shrank that unchargeable region; it did **not** remove it. A wrong
   gating finding at `storectl/guidance.py`, at `tests/test_guidance.py`, or at
   the untouched `render_apply_plan` still collides on `guidance` and is still
   referred rather than charged. `false_positive_rate` is therefore a lower
   bound rather than a rate, `frozen-configuration.json` records it as partially
   measurable, the `probe.surface-token-collision` probe pins the residual gap
   in the calibration set, and the one-token rule is escalated to #59 as a
   candidate v2 gate rather than recorded as solved. See limitation 4 in
   [LIMITATIONS.md](LIMITATIONS.md) for the measured table.

Formulations for `anf.test-asserts-shape-only` were likewise drawn from observed
prose. Those for `anf.unquoted-store-root` were **not** observed in any run and
remain unvalidated; they are retained because a competent reviewer plausibly
raises the point.

## Validation, and a second measurement of the same effect

The calibrated formulations were re-measured after calibration, on prose they
were not fitted to. At the frozen configuration — five runs per case, corpus
version `1.3-pilot-*`, suite commit `2ae0d23c18f247f49d3cc5e76f26d1cf9610c83e`,
raw output retained at
`review-suite/evals/artifacts/pilot-orchestrator/2ae0d23-1.3-pilot-orchestrator/`
— `rollback-guidance-render` scored **recall 1.0, false-positive rate 0.0, zero
adjudication referrals, and verdict stability 1.0 over five attempts.** The
calibration generalised beyond the exact sentences it was drawn from. It is not
proven to generalise indefinitely; see limitation 3 in
[LIMITATIONS.md](LIMITATIONS.md).

The same run measured the opposite condition on an independent case.
`status-label-normalization` was added to the orchestrator stratum with two root
causes authored from an adjudicated source thread and **deliberately left
uncalibrated**, as a control:

| case                         | `calibrated` | recall  | verdict stability | referrals | reviewer verdict       |
| ---------------------------- | ------------ | ------- | ----------------- | --------- | ---------------------- |
| `rollback-guidance-render`   | `true`       | **1.0** | 1.0               | 0         | `changes_required` × 5 |
| `status-label-normalization` | `false`      | **0.0** | 1.0               | 10        | `changes_required` × 5 |

The uncalibrated case's reviewer gated the change on every attempt, stably, and
the grader matched neither root cause. Two cases, ten attempts, one conclusion:
**an uncalibrated expectation reports a number about itself, not about the
reviewer.**

That is why the flag exists. `expectation.calibrated` is machine-readable, and a
test refuses a scored case that is not calibrated or that ships no calibration
set. The uncalibrated case is retained deliberately as the measured control, and
its ten referrals are also the evidence for the adjudication disagreement
recorded against it in [ADJUDICATION-PLAN.md](ADJUDICATION-PLAN.md).

## Calibration cases and how they are enforced

`review-suite/evals/calibration/<case_id>.json` holds the probe reviews.
`review-suite/scripts/tests/test_eval_calibration.py` replays each probe through
the real grader against the real shipped expectation and asserts the exact
classification, matched root causes, recall, false-positive ids, and
adjudication referrals. It runs under `just test-review-suite` and `just test`,
and launches nothing.

A probe's `kind` is a claim about grading behaviour, not a label. The test
asserts the required outcome **per kind against the real grader**, not against
the set's own `expect` block, so a set cannot certify a boundary by declaring
whatever outcome it happens to get — a `plausible_false_positive` probe that
does not classify `unexpected` and charge a false positive fails. A set that
omits a required boundary altogether also fails. Current probes for
`rollback-guidance-render`:

| probe                               | kind                       | asserts                                                                                                                                            |
| ----------------------------------- | -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `probe.observed-root-cause`         | `observed`                 | the prose a real reviewer returned is `matched`, recall 1.0                                                                                        |
| `probe.paraphrase`                  | `paraphrase`               | a differently worded equivalent claim is also `matched`                                                                                            |
| `probe.overlapping-symptom`         | `overlapping_symptom`      | the same symptom without the cause is `partial`, earns no recall, and is not charged as a false positive                                           |
| `probe.duplicate-report`            | `duplicate_report`         | one root cause reported twice earns recall once; the second is `duplicate`                                                                         |
| `probe.partial-claim-wrong-surface` | `partial_claim`            | the right cause at the wrong surface is `partial`, neither credited nor punished                                                                   |
| `probe.plausible-false-positive`    | `plausible_false_positive` | a plausible but unevidenced gating finding sharing no surface token is `unexpected` and **is** charged as a false positive                         |
| `probe.surface-token-collision`     | `surface_token_collision`  | the measured limit: an equally wrong gating finding at the untouched neighbour is only `partial`, because one shared token counts as a surface hit |
| `probe.accepted-non-finding`        | `accepted_non_finding`     | a real but non-material observation is `accepted`, not a false positive                                                                            |

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
