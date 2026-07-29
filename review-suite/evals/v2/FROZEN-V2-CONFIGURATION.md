# Frozen v2 scored configuration (#57)

This record freezes the exact configuration `#57` scored against, before any of
its own scored output was examined, per `gate-manifest.json`'s own rule ("frozen
the moment any scored v2 output for the affected stratum is examined"). It does
not modify `gate-manifest.json`, `DECISION-RECORD.md`, `FAILURE-TAXONOMY.md`,
`audits/`, or `baseline/v1/` - all remain exactly as `#58`/`#59` delivered them.
It adds one new file only.

## Grader version transition (reviewed, explicitly owner-authorized)

`gate-manifest.json` preregistered its thresholds against the grader as it stood
before `finding_surfaces()`'s real defect (location-only surface matching; a
symbol named only in a finding's prose was invisible to the grader) was found
and fixed. That fix, its cause, and its version-comparability consequence are
documented in [`GRADER-1.1-COMPARABILITY.md`](GRADER-1.1-COMPARABILITY.md); its
effect on the two `s1` target cases (pre-#53 and post-#53, both under the fixed
grader) is documented in
[`s1-rescore-pre-post-comparison.md`](s1-rescore-pre-post-comparison.md); its
effect on `s2`/`s3` is documented in
[`s2-s3-grader-1.1-recheck.md`](s2-s3-grader-1.1-recheck.md).

**The repository owner has explicitly authorized running #57's own scored
comparison against the fixed (`1.1`) grader, not the original (`1.0`) grader
that `gate-manifest.json` was preregistered against.** This is the "reviewed
version transition" #57's own body requires before deviating from a frozen
input, and the three documents above are its evidentiary trail: a real,
disclosed defect was found mid-measurement by a predecessor task, fixed under an
existing, unrelated calibration constraint (the
`probe.partial-claim-wrong- surface` case had to keep passing), and the fix's
reach was independently verified against retained raw attempts for both `s1`'s
two target cases and all four `s2`/`s3` material cases before this ticket ran a
single further scored attempt. Every scored result in this record and in `#57`'s
closeout report is graded under grader `1.1`. Per the comparability rule those
three documents establish, no figure here is compared directly against any
`1.0`- graded figure, including `baseline/v1/`'s own frozen numbers, without
saying so explicitly.

## Runtime/model stratum (verified unchanged, matches `gate-manifest.json`'s pin exactly)

- `runtime`: `claude` (Claude Code CLI)
- `runtime_cli_version`: `2.1.92` - verified via `claude --version` immediately
  before scoring began
- `model`: `claude-opus-4-6[1m]` - verified via one negligible-cost (`$0.00904`)
  sanity call reading the CLI's own `modelUsage` reporting, with no `--model`
  flag passed, exactly matching how the executor invokes it
- No runtime, runtime-version, or model drift was detected. Per
  `gate-manifest.json`'s stratum rule, scoring proceeded; had drift been
  detected, this ticket would have returned `blocked` instead.

## Suite commit and corpus/grader versions

| Configuration                                               | `suite_commit`                             | `corpus_version`                  | `grader_version` | `skill_root`                                                                                        |
| ----------------------------------------------------------- | ------------------------------------------ | --------------------------------- | ---------------- | --------------------------------------------------------------------------------------------------- |
| `s1`, both passes together (reused, not re-run - see below) | `2c671fd75f4bc11b3137f8d615764ac6c4e21851` | `0.1-s1-populated`                | `1.1` (regraded) | real `skills/` tree (unablated)                                                                     |
| `s1`, traversal-pass-only (new)                             | `e2c56f68fe56094a6c92fd4a220539f47d6f9f98` | `0.1-s1-populated`                | `1.1`            | `review-suite/evals/v2/ablation-skill-roots/traversal-only/` overlaid on the real `skills/` tree    |
| `s1`, verification-sufficiency-pass-only (new)              | `e2c56f68fe56094a6c92fd4a220539f47d6f9f98` | `0.1-s1-populated`                | `1.1`            | `review-suite/evals/v2/ablation-skill-roots/verification-only/` overlaid on the real `skills/` tree |
| `s2-solution-simplicity-lens` (reused, not re-run)          | `a247d47d51eee9513b3431fc59ba34afe9316bfb` | `1.3-pilot-solution-simplicity`\* | `1.1`            | real `skills/` tree                                                                                 |
| `s3-code-simplicity-lens` (reused, not re-run)              | `a247d47d51eee9513b3431fc59ba34afe9316bfb` | `1.3-pilot-code-simplicity`\*     | `1.1`            | real `skills/` tree                                                                                 |

