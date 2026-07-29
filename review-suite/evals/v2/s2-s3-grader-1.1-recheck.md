# `s2-solution-simplicity-lens` and `s3-code-simplicity-lens`: does the grader `1.1` fix reach here too?

This is a follow-up recheck to `GRADER-1.1-COMPARABILITY.md` and
`s1-rescore-pre-post-comparison.md` in this directory. Those two records fixed a
real defect in `finding_surfaces()` (only structured `location` fields were
tokenized for a surface match; a symbol named only in a finding's prose was
invisible to the grader) and showed it turned two `s1-correctness-orchestrator`
cases' frozen v1 "confident miss" into a grader artifact. `s2` and `s3` were
never touched by that measurement - #53 only changed `review-correctness` - so
this task independently checks whether the same defect reaches these two
strata's four material cases. **It does not modify `baseline/v1/`,
`gate-manifest.json`, `DECISION-RECORD.md`, `FAILURE-TAXONOMY.md`, or `audits/`;
it adds new files only.**

## Step 1: does v1's raw attempt data survive anywhere on this machine?

No. Searched directly (file name, Spotlight, and the artifact-path convention
`review-suite/evals/artifacts/<stratum>/<commit>-<corpus_version>/` that
`runner.py`'s `_artifact_stem` and `CALIBRATION.md` document) across `/Users`,
`/private/tmp`, and `/var/folders`. The only surviving `evals/artifacts/`
content anywhere on this machine belongs to the unrelated pilot strata
(`pilot-orchestrator`, `pilot-code-simplicity`, `pilot-solution-simplicity`, all
for the `rollback-guidance-render` / `status-label-normalization` pilot cases)
in a different worktree - nothing for `s2-solution-simplicity-lens` or
`s3-code-simplicity-lens`'s actual material cases. This matches `s1`'s
documented pattern exactly: `evals/artifacts/` is git-ignored, and no prior
task's raw output for these two strata was ever committed anywhere. Re-grading
v1 for free was not possible; a fresh run was required, as expected.

## Step 2 and 3: fresh run under the fixed grader, and what changed

Both lenses (`review-solution-simplicity`, `review-code-simplicity`) are
unchanged since v1 - no `#51`-`#57` child touched either skill - so this is a
direct single-era comparison, not a pre/post split like `s1` needed.

**Runtime/model verified unchanged before launch** (per `gate-manifest.json`'s
`runtime_model_stratum` stratum rule): `claude --version` reports `2.1.92`,
matching the pin exactly; a one-line sanity call confirmed the CLI's default
model (no `--model` flag passed, matching how the executor was invoked) still
resolves to `claude-opus-4-6[1m]`, also matching the pin exactly. No new,
non-comparable runtime/model stratum was created.

Invocation (identical pattern to `s1`'s rescore, `runs_per_case` and `timeout`
both unchanged from `gate-manifest.json`'s original v1 values since neither
stratum's timeout needed raising):

```
just eval-review-suite "python3 review-suite/scripts/evals/claude_executor.py" \
  --corpus review-suite/evals/strata/<s2-or-s3-stratum> \
  --runs 5 --timeout 300 \
  --artifact-dir review-suite/evals/artifacts/<stratum>/a247d47-<corpus_version> \
  --attempts-out review-suite/evals/artifacts/<stratum>/a247d47-<corpus_version>.attempts.jsonl \
  --report-out review-suite/evals/v2/<stratum>.report.json
```

`suite_commit` recorded in both reports:
`a247d47d51eee9513b3431fc59ba34afe9316bfb` (`origin/main`'s head at launch time
\- the grader-fix merge commit itself). 40 attempts total (20/stratum), all
graded, zero evaluation failures (`blocked_rate`, `malformed_output_rate`,
`runtime_failure_rate`, etc. all `0.0` in both reports),
`verdict_stability`/`finding_stability` `1.0` for every one of the 8 cases.

### The four numbers, v1 (frozen) vs. this recheck (fixed grader)

| Case                                   | Stratum | v1 `mean_recall` | v1 `false_positive_attempts` | v1 `ever_referred` | v2 `mean_recall` | v2 `mean_combined_recall` | v2 `false_positive_attempts` |
| -------------------------------------- | ------- | ---------------- | ---------------------------- | ------------------ | ---------------- | ------------------------- | ---------------------------- |
| `registry-client-layering`             | s2      | 0.0              | 0/5                          | non-empty          | 0.0              | **1.0**                   | 0/5                          |
| `setup-service-path-gateway`           | s2      | 0.0              | **4/5**                      | non-empty          | 0.0              | **1.0**                   | **0/5**                      |
| `metrics-label-formatting-duplication` | s3      | 0.0              | 0/5                          | non-empty          | 0.0              | **1.0**                   | 0/5                          |
| `watcher-check-policy-duplication`     | s3      | 0.0              | 0/5                          | non-empty          | 0.0              | **1.0**                   | 0/5                          |

`mean_recall` stays `0.0` in both eras for the same reason it does in `s1`:
every one of these four cases is permanently `calibrated: false`
(`CALIBRATION.md`), so a real reviewer's paraphrase essentially never contains
one of the pre-written `equivalent_formulations` verbatim.
`mean_combined_recall` did not exist as a field in v1's report schema at all
(`report_version: 1.0`, before the relevance-guard mechanism that produces this
field existed) - so "did it change from v1" is answered by "v1 never measured
it," and the honest comparison is the classification each grader era assigns,
not a numeric delta on a field only one era has.

### Direct verification, not just a before/after report diff

The single most important check this task ran, and the one a bare report
comparison would have missed: **re-grading this run's own freshly captured raw
attempts
(`review-suite/evals/artifacts/{s2,s3}-*/a247d47-0.1-*-populated/*.stdout.json`,
retained on disk right now, not the frozen v1 baseline) with the grader exactly
as it stood at commit `85ccf13` (`a247d47`'s parent, `GRADER_VERSION 1.0`, no
`surface_named_in_prose`, no `combined_recall`/relevance-guard field at all)
against the same 20 attempts/stratum the current grader just scored.** This
required writing a small one-off script (not committed - it duplicates no
shipped tool, it only proves a point once) that imports the extracted `85ccf13`
`grader.py` as a second module alongside the current one and calls both
`grade()` functions on the same retained `result` payload per attempt. This
directly answers "does the `1.1` fix change anything here," rather than
inferring it from two reports built by two different graders on two different
sample sets.

**Three of the four cases show no material difference at all.**
`registry-client-layering`, `metrics-label-formatting-duplication`, and
`watcher-check-policy-duplication`: every one of their 15 fresh attempts (5
each) was *already* classified `referred` by the `85ccf13` grader, with zero
false positives - identical in kind to what v1 itself reported for these three
cases. The only thing that changes for these three under `1.1` is that
`combined_recall` (a metric the old grader could not compute at all) now
resolves the already-correct referral to `1.0` automatically instead of
requiring a human adjudicator to confirm it, exactly as `s1`'s comparison
document already noted was possible even for a correctly-functioning referred
path. This is a real, disclosed change in *mechanism* but not evidence these
three cases were ever measured wrong.

**`setup-service-path-gateway` is materially, concretely affected by the same
defect s1's two cases had - not the "fully blind, zero-referral" form, but the
same underlying mechanism, at the referred-vs-false-positive boundary.** Under
the `85ccf13` grader, only 2 of this run's 5 fresh attempts (runs 1 and 4) were
classified `referred`; the other 3 (runs 2, 3, 5) were classified as pure,
unrelated **false positives** - `old_referred: []`,
`old_false_positive_finding_ids: ['ss.speculative-gateway-and-dep-bag']` /
`['sol.unnecessary-gateway-and-dep-bag']` /
`['ss.unnecessary-gateway-and-dep-bag']` respectively. Reading the retained raw
`location` fields for exactly these five attempts explains why: runs 1 and 4
happen to write `services/setup.py:SetupPathGateway` as a `location` string (the
expected `surface`, `SetupPathGateway`, literally appears after the colon), so
the old grader's plain location-tokenization already matched it by coincidence.
Runs 2, 3, and 5 write only generic locations - `services/setup.py (diff)`,
`services/setup.py:4-15`, `services/setup.py`, `commands/setup.py` - and name
`SetupPathGateway` only in the finding's `concern`/`evidence[].detail` prose,
exactly the pattern `surface_named_in_prose()` was built to catch. The fixed
(`1.1`) grader correctly reclassifies all 5 of these runs as `referred` with
`combined_recall: 1.0` and zero false positives.

**This closely mirrors v1's own reported number for this exact case**
(`false_positive_attempts: 4/5`, only one adjudication-required referral
recorded) far more closely than it mirrors the "everything was already fine"
pattern the other three cases show. v1's own raw attempts do not survive (see
Step 1), so this cannot be proven attempt-by-attempt for v1 the same way it was
just proven for this run's own fresh attempts - but the mechanism, the
expectation file (`surface: "SetupPathGateway"`, unchanged since v1), and the
resulting shape (mostly-false-positive, occasionally-referred) are the same code
and the same case v1 measured. **The well-evidenced inference is that v1's own
`4/5` false-positive rate for `setup-service-path-gateway` was itself
substantially inflated by this same grader defect**, not a demonstrated reviewer
false-alarm tendency - the same caveat-qualified conclusion
`s1-rescore-pre-post-comparison.md` reached for its own two target cases, at the
same evidentiary strength (mechanism-and-expectation match, not a re-graded v1
artifact).

## Step 4: non-regression floor on the negative controls

| Case                                   | Stratum | v1 `false_positive_attempts` | v2 `false_positive_attempts` | v1/v2 `verdict_stability`, `finding_stability` |
| -------------------------------------- | ------- | ---------------------------- | ---------------------------- | ---------------------------------------------- |
| `reconciliation-outcome-type`          | s2      | 0/5                          | 0/5                          | 1.0 / 1.0 (both eras)                          |
| `record-status-transition-guard`       | s2      | 0/5                          | 0/5                          | 1.0 / 1.0 (both eras)                          |
| `compat-accessor-boundary-duplication` | s3      | 0/5                          | 0/5                          | 1.0 / 1.0 (both eras)                          |
| `env-inventory-bullet-format`          | s3      | 0/5                          | 0/5                          | 1.0 / 1.0 (both eras)                          |

All four clean/negative controls hold exactly unchanged: zero false positives in
both eras, perfect stability in both eras. No regression.

## What this means, plainly

- **The grader defect's reach is not limited to the two `s1` cases already
  fixed.** It also affected `setup-service-path-gateway`'s false-positive rate
  in `s2` - a real, concrete effect on a real number in the frozen v1 baseline,
  evidenced directly (not merely inferred) via a same-attempts,
  two-grader-versions counterfactual.
- **It does not change any of the four material cases' fundamental
  classification from "missed" to "found."** Unlike `s1`'s two cases (which went
  from zero-referral confident misses to fully confirmed matches), all four
  `s2`/`s3` cases were already correctly routed to the `referred` adjudication
  path in the large majority of attempts under the old grader, in every case
  except the specific `setup-service-path-gateway` runs identified above. A
  human adjudicator reviewing v1's `adjudication_required` list (which includes
  `setup-service-path-gateway` run 5 and multiple `registry-client-layering`
  runs) would have seen and could have confirmed the correct root cause even
  under the old grader, for the referred subset - this was never the "silent,
  nobody-ever-looked" failure mode `s1`'s two target cases were.
