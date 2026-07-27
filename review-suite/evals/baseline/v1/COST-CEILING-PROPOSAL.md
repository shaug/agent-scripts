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
rested on a denominator of one. The envelope below was therefore measured fresh,
per stratum, at the frozen configuration.

## Measured pilot input

Three runs per stratum, one case per stratum, nine attempts, zero evaluation
failures. Suite commit `16560d807c66076fcbf3f00d3a87f543c6ae2458`, model
`claude-opus-4-6[1m]`, timeout 300 s, no retries.

| stratum                     | closure docs | input tokens / attempt | cost / attempt observed    | latency max |
| --------------------------- | ------------ | ---------------------- | -------------------------- | ----------- |
| `pilot-orchestrator`        | 8            | 32,573                 | 0.1774, 0.0563, 0.0542 USD | 37.2 s      |
| `pilot-solution-simplicity` | 2            | 25,901                 | 0.1089, 0.0240, 0.0228 USD | 14.2 s      |
| `pilot-code-simplicity`     | 2            | 25,691                 | 0.1110, 0.0242, 0.0245 USD | 15.0 s      |

## The one non-obvious thing the pilot measured

Per-attempt cost is not uniform. In every stratum the **first** attempt cost
three to four times the ones after it, because it pays prompt-cache creation
while later attempts read the cache. The whole payload — skill closure,
contracts, reviewer prompt — is identical across attempts of a stratum, so
almost all of it is cacheable.

A ceiling built from the mean would therefore be exceeded by any real run whose
cache does not stay warm: a stratum executed in short bursts, strata
interleaved, a cache eviction, or simply a longer wall-clock run. The proposal
below is built from the **cold** per-attempt cost, so the ceiling holds in the
worst case rather than the lucky one.

## Proposal

Scored composition and run count as frozen: 5 runs per case; 7 cases in the
orchestrator-targeted correctness stratum, 4 in each lens stratum.

| stratum                       | cases | runs | attempts | cold cost / attempt | worst-case spend | +25% headroom | **proposed ceiling** |
| ----------------------------- | ----- | ---- | -------- | ------------------- | ---------------- | ------------- | -------------------- |
| `s1-correctness-orchestrator` | 7     | 5    | 35       | 0.1774 USD          | 6.21 USD         | 7.76 USD      | **8.00 USD**         |
| `s2-solution-simplicity-lens` | 4     | 5    | 20       | 0.1089 USD          | 2.18 USD         | 2.72 USD      | **3.00 USD**         |
| `s3-code-simplicity-lens`     | 4     | 5    | 20       | 0.1110 USD          | 2.22 USD         | 2.78 USD      | **3.00 USD**         |
| all three                     | 15    | 5    | 75       |                     | 10.61 USD        | 13.26 USD     | **14.00 USD**        |

Expected spend if caching behaves as observed, using the warm figures, is
materially lower: about 3.4 USD for `s1`, 1.0 USD for each lens stratum, roughly
**5.5 USD total**. The ceiling is deliberately the pessimistic number; the
expectation is deliberately not.

The headroom covers reported-cost variance, a slightly longer answer, and the
possibility that a scored packet is larger than the pilot packet. It does not
cover a model change, a closure change, or a run-count change: each of those is
a new stratum and needs its own measured envelope.

## Ceilings are per stratum, not blended

The orchestrator stratum costs roughly 1.8 times a lens stratum per attempt
because it ships eight documents rather than two. One blended figure would
over-fund the lens strata and under-fund the orchestrator, and the first stratum
to run would silently consume another's budget. Track and enforce each
separately.

## What to do when a ceiling is reached

Stop further runs in that stratum and record an incomplete baseline for it.
Never reduce repetitions after outputs are visible: choosing a smaller
denominator once results are known is how a stability figure becomes a claim
about the model rather than a measurement.

## Costs this proposal does not cover

- The scored run itself is the only paid step; `just test`, `just lint`,
  `just check`, and `just audit-review-corpus` never launch a runtime.
- The pilot already spent **0.8889 USD** in total: 0.6031 USD over the nine
  attempts recorded here, plus 0.2857 USD over three earlier orchestrator
  attempts at corpus version `1.0-pilot-orchestrator`, whose observed prose the
  shipped formulations were calibrated against.
- Re-running a stratum after a formulation change is not free. Calibration is
  done against pilot output only, so a scored stratum should need no re-run for
  grading reasons.
