# `s1-correctness-orchestrator` ablation matrix: traversal-only, verification-only, both together (#57)

This is #57's own scored ablation measurement, run against the exact
configuration frozen in
[`FROZEN-V2-CONFIGURATION.md`](FROZEN-V2-CONFIGURATION.md). It reports each
configuration's contribution separately, per #57's own instruction not to
average across configurations. It does not modify `baseline/v1/`,
`gate-manifest.json`, `DECISION-RECORD.md`, `FAILURE-TAXONOMY.md`, or `audits/`.

**Disclosed operating condition.** The two new scored runs below (traversal-
only, verification-only) executed while this shared machine reported very heavy,
unrelated concurrent load (load averages briefly over 190-200, 100% CPU from
other sessions, confirmed not to originate from this task's own ~7 processes).
Neither run produced a single `timeout`, `runtime_failure`, `spawn_failure`,
`output_too_large`, or `malformed_output` attempt (every failure-rate field is
`0.0` in both reports), and observed latency (mean 43.6s / 50.9s, max 74.0s /
87.2s) stayed well under the 300s timeout and did not exceed the reused "both
together" configuration's own historical mean (49.0s). No execution-level
evidence ties the load to a degraded or invalid attempt. This is stated plainly
rather than silently smoothed over, per instruction, precisely because one real
quality regression *was* found below (session-continuation-summary,
verification-only) - it is reported as a finding, not dismissed as a load
artifact, because nothing in the raw attempts or the failure-rate fields
supports that explanation.

## The three configurations

| Configuration                                                                          | `suite_commit`                             | `skill_root`                              | Attempts | Cost (USD) | Mean latency |
| -------------------------------------------------------------------------------------- | ------------------------------------------ | ----------------------------------------- | -------- | ---------- | ------------ |
| Both passes together (reused, scored by a predecessor task at this same skill content) | `2c671fd75f4bc11b3137f8d615764ac6c4e21851` | real `skills/` tree                       | 35       | 3.559636   | 49.04s       |
| Traversal-pass-only (new, this ticket)                                                 | `e2c56f68fe56094a6c92fd4a220539f47d6f9f98` | `ablation-skill-roots/traversal-only/`    | 35       | 3.560108   | 43.62s       |
| Verification-sufficiency-pass-only (new, this ticket)                                  | `e2c56f68fe56094a6c92fd4a220539f47d6f9f98` | `ablation-skill-roots/verification-only/` | 35       | 3.866613   | 50.93s       |

All three: `grader_version 1.1`, `corpus_version 0.1-s1-populated`,
`runs_per_case 5`, `cases 7` (35 attempts), `runtime claude 2.1.92`,
`model claude-opus-4-6[1m]`. Zero evaluation failures of any kind in any of the
three.

## Target-case gate results (settled gate: `mean_recall >= 0.6` OR guarded `mean_combined_recall >= 0.8`, per case independently, per #53's issue body)

| Case                                | Owning mechanism                  | Both together                                 | Traversal-only                                | Verification-only                             |
| ----------------------------------- | --------------------------------- | --------------------------------------------- | --------------------------------------------- | --------------------------------------------- |
| `dependency-strictness-propagation` | #52 schema + #53 traversal pass   | `mean_recall 0.0`, `combined 1.0` -> **PASS** | `mean_recall 0.0`, `combined 1.0` -> **PASS** | `mean_recall 0.0`, `combined 1.0` -> **PASS** |
| `stale-claim-release-guard`         | #53 verification-sufficiency pass | `mean_recall 0.0`, `combined 1.0` -> **PASS** | `mean_recall 0.0`, `combined 1.0` -> **PASS** | `mean_recall 0.0`, `combined 1.0` -> **PASS** |

Both target cases show `verdict_stability`/`finding_stability` of `1.0` in all
three configurations - the v1 floor of `1.0` holds everywhere.

**Mechanically, both passes' preregistered removal-rule condition is satisfied**
(`gate-manifest.json`'s `mechanism_ablations`: "Remove if
`dependency-strictness-propagation` does not move... in this isolated
configuration" / "Remove if `stale-claim-release-guard` does not move... in this
isolated configuration" - neither triggers, since both cases pass in every
configuration, including their own isolated one).

**This is not the whole picture, and reporting only the table above would be the
kind of smoothing this ticket is instructed not to do.** Both target cases pass
**regardless of which single pass is active, or whether either is active at
all**:

- `dependency-strictness-propagation` passes under verification-only, the
  configuration in which the traversal pass - its nominal owning mechanism - is
  explicitly disabled.
- `stale-claim-release-guard` passes under traversal-only, the configuration in
  which the verification-sufficiency pass - its nominal owning mechanism - is
  explicitly disabled.
- This extends, rather than contradicts, `s1-rescore-pre-post-comparison.md`'s
  own already-recorded finding: the **pre-#53 reviewer** (commit `8e4fdbd`,
  before either pass existed as an instruction) already resolved both cases
  5-for-5 under the fixed grader, "without being explicitly instructed to run
  either pass by name."

