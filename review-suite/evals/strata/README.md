# Baseline strata

A stratum is the unit of valid comparison. Two corpora are the same stratum only
when they send the same payload composition to the same runtime: same target
skill, same declared dependency closure, same runtime and model, same kind of
ground truth. Anything else is a different stratum, and reporting two strata as
one figure is an invalid comparison rather than a rougher one.

Each directory here is a complete, independently loadable corpus, because a
corpus index declares exactly one `target_skill`. `corpus.json` additionally
declares a `stratum` block naming the stratum id, the ground truth its
expectations came from, whether it is scored, and what it is for.

## Why one directory per stratum rather than one corpus with mixed targets

`review-code-change` requires `review-solution-simplicity`,
`review-correctness`, and `review-code-simplicity` to be readable and returns an
aggregate `blocked` result naming any that are missing. A stratum targeting the
orchestrator therefore ships eight documents; a stratum targeting one
self-sufficient lens ships two. The measured difference is not cosmetic — see
the pilot numbers below — so the payload has to be a property of the corpus, and
the corpus index is where a target can be swapped without a code change.

## Ground truth, and the stratum label it forces

This repository has no pull-request review history: zero reviews, zero review
threads, and zero comments across all of its pull requests. There is no
in-repository connector material to curate, and none may be invented, so ground
truth is sourced from real adjudicated **human** review elsewhere and from this
suite's own delivery history. Every shipped stratum is labelled `human-review`
or `repository-history` accordingly.

The **connector stratum is deferred, not satisfied.** Connector-escape recall
has never been measured here. A test asserts that no shipped corpus claims
`connector-review` ground truth, so a human-review figure cannot be reported as
a connector figure by accident. See
[the baseline limitations record](../baseline/v1/LIMITATIONS.md).

## Pilot strata

The three `pilot-*` corpora are unscored. They exist to establish executor
compatibility, timeout behaviour, and a cost and latency envelope **per
stratum**, and they are disjoint from every scored case: a test asserts no case
id appears both in a scored corpus and in a pilot corpus, because calibrating a
formulation on a case that is also scored fits the grader to the answer.

All three carry one byte-identical case, so the declared skill closure is the
only variable between them. That isolation is the point, and it has one
deliberate consequence: the case and its expectation are calibrated for the
orchestrator target, so the two lens strata grade as a miss and their graded
output is not a quality signal. Only their payload size, latency, cost, and
protocol outcomes are. Those two corpora declare
`stratum.grading_is_signal: false` for exactly this reason, a test forbids a
scored stratum from declaring it false, and
[`baseline/v1/pilot/README.md`](../baseline/v1/pilot/README.md) repeats the
caveat beside the reports themselves. **Do not quote the recall or false-clean
figure from either lens pilot report.**

That consequence is itself a corpus-design rule for the scored strata: **an
expectation is target-specific.** A correctness root cause is not a defect a
code-simplicity lens is contracted to report, so a scored simplicity stratum
must carry expectations authored for its own lens rather than a shared case
list.

### Measured envelope

Five runs per case, run from the committed tree at suite commit
`2ae0d23c18f247f49d3cc5e76f26d1cf9610c83e` — the commit every report records,
and the one the batch is reproducible from. Model `claude-opus-4-6[1m]`, corpus
version `1.3-pilot-*`, grader version `1.0`, timeout 300 s, no retries, one
fresh process per attempt. **20 attempts, zero evaluation failures, zero
timeouts, 1.2536 USD.**