- **The one exception is real and should not be smoothed into "s2/s3 hold up
  unchanged."** `setup-service-path-gateway`'s reported `4/5` false-positive
  rate in the frozen v1 baseline is, on this evidence, largely a grader artifact
  rather than a demonstrated reviewer false-alarm tendency - the same category
  of correction as `s1`'s two cases, at a different point in the grading
  pipeline (false-positive misclassification rather than a complete silent
  miss).
- **The three other material cases, and all four negative controls, hold up as
  originally reported**, with the fixed grader now able to confirm their
  already-correct referrals automatically instead of only via human
  adjudication.

## Spend

| Run                                                        | Attempts | Cost (USD)   |
| ---------------------------------------------------------- | -------- | ------------ |
| `s2-solution-simplicity-lens`, 4-case stratum, 5 runs/case | 20       | 1.190071     |
| `s3-code-simplicity-lens`, 4-case stratum, 5 runs/case     | 20       | 0.958775     |
| **Total**                                                  | **40**   | **2.148846** |

Against this task's own $5.00 hard ceiling: **$2.15 spent, $2.85 headroom
remaining, ceiling never approached.** (One additional trivial one-line
`claude -p` sanity call, made only to confirm the CLI's default model/version
still matches the `gate-manifest.json` pin before launching any scored run, cost
a negligible fraction of a cent and is not reflected in the table above since it
produced no graded attempt.) The `85ccf13`-grader counterfactual re-grade in
this document's "Direct verification" section spent nothing further - no
executor process ran for it, exactly like `regrade.py`'s existing free
re-grading path.

## What this does not do

- Does not touch `baseline/v1/`, `gate-manifest.json`, `DECISION-RECORD.md`,
  `FAILURE-TAXONOMY.md`, or `audits/` - all remain exactly as `#58`/`#59`
  delivered them.
- Does not re-run or touch `s1-correctness-orchestrator` - already covered by
  `s1-rescore-pre-post-comparison.md`.
- Does not decide anything about `#52`, `#53`, `#54`, or any other ticket's
  disposition. It reports what the fixed grader shows for `s2`/`s3`; any policy
  consequence is for the repository owner to weigh.