\*See each report's own `configuration.corpus_version` for the exact string;
restated here from the committed report files, not retyped from memory.

**Reuse rationale for "both passes together," `s2`, and `s3`:** these three
configurations were already scored under grader `1.1` by predecessor measurement
tasks in this same epic (`s1-rescore-pre-post-comparison.md`'s "post-#53, full
7-case stratum" run; `s2-s3-grader-1.1-recheck.md`'s full-stratum runs), against
a `suite_commit` whose `skills/review-code-change`,
`skills/review-solution-simplicity`, `skills/review-correctness`, and
`skills/review-code-simplicity` trees are byte-identical to this ticket's own
`suite_commit` (`e2c56f6`) for every file those runs actually evaluated - this
ticket's own diff touches only `review-suite/scripts/evals/runner.py`, its own
tests, and two new eval-only fixture files outside `skills/`, none of which are
part of the target skill closure any scored run sends to a reviewer. Re-running
either configuration would spend real money to reconfirm a result no code change
since the prior run could have altered. `gate-manifest.json`'s non-regression
floor for `s2`/`s3` ("all 8 cases must replay with identical statuses to their
v1 report") was already checked by `s2-s3-grader-1.1-recheck.md`; this record
does not repeat that check.

## Executor and suite configuration

- `executor_command`: `python3 review-suite/scripts/evals/claude_executor.py`
- `process_isolation`: one fresh executor process per attempt (unchanged from
  v1)
- `runs_per_case`: `5` (unchanged from `gate-manifest.json`, for v1/v2
  comparability)
- `retry_policy`: none (a failed attempt is an evaluation failure, never
  retried)
- `timeout_seconds`: `300` for the two new ablation runs, matching
  `gate-manifest.json`'s own (unconditionally applicable) pin. Disclosed
  methodology note: the earlier "both passes together" run this record reuses
  used `450s` (a separate, `#53`-issue-body-specific override, itself never
  approached: observed max latency across that run was `116.6s`). Neither
  timeout was approached by any attempt in any of the three configurations (see
  per-configuration latency tables below), so this difference is disclosed for
  completeness and does not affect comparability of the reported figures.
- `max_output_bytes`: default (`4,000,000`), unchanged

## Ablation mechanism

The shipped `review-correctness` skill performs both required passes
(consumer/impact-traversal; verification-sufficiency) unconditionally on every
review, by design (`skills/review-correctness/SKILL.md`: "not routed specialist
modules"). To score each pass in isolation without adding a runtime toggle to
the shipped skill, this ticket adds an optional `--skill-root` override to
`review-suite/scripts/evals/runner.py` (default: the real `skills/` tree, so
every existing caller and report is unaffected) and two eval-only
`review-correctness/SKILL.md` overlays under
`review-suite/evals/v2/ablation-skill-roots/{traversal-only,verification-only}/`,
each disabling exactly one required pass with an explicit no-op instruction.
Every other file in each ablation root is byte-identical to the real `skills/`
tree (verified directly via `diff -rq` before each scored run). The resolved
`skill_root` is recorded verbatim in every report's `configuration.skill_root`
field, so an ablation run can never be mistaken for a standard-configuration
one. See `review-suite/scripts/evals/runner.py`'s `target_skill_documents`
docstring and `review-suite/scripts/tests/test_eval_runner.py`'s
`test_an_overridden_skill_root_is_recorded_and_changes_the_closure` for the
mechanism's own tests.

## Cost ceiling

- This ticket's own hard ceiling: **$20.00** for its scored evaluation.
- `gate-manifest.json`'s per-stratum proposed ceilings: `s1` $12.00, `s2` $3.00,
  `s3` $3.00 (all unchanged, all preregistered before any v2 output was
  examined).
- Actual total spend against this ticket's own $20.00 ceiling: see the closeout
  report's spend table. The two new scored runs (traversal-only,
  verification-only) are the only real-money spend this ticket itself incurred;
  the reused "both passes together," `s2`, and `s3` figures were paid for by
  predecessor measurement tasks in this epic and are not counted a second time
  against this ticket's own ceiling.

## Invalid runs, missing data, and threshold-change discipline

Unchanged from `gate-manifest.json`: an attempt classified
`spawn_failure`/`timeout`/`runtime_failure`/`output_too_large`/
`malformed_output`/`protocol_mismatch` is never graded and never silently
retried. Every quality/stability/non-regression threshold in
`gate-manifest.json`'s `quality_stability_non_regression_thresholds` section,
and the settled per-case gate from `#53`'s own issue body (`mean_recall >= 0.6`
OR guarded `mean_combined_recall >= 0.8`, per case independently), was fixed
before this ticket examined any of its own scored output. No threshold was tuned
after seeing a result.