Taken together (pre-#53 zero-pass baseline, plus both single-pass ablations,
plus the combined configuration), **four independent configurations now show
both target cases resolved, and none of the four demonstrates that either
specific pass's own instruction text is what causes the resolution.** The most
parsimonious explanation consistent with all four data points is that a capable
reviewer, once graded by a grader that can see a symbol named only in prose
(grader `1.1`), already finds both root causes from the packet's raw diff and
repository access alone - independent of whether it is told to run a named
"traversal" or "verification-sufficiency" pass. **Passing the numeric gate is
real; demonstrating this pass's own unique, causal contribution is not** - this
is exactly #57's own "unique contribution beyond earlier mechanisms" reporting
dimension, and it is not satisfied by either pass in isolation, on this
evidence.

## Non-regression floor (all cases, all three configurations)

| Case                              | Requirement                                 | Both together                               | Traversal-only              | Verification-only        |
| --------------------------------- | ------------------------------------------- | ------------------------------------------- | --------------------------- | ------------------------ |
| `dependency-hint-parser-coverage` | 0 false positives                           | 0/5                                         | 0/5                         | 0/5                      |
| `post-bootstrap-module-load`      | 0 false positives                           | 0/5                                         | 0/5                         | 0/5                      |
| `session-continuation-summary`    | 0 false positives                           | 0/4 graded (1 excluded, `malformed_output`) | 0/5                         | **3/5 - FLOOR VIOLATED** |
| `process-isolation-assertion`     | false-alarm rate \<= 2/5 (v1)               | 0/5                                         | 0/5                         | 0/5                      |
| `optional-tool-probe`             | not gated; v1 `mean_recall` 0.2, no ceiling | `mean_recall 0.8`, 0 fp                     | `mean_recall 0.6`, **1 fp** | `mean_recall 1.0`, 0 fp  |

**`session-continuation-summary` regresses under the verification-only
configuration specifically.** 3 of 5 attempts raised a `blocking` finding that
the test covering the finalize-only session path "asserts only on the return
value" and would not catch a regression that deleted the `finalize()` call or
added an accidental `start_agent()` call - a finding shaped exactly like the
verification-sufficiency pass's own intended output, on a case whose expectation
record carries no expected root cause (`expected_root_cause_ids: []`, a
deliberate "correct control"). The grader correctly classifies all three as
false positives/false alarms per the corpus's own ground truth
(`verdict_stability` drops to `0.6`). **This regression does not appear in the
"both passes together" configuration** (0 false positives on this case, matching
v1), so it is not evidence against the combined, already-shipped configuration -
it is evidence that running the verification-sufficiency pass *alone*, without
the traversal pass, makes this reviewer measurably more willing to raise a
marginal test-sufficiency finding on a case designed to have none. No comparable
regression appears under traversal-only.

