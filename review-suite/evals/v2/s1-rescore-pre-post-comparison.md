# `s1-correctness-orchestrator`: pre-#53 vs. post-#53, under the fixed grader

This is the plain, apples-to-apples comparison the repository owner asked for:
whether `dependency-strictness-propagation` and `stale-claim-release-guard` -
the two cases the frozen v1 baseline recorded as confident (zero-ambiguity)
misses, and the two cases #53 was built to fix

- were a genuine reviewer capability gap before #53, and whether #53 closed it.
  It measures facts; it does not decide #54's fate, #52/#53's disposition, or
  anything else. See `GRADER-1.1-COMPARABILITY.md` in this directory for why a
  grader fix was necessary before this comparison meant anything, and
  `s1-rescore-frozen-configuration.json` for the originally frozen re-score
  configuration this comparison extends.

## The four numbers

Both cases have exactly one material root cause each, so `mean_recall` is the
fraction of 5 attempts that named it in an accepted formulation, and
`mean_combined_recall` is the fraction of 5 attempts that either did that or had
the surface concretely and relevantly named in a referred finding (the
preregistered v2 scoring gate's alternative path, relevance-guarded per #53's
issue body).

| Case                                | Era                                     | Runs       | `mean_recall` | `mean_combined_recall` | Gate (`>=0.6` recall OR `>=0.8` combined) |
| ----------------------------------- | --------------------------------------- | ---------- | ------------- | ---------------------- | ----------------------------------------- |
| `dependency-strictness-propagation` | pre-#53 (commit `8e4fdbd`, #52's merge) | 5/5 graded | 0.0           | **1.0**                | **PASS** (combined path)                  |
| `dependency-strictness-propagation` | post-#53 (commit `2c671fd`)             | 5/5 graded | 0.0           | **1.0**                | **PASS** (combined path)                  |
| `stale-claim-release-guard`         | pre-#53 (commit `8e4fdbd`, #52's merge) | 5/5 graded | 0.0           | **1.0**                | **PASS** (combined path)                  |
| `stale-claim-release-guard`         | post-#53 (commit `2c671fd`)             | 5/5 graded | 0.0           | **1.0**                | **PASS** (combined path)                  |