| stratum                     | target                       | docs | digest             | case                         | input tokens / attempt | cold cost  | warm cost         | latency range |
| --------------------------- | ---------------------------- | ---- | ------------------ | ---------------------------- | ---------------------- | ---------- | ----------------- | ------------- |
| `pilot-orchestrator`        | `review-code-change`         | 8    | `9b2805f14cdd6158` | `rollback-guidance-render`   | 32,464                 | 0.1698 USD | 0.0519–0.0532 USD | 31.8–34.9 s   |
| `pilot-orchestrator`        | `review-code-change`         | 8    | `9b2805f14cdd6158` | `status-label-normalization` | 33,442                 | 0.2021 USD | 0.0589–0.0684 USD | 37.7–51.2 s   |
| `pilot-solution-simplicity` | `review-solution-simplicity` | 2    | `6257ee4448b15874` | `rollback-guidance-render`   | 25,800                 | 0.1094 USD | 0.0216–0.0238 USD | 10.4–14.2 s   |
| `pilot-code-simplicity`     | `review-code-simplicity`     | 2    | `a6187d8971eaef24` | `rollback-guidance-render`   | 25,617                 | 0.1116 USD | 0.0245–0.0303 USD | 12.7–22.9 s   |

Two measurements shape the ceiling, and both are in
[the cost-ceiling proposal](../baseline/v1/COST-CEILING-PROPOSAL.md):

- **The first attempt of a case costs three to four times the rest**, because it
  pays prompt-cache creation while later attempts read the cache. A ceiling
  built from the mean is exceeded by any run whose cache does not stay warm.
- **Cost tracks output volume, not packet size.** The orchestrator stratum
  carries two cases specifically to measure this. The larger packet raised input
  tokens by 3.0% and raised warm cost by 21% and warm mean latency by 22%,
  because mean warm output grew 29% — the packet warranted more findings, and
  output tokens dominate.

Verdict stability and finding stability were 1.0 on every case at five runs, so
five runs did not surface instability on these packets. That is a statement
about these packets, not a licence to reduce the run count.

Total pilot spend across the whole ticket: **4.6312 USD over 72 attempts** in
six batches. Only the last, the committed configuration above, is cited as the
frozen envelope; the earlier batches sized it and produced the prose the
formulations were calibrated against.

Raw output is retained outside git at
`review-suite/evals/artifacts/<stratum>/<commit>-<corpus_version>/`, with the
run's per-attempt records beside it. The commit and corpus version are in the
path deliberately: an artifact is named for its case and run number only, so
re-running a stratum into an unscoped directory silently replaced output a
committed record already cited — which happened once, and cost the
calibration-source run. The runner now refuses before launching any attempt when
a run would overwrite retained output. The exact per-stratum invocations,
artifact paths included, are recorded in
[`baseline/v1/frozen-configuration.json`](../baseline/v1/frozen-configuration.json).

## Scored strata

`s1-correctness-orchestrator` is populated with seven cases covering #58's
correctness classes: three accepted material escapes, two clean controls, and
two negative controls. Every case is minimized from a real review disposition in
the public `shaug/atelier` or in this repository's own history, and every case
carries an executable oracle as its second independent adjudication.

It declares `scored: false`, which is not a formality. Every expectation is
`calibrated: false` and no case has been run through any runtime, deliberately —
observing a scored case's prose in order to calibrate it would fit the grader to
the answer. Limitation 14 in
[the limitations record](../baseline/v1/LIMITATIONS.md) sets out the four
resolutions and the owner picks one before `scored` flips.

`s2-solution-simplicity-lens` and `s3-code-simplicity-lens` remain unpopulated.

## Adding a stratum

1. Create `review-suite/evals/strata/<stratum-id>/` with `corpus.json`,
   `reviewer/PROMPT.md`, `reviewer/<case>/packet.json`, and private
   `expectations/` and `provenance/` records for every declared case.
2. Declare the `stratum` block, including honest `ground_truth` and
   `grading_is_signal`.
3. Add a calibration set under `review-suite/evals/calibration/` for every
   scored case; the calibration test requires one and will fail without it. It
   must probe every grading boundary, and each probe must demonstrate what its
   kind claims against the real grader.
4. Run `just audit-review-corpus`. It discovers every corpus here, so a new
   stratum is gated without editing the recipe.
5. Run `just test-review-suite`.
