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
protocol outcomes are.

That consequence is itself a corpus-design rule for the scored strata: **an
expectation is target-specific.** A correctness root cause is not a defect a
code-simplicity lens is contracted to report, so a scored simplicity stratum
must carry expectations authored for its own lens rather than a shared case
list.

### Measured envelope, three runs per stratum

Suite commit `16560d807c66076fcbf3f00d3a87f543c6ae2458`, model
`claude-opus-4-6[1m]`, corpus version `1.1-pilot-*`, grader version `1.0`,
timeout 300 s, no retries, nine attempts, zero evaluation failures.

| stratum                     | target                       | docs | digest             | input tokens / attempt | cost / attempt (mean) | cost / attempt (first, cold cache) | latency mean | latency max |
| --------------------------- | ---------------------------- | ---- | ------------------ | ---------------------- | --------------------- | ---------------------------------- | ------------ | ----------- |
| `pilot-orchestrator`        | `review-code-change`         | 8    | `9b2805f14cdd6158` | 32,573                 | 0.0959 USD            | 0.1774 USD                         | 34.8 s       | 37.2 s      |
| `pilot-solution-simplicity` | `review-solution-simplicity` | 2    | `6257ee4448b15874` | 25,901                 | 0.0519 USD            | 0.1089 USD                         | 13.2 s       | 14.2 s      |
| `pilot-code-simplicity`     | `review-code-simplicity`     | 2    | `a6187d8971eaef24` | 25,691                 | 0.0532 USD            | 0.1110 USD                         | 13.4 s       | 15.0 s      |

The first attempt in every stratum cost roughly three to four times the
following ones, because it pays prompt-cache creation while later attempts read
the cache. A ceiling built from the mean would be exceeded by any run whose
cache does not stay warm, which is why
[the cost-ceiling proposal](../baseline/v1/COST-CEILING-PROPOSAL.md) is built
from the cold figure.

Total pilot spend for the recorded run: **0.6031 USD over nine attempts**, plus
**0.2857 USD over three attempts** for the earlier calibration-source run at
corpus version `1.0-pilot-orchestrator`, whose observed prose the shipped
formulations were calibrated against. **0.8889 USD total.**

## Adding a stratum

1. Create `review-suite/evals/strata/<stratum-id>/` with `corpus.json`,
   `reviewer/PROMPT.md`, `reviewer/<case>/packet.json`, and private
   `expectations/` and `provenance/` records for every declared case.
2. Declare the `stratum` block, including honest `ground_truth`.
3. Add a calibration set under `review-suite/evals/calibration/` for every
   scored case; the calibration test requires one and will fail without it.
4. Run `just audit-review-corpus`. It discovers every corpus here, so a new
   stratum is gated without editing the recipe.
5. Run `just test-review-suite`.
