# `session-continuation-summary` confirming rerun (verification-only, post-#57)

This is a small, bounded, owner-authorized confirming rerun of one finding from
`#57` (PR #88, commit `b4e061f`): under the `verification-sufficiency-pass-only`
ablation configuration, `session-continuation-summary` - a clean control case in
`s1-correctness-orchestrator` with `expected_root_cause_ids: []` - regressed to
`3/5` false positives, while every other tested configuration (including v1)
showed `0/5`. `#57`'s own report (`S1-ABLATION-MATRIX.md`) found no
execution-level evidence tying this to the very heavy, unrelated shared-machine
load present during its run (load averages 190-200; no timeouts, failures, or
abnormal latency), but flagged the result as small-sample (5 attempts) and worth
a confirming rerun before anyone treats it as settled. That is the entire scope
of this record: rerun the one case under the one configuration and report
whether it reproduces. It does not modify `S1-ABLATION-MATRIX.md`,
`FROZEN-V2-CONFIGURATION.md`, `CLOSEOUT-REPORT.md`, `gate-manifest.json`,
`DECISION-RECORD.md`, `FAILURE-TAXONOMY.md`, `audits/`, or `baseline/v1/` - it
adds two new files only (this one and its raw report JSON). It does not decide
anything about `#52`/`#53`'s disposition.

## Method (exact reproduction, per `FROZEN-V2-CONFIGURATION.md`'s "Ablation mechanism")

1. Copied this worktree's real `skills/` tree to a fresh local directory.
2. Overwrote `<copy>/review-correctness/SKILL.md` with the content of the
   committed
   `review-suite/evals/v2/ablation-skill-roots/verification-only/review-correctness/SKILL.md`
   (byte-for-byte; no edits).
3. Built a single-case corpus directory mirroring
   `review-suite/evals/strata/s1-correctness-orchestrator/` but declaring only
   `session-continuation-summary` in `corpus.json` and carrying only that case's
   `reviewer/`, `private/expectations/`, and `private/provenance/` files - a
   targeted confirming rerun of one case, not a re-score of the 7-case stratum.
   `corpus.json`'s other fields (`corpus_version 0.1-s1-populated`,
   `grader_version 1.1`, `target_skill`, `target_skill_dependencies`, `stratum`)
   are carried verbatim from the real stratum corpus, unedited.
4. Ran `review-suite/scripts/evals/runner.py` against that corpus and skill root
   with `--runs 5 --timeout 300` (both matching `FROZEN-V2-CONFIGURATION.md`'s
   pin for the two new ablation runs), the unchanged executor
   (`python3 review-suite/scripts/evals/claude_executor.py`), and no other
   flags.
5. Graded with the grader already pinned in this worktree's `corpus.json`/report
   output: `grader_version 1.1` - the current, fixed grader, same version `#57`
   itself used and the same one `FROZEN-V2-CONFIGURATION.md`'s owner-authorized
   version transition covers.

## Runtime verification

- `claude --version` in this worktree immediately before scoring: `2.1.92`,
  matching `FROZEN-V2-CONFIGURATION.md`'s pinned `runtime_cli_version` exactly.
- `model`: `claude-opus-4-6[1m]` (recorded verbatim in the report's
  `configuration.executor_models`, no `--model` flag passed - same invocation
  shape as the original ablation runs).
- No runtime or model drift from the frozen configuration.

## Result

| Metric                                                                 | Original (`#57`, verification-only, full 7-case stratum) | This rerun (verification-only, this case only) |
| ---------------------------------------------------------------------- | -------------------------------------------------------- | ---------------------------------------------- |
| Attempts                                                               | 5                                                        | 5                                              |
| False positive attempts                                                | **3**                                                    | **3**                                          |
| `verdict_stability`                                                    | 0.6                                                      | 0.6                                            |
| `finding_stability`                                                    | 1.0                                                      | 1.0                                            |
| Evaluation failures (timeout/spawn/runtime/malformed/output-too-large) | 0                                                        | 0                                              |
| Mean latency                                                           | 50.93s (whole stratum)                                   | 60.71s (this case only)                        |
| Max latency                                                            | 87.2s (whole stratum)                                    | 73.997s                                        |
| Cost                                                                   | $3.866613 (whole 7-case, 35-attempt stratum)             | $0.569074 (this case, 5 attempts)              |