Every one of these 20 attempts (10 pre-#53 + 10 post-#53) individually scored
`combined_recall: 1.0` - this is not an average smoothing over a mixed result;
the fixed grader recognizes the correct root cause in all 10 attempts of both
eras. `mean_recall` stays `0.0` in both eras because both cases are
deliberately, permanently `calibrated: false` (their `equivalent_formulations`
were authored without ever being checked against real reviewer prose, by corpus
design - see `CALIBRATION.md`), so a real reviewer's paraphrase essentially
never contains one of the five pre-written phrases verbatim. That is a property
of the corpus's calibration state, not of reviewer behavior, and applies
identically to both eras.

## Non-regression floor (post-#53, 35-attempt full-stratum run)

| Requirement                                                                                                        | v1 (frozen)       | v2, this run (fixed grader) | Holds?              |
| ------------------------------------------------------------------------------------------------------------------ | ----------------- | --------------------------- | ------------------- |
| `dependency-strictness-propagation` / `stale-claim-release-guard` `verdict_stability`, `finding_stability` >= 1.0  | 1.0 / 1.0         | 1.0 / 1.0 (both cases)      | Yes                 |
| `dependency-hint-parser-coverage`, `post-bootstrap-module-load`, `session-continuation-summary`: 0 false positives | 0 each            | 0 each                      | Yes                 |
| `process-isolation-assertion` false-alarm rate \<= 2/5                                                             | 2/5               | 0/5                         | Yes (improved)      |
| `optional-tool-probe` (open question, not gated)                                                                   | `mean_recall` 0.2 | `mean_recall` 0.8           | Not gated; recorded |

One evaluation failure occurred in the 35-attempt run
(`session-continuation-summary` run 4, `malformed_output`: the reviewer's own
`consumer_impact_evidence[1].disposition` failed validator cross-checks) -
excluded from grading per protocol, not counted toward any floor, consistent
with the "never retried, never silently padded" rule both v1 and this run share.

## What this means

**The pre-#53 reviewer already found both defects, every time, before #53
existed.** Reading the raw pre-#53 attempts directly (not just the grade)
confirms this: run 1 of `dependency-strictness-propagation` names
`dependency_finalized`/`integration_proven` and the exact consequence
(`reconcile_closed` reopens the record, the scheduler path does not); run 1 of
`stale-claim-release-guard` names the `owner=None` scan-to-apply race and the
exact guard-skip mechanism. All 5 attempts of each case, both pre- and post-#53,
are this concrete and this consistent - checked individually, not sampled.

**The frozen v1 baseline's "confident miss" on these two cases was a grader
artifact, not a demonstrated reviewer capability gap.** v1 scored these two
cases with `GRADER_VERSION` `1.0`, which read only structured `location` fields
for a surface match; a reviewer that names the exact symbol only in prose (which
both eras of reviewer did, on every attempt) was scored `unexpected` (false
positive) and the root cause counted as a genuine miss, identically to what this
measurement's own post-#53 run showed before the grader was fixed. v1's raw
attempts are not retained anywhere on this machine or in this repository's
history, so this cannot be proven attempt-by-attempt for v1 the way it was just
proven for pre-#53 and post-#53 here - but the mechanism is the same code, the
same two deliberately-uncalibrated expectations, and the same "confident, zero-
referral" shape v1 reported, on a reviewer now directly shown to answer these
exact two cases correctly and consistently in the era immediately preceding v1's
own measurement window.

**#53's two added passes (consumer/impact-traversal, verification-sufficiency),
while real and reasonable engineering, are not shown by this evidence to have
closed a demonstrated recall or stability gap on these two specific cases.** The
pre-#53 reviewer already populated `consumer_impact_evidence` for the traversal
case in the sampled raw attempt, and already stated the correct verification gap
in prose for the guard case, without being explicitly instructed to run either
pass by name.

## Methodology notes and honest caveats

- **The grader fix happened mid-measurement, after some scored v2 output was
  already visible.** This is a real deviation from strict freeze-before-scoring
  discipline in letter, and is disclosed rather than smoothed over. It differs
  from the tuning `gate-manifest.json` forbids ("frozen the moment any scored
  output is examined... requires a new manifest version") in kind, not just in
  degree: the defect was identified by reading raw prose directly and finding it
  plainly, concretely correct despite being graded a miss - not by adjusting a
  number to get a preferred result - and the fix was constrained by an existing,
  unrelated calibration boundary (`probe.partial-claim-wrong-surface`) that had
  to keep passing, not by this comparison's own two target cases.
  `GRADER-1.1-COMPARABILITY.md` documents the change and the new-stratum rule
  this creates.
- **v1's own raw attempts cannot be re-graded** - they are not retained anywhere
  reachable from this repository or this machine, confirmed by direct search.
  The claim above about v1's baseline is therefore a well-evidenced inference
  from an unchanged mechanism and an unchanged expectation file, not a re-graded
  fact the way pre-#53 and post-#53 are.
- **`mean_recall` staying `0.0` in both eras is a corpus calibration property,
  not a reviewer weakness** - see `CALIBRATION.md` and each case's
  `expectation.json` (`"calibrated": false`, permanently, by owner-settled
  design). It is reported here for completeness, not as a quality signal to act
  on.
- **Sample size is small** (5 runs/case/era, 20 attempts total for the two
  target cases): a real capability difference smaller than this sample can
  resolve is not ruled out. What is ruled out, at this sample size, is the
  specific "zero-for-five, zero-referral, confident" pattern v1 reported -
  neither era reproduces that pattern once the grader can see what the reviewer
  actually wrote.

## Spend

| Run                                        | Attempts | Cost (USD)   |
| ------------------------------------------ | -------- | ------------ |
| Post-#53, full 7-case stratum, 5 runs/case | 35       | 3.559636     |
| Pre-#53, 2-case subset corpus, 5 runs/case | 10       | 0.822182     |
| **Total**                                  | **45**   | **4.381818** |

Against the $12.00 ceiling (per #53's issue body and this task's own hard
ceiling): **$4.38 spent, $7.62 headroom remaining, ceiling never approached.**
Re-grading both the 35 post-#53 and 10 pre-#53 attempts with the fixed grader
(`review-suite/scripts/evals/regrade.py`) cost nothing further - no executor
process ran for either re-grade.

## Recommendation (not a decision)

This is a recommendation for the repository owner to weigh, not a decision this
measurement task is authorized to make:

- **On #54:** the evidence #54's provisional status cites (via #59's decision
  record) - two confident, zero-ambiguity misses - does not survive this
  measurement. Both cases resolve correctly under both the pre- and post-#53
  reviewer once the grader can see what was actually written. This measurement
  finds no remaining recall or stability failure on these two cases that would
  justify unblocking #54's independent-discovery architecture; if anything, it
  removes the specific evidence #54's own text says is required before
  proceeding. #54's own "narrow or close this ticket" fallback reads as the
  better-supported path on this evidence, but that determination belongs to the
  repository owner.
- **On #52/#53's original justification (separate from #54):** #59's decision
  record grounded #52's `consumer_impact_evidence` schema and #53's two required
  passes in these same two "confident miss" cases. That grounding is now shown
  to rest on a grader artifact rather than a real capability gap, for these two
  specific cases. This does not mean #52/#53's actual changes are wrong or
  harmful - `consumer_impact_evidence` and `verification_sufficiency_evidence`
  are reasonable, real, structurally sound additions to the review contract
  regardless of whether they closed a measured gap - but their evidentiary
  justification, as recorded, should likely be revisited or reworded by whoever
  owns `DECISION-RECORD.md`. This measurement does not edit that file; it only
  flags the discrepancy for the owner who does.
- **On the grader itself:** the location-only surface-matching blind spot this
  fix closes is not proven to be limited to these two cases. Any other stratum
  or case whose expectation's `surface` field is a symbol name (rather than,
  say, a file path a reviewer would naturally type into `location`) may carry
  the same undetected blind spot. Re-auditing `s2-solution-simplicity-lens` and
  `s3-code-simplicity-lens`'s expectations for this pattern, and considering
  whether v1's baseline itself warrants a disclosed re-score under `1.1` (a
  large, separate undertaking, explicitly out of scope here since it would mean
  touching or superseding `baseline/v1/`), are both reasonable next steps for
  the owner to weigh - not decided or begun here.