`optional-tool-probe` is explicitly not gated (`gate-manifest.json`: "re-scoring
must not regress its v1 mean_recall of 0.2 but no target above that is set");
all three configurations exceed that floor. The one false positive under
traversal-only and the perfect score under verification-only are recorded for
completeness, not as a gate result.

## Reused `s2`/`s3` results (unchanged since v1, no ablation applicable - see `s2-s3-grader-1.1-recheck.md` for the full methodology)

| Stratum | Case                                             | `mean_combined_recall` | False positives | Stability |
| ------- | ------------------------------------------------ | ---------------------- | --------------- | --------- |
| s2      | `registry-client-layering`                       | 1.0                    | 0/5             | 1.0 / 1.0 |
| s2      | `setup-service-path-gateway`                     | 1.0                    | 0/5             | 1.0 / 1.0 |
| s3      | `metrics-label-formatting-duplication`           | 1.0                    | 0/5             | 1.0 / 1.0 |
| s3      | `watcher-check-policy-duplication`               | 1.0                    | 0/5             | 1.0 / 1.0 |
| s2      | `reconciliation-outcome-type` (control)          | n/a                    | 0/5             | 1.0 / 1.0 |
| s2      | `record-status-transition-guard` (control)       | n/a                    | 0/5             | 1.0 / 1.0 |
| s3      | `compat-accessor-boundary-duplication` (control) | n/a                    | 0/5             | 1.0 / 1.0 |
| s3      | `env-inventory-bullet-format` (control)          | n/a                    | 0/5             | 1.0 / 1.0 |

All 8 `s2`/`s3` cases replay with identical statuses to their v1 report, per
`gate-manifest.json`'s own non-regression requirement (already verified by
`s2-s3-grader-1.1-recheck.md`; not re-verified here since neither stratum's
prompts or schema consumption are touched by anything in this manifest).

## Cost and latency delta vs. `baseline/v1`'s frozen `s1` figures

`baseline/v1/s1-correctness-orchestrator.report.json`'s own cost/latency figures
are graded under `GRADER_VERSION 1.0` and a different suite commit (`2644c12`);
grading version does not change cost or latency (those are runtime-measured, not
grader-computed), so a same-runtime comparison is valid here. v1's total cost
for the 35-attempt `s1` run was within its $9.00 ceiling; this ticket's own two
new 35-attempt runs cost $3.560 and $3.867 respectively - both below the reused
"both together" run's $3.560 and well below `gate-manifest.json`'s proposed
$12.00 v2 ceiling for this stratum. Mean latency for the two new configurations
(43.6s, 50.9s) is comparable to the reused "both together" run's 49.0s; none
approached its 300s timeout.

## Settled verdict per mechanism (mechanical gate vs. unique-contribution finding)

| Mechanism                                    | Target case                         | Mechanical gate                                                         | Unique contribution demonstrated?                                                                                                    | Non-regression cost found?                                               |
| -------------------------------------------- | ----------------------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------ |
| #53 traversal pass (isolated)                | `dependency-strictness-propagation` | PASS                                                                    | **No** - case also passes with this pass disabled                                                                                    | None found in this configuration                                         |
| #53 verification-sufficiency pass (isolated) | `stale-claim-release-guard`         | PASS                                                                    | **No** - case also passes with this pass disabled                                                                                    | **Yes** - `session-continuation-summary` false-positive regression (3/5) |
| #53 both passes combined (as shipped)        | both                                | PASS                                                                    | Not newly demonstrated by this measurement (see above); no regression to `session-continuation-summary` or any other non-target case | None found                                                               |
| #52 `consumer_impact_evidence` schema        | `dependency-strictness-propagation` | PASS (schema's removal rule is tied to the traversal-pass result above) | Same caveat as the traversal pass above                                                                                              | None found                                                               |

See the closeout report for the recommendation (not a decision) this evidence
supports.