**This reproduces exactly: 3 of 5 attempts, the same count as the original
run.** Directly observed in each reproducing attempt's raw output during this
run (the committed report JSON carries only aggregate `per_case`/`quality`
figures, not per-attempt finding IDs, so this specific detail is reported from
first-hand observation rather than as something re-derivable from the committed
JSON alone): the false-positive finding in every reproducing attempt was the
same shape as originally reported - finding_id `corr.verify-finalize-called`, a
`blocking` finding that the test covering the finalize-only session path
"asserts only on the return value" and would not catch a regression that deleted
the `finalize()` call or added an accidental `start_agent()` call - raised
against a case whose expectation record carries no expected root cause
(`expected_root_cause_ids: []`, a deliberate clean control). The two
non-reproducing attempts returned `clean`, matching the case's expected verdict.

No attempt in this rerun produced a `timeout`, `spawn_failure`,
`runtime_failure`, `output_too_large`, or `malformed_output` classification
(every failure-rate field is `0.0`); observed latency (mean 60.71s, max 73.997s)
stayed well under the 300s timeout. This machine was not confirmed free of
concurrent load during this rerun, but the result is unchanged from the original
regardless: the regression reproduces at the same rate under a fresh,
independent set of 5 attempts.

## Interpretation

The original finding **reproduces**. This confirming rerun does not support the
hypothesis that the `3/5` false-positive rate was a shared-machine-load artifact
of `#57`'s own run - a second, independent set of 5 attempts, run at the pinned
runtime/model version, against the identical ablation mechanism and case, again
resolves `3/5`. Per instruction, this record states the number plainly (`3/5`,
matching the original `3/5`) rather than characterizing it as "confirming" a
specific causal theory beyond that: it is evidence the regression is a real,
repeatable property of the verification-sufficiency-pass-only configuration on
this case, not disappearing under a clean rerun.

This record does not decide what should happen to the
verification-sufficiency-pass-only configuration, `#52`, or `#53` as a result.
See `S1-ABLATION-MATRIX.md`'s and the closeout report's own settled verdicts and
recommendations for that.

## Suite commit note

This rerun's own `configuration.suite_commit` (recorded verbatim in the raw
report JSON) is this worktree's `HEAD` at run time,
`b4e061f7847b3fc911a05fe4c8e50218f4f957b7` (`#57`/PR #88's own merge commit) -
later than the original ablation run's
`e2c56f68fe56094a6c92fd4a220539f47d6f9f98`, since this rerun necessarily runs
after `#57` merged. The real `skills/` tree's four target-skill-closure
documents other than the overlaid `review-correctness/SKILL.md` are unchanged
between those two commits. `configuration.target_skill_digest` differs from the
original verification-only report's own recorded digest (`6e05fb283aa9ed69` here
vs. `d85efbc6381a2775` there); this is expected and already disclosed by
`FROZEN-V2-CONFIGURATION.md`'s "Ablation mechanism" section, which notes the
committed overlay file was reformatted by `just fmt-md` *after* the original
scored runs launched (rewrapped line breaks only, no textual change,
independently re-diffed there against the committed file). This rerun built its
skill root from the overlay file's current, already-reformatted, committed
content, so its digest reflects the post-reformat bytes; the original run's
digest reflects the pre-reformat bytes. Neither digest difference reflects any
change in reviewer-visible instruction content.

## Cost ceiling

- This ticket's own hard ceiling: **$1.00**.
- Actual spend: **$0.569074** (5 attempts, one case, one configuration) - the
  only real-money spend this ticket incurred.

## Raw evidence

The full raw report (including per-attempt cost, latency, grading detail, and
the exact `configuration` block reproduced above) is committed alongside this
record at
[`session-continuation-summary-confirming-rerun.report.json`](session-continuation-summary-confirming-rerun.report.json).
