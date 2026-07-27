# Per-stratum cost ceiling: proposal

This is a **proposal**, not a ceiling. A scored run spends real money, so the
ceiling has to be preregistered by the repository owner *before* any scored
output is examined; otherwise a run that looks disappointing can be quietly
extended, or a run that looks good can be quietly stopped. Every number below is
derived from this ticket's own unscored pilot against the fixed usage
accounting. Nothing here is extrapolated from any earlier figure.

## Why an earlier figure could not be used

The evaluator's protocol smoke run reported a cost, and that figure is void for
this purpose twice over. Its usage accounting dropped cache-creation and
cache-read tokens, understating input by orders of magnitude, and its verdicts
rested on a denominator of one. The envelope below was measured fresh, per
stratum, at the frozen configuration.

## Measured pilot input

Five runs per case, run from the committed tree at suite commit
`2ae0d23c18f247f49d3cc5e76f26d1cf9610c83e` — the commit every report records,
and the one the batch is reproducible from. Model `claude-opus-4-6[1m]`, corpus
version `1.3-pilot-*`, grader version `1.0`, timeout 300 s, no retries, one
fresh process per attempt. **20 attempts, zero evaluation failures, zero
timeouts, 1.2536 USD.**

| stratum                     | closure docs | case                         | input tokens / attempt | cost, first attempt (cold cache) | cost, later attempts (cache read) | latency range |
| --------------------------- | ------------ | ---------------------------- | ---------------------- | -------------------------------- | --------------------------------- | ------------- |
| `pilot-orchestrator`        | 8            | `rollback-guidance-render`   | 32,464                 | 0.1698 USD                       | 0.0519 – 0.0532 USD               | 31.8 – 34.9 s |
| `pilot-orchestrator`        | 8            | `status-label-normalization` | 33,442                 | 0.2021 USD                       | 0.0589 – 0.0684 USD               | 37.7 – 51.2 s |
| `pilot-solution-simplicity` | 2            | `rollback-guidance-render`   | 25,800                 | 0.1094 USD                       | 0.0216 – 0.0238 USD               | 10.4 – 14.2 s |
| `pilot-code-simplicity`     | 2            | `rollback-guidance-render`   | 25,617                 | 0.1116 USD                       | 0.0245 – 0.0303 USD               | 12.7 – 22.9 s |

Every per-attempt figure above is re-derivable from the retained per-attempt
records at
`review-suite/evals/artifacts/<stratum>/2ae0d23-1.3-<stratum>.attempts.jsonl`.

## Two things the pilot measured that change how a ceiling must be built

### 1. The first attempt of a case costs three to four times the rest

Every stratum shows it. The payload — skill closure, review contracts, reviewer
prompt, packet — is identical across attempts of a case, so almost all of it is
cacheable; the first attempt pays cache creation and the rest are cache reads.

A ceiling built from the mean would be exceeded by any real run whose cache does
not stay warm: strata executed in short bursts, strata interleaved, an eviction,
or simply a longer wall-clock run. **The proposal below assumes every attempt
pays cache creation**, which is a cost actually observed rather than a
hypothetical one.

### 2. Cost tracks output volume, not packet size

This is the non-obvious one, and it is why the orchestrator stratum carries two
pilot cases of materially different size.

Comparing the two cases inside the same run batch, so the runtime environment is
constant: the larger packet raised input tokens by 978, **3.0%**. It raised mean
cache-read cost by **21%** and mean cache-read latency by **22%**, because mean
cache-read output grew from 1,458 to 1,880 tokens, **29%** — the larger packet
warranted more findings, and output tokens are far more expensive per token than
cached input.

So per-attempt cost scales with *how much a reviewer has to say*, which tracks
the number of material findings a case warrants — not with how big the packet
is. A scored stratum whose escapes carry two root causes each will sit at the
upper end of the observed range; its clean controls will sit at the lower end.
The proposal therefore uses the **worse** of the two measured cases for the
orchestrator stratum.

Absolute input-token counts drift slightly across batches — 32,507, 32,955,
33,166, then 32,464 for the same case — because reported input includes
runtime-side prompt overhead that the payload does not control. Treat the
within-batch difference as the measurement and the absolute count as
approximate.

## Proposal

Scored composition and run count as frozen: 5 runs per case; 7 cases in the
orchestrator-targeted correctness stratum, 4 in each lens stratum.

| stratum                       | cases | runs | attempts | worst cold cost / attempt | all-cold worst case | +15% headroom | **proposed ceiling** | expected spend |
| ----------------------------- | ----- | ---- | -------- | ------------------------- | ------------------- | ------------- | -------------------- | -------------- |
| `s1-correctness-orchestrator` | 7     | 5    | 35       | 0.2021 USD                | 7.07 USD            | 8.13 USD      | **9.00 USD**         | 3.33 USD       |
| `s2-solution-simplicity-lens` | 4     | 5    | 20       | 0.1094 USD                | 2.19 USD            | 2.52 USD      | **3.00 USD**         | 0.82 USD       |
| `s3-code-simplicity-lens`     | 4     | 5    | 20       | 0.1116 USD                | 2.23 USD            | 2.57 USD      | **3.00 USD**         | 0.93 USD       |
| all three                     | 15    | 5    | 75       |                           | 11.49 USD           | 13.22 USD     | **15.00 USD**        | 5.08 USD       |

**Expected spend** assumes the cache behaves as measured — one cache-creation
attempt per case, the rest cache reads — using the worst observed warm figure
per stratum. It is the number to expect. The ceiling is the number to
preregister. They differ by roughly a factor of three, and that gap is the
measured cost of not being able to rely on cache warmth.

The headroom covers reported-cost variance and a case that warrants more output
than either pilot case. It does **not** cover a model change, a closure change,
or a run-count change: each of those is a new stratum and needs its own measured
envelope.

## Ceilings are per stratum, not blended

Per attempt, the orchestrator stratum costs roughly 1.7 times a lens stratum
cold and roughly 2.5 times warm, because it ships eight documents rather than
two. One blended figure would over-fund the lens strata and under-fund the
orchestrator, and the first stratum to run would silently consume another's
budget. Track and enforce each separately.

## What to do when a ceiling is reached

Stop further runs in that stratum and record an incomplete baseline for it.
Never reduce repetitions after outputs are visible: choosing a smaller
denominator once results are known is how a stability figure becomes a claim
about the model rather than a measurement.

## What this proposal does not cover

- The scored run is the only paid step. `just test`, `just lint`, `just check`,
  and `just audit-review-corpus` never launch a runtime.
- **Pilot spend across this ticket: 4.6312 USD over 72 attempts**, in six
  batches — 0.2857 (3 attempts, the calibration source), 0.6031 (9), 0.8496
  (10), 0.4126 (10), 1.2266 (20), and 1.2536 (20, the committed configuration).
  The earlier batches sized the envelope, produced the prose the formulations
  were calibrated against, and were superseded as the corpus and the records
  were corrected; only the last is cited as the frozen envelope, and only it ran
  from a committed tree.
- Re-running a stratum after a formulation change is not free, so calibration is
  done against pilot output only. A scored stratum should need no re-run for
  grading reasons.
