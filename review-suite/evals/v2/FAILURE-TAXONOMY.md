# v1 failure taxonomy

`taxonomy_version: 1.0`. Classifies every material outcome in the frozen v1
baseline (`review-suite/evals/baseline/v1/*.report.json`, suite commit
`2644c12`, `v1_review_behaviour_commit`
`16560d807c66076fcbf3f00d3a87f543c6ae2458`) by the smallest evidenced cause.
Read [`LIMITATIONS.md`](../baseline/v1/LIMITATIONS.md) beside this document;
every classification below cites the exact `per_case` field it rests on, and
every cited figure was independently re-read from the committed report JSON
while writing this document, not copied from an earlier summary.

This taxonomy answers one question per case: is the outcome reviewer,
evidence/rubric, grader/corpus, or runtime/tooling behavior? It does not
prescribe a mechanism; that is [`DECISION-RECORD.md`](DECISION-RECORD.md)'s job,
and it only proposes a mechanism for a cause classified here as reviewer
behavior with a demonstrated, repeatable (`mean_recall: 0.0`,
`ever_referred_root_cause_ids: []`) shape.

## Category vocabulary

Each case is tagged with one primary category from #59's own list, then rolled
up into one of the five acceptance-criterion buckets: **reviewer**,
**evidence/rubric**, **grader/corpus**, or **runtime/tooling**. A case with no
expected root cause and no false-positive/false-alarm attempts is recorded as a
**correct control**, not a failure, but is still listed so every material
outcome in the frozen reports is accounted for.

## s1-correctness-orchestrator (7 cases, 5 attempts each, 35 attempts total)

| case                                | outcome                 | primary category                                                      | bucket                                    |
| ----------------------------------- | ----------------------- | --------------------------------------------------------------------- | ----------------------------------------- |
| `dependency-hint-parser-coverage`   | correct control         | —                                                                     | reviewer (correct)                        |
| `dependency-strictness-propagation` | confident miss          | weak change/consumer/negative-space traversal                         | reviewer                                  |
| `optional-tool-probe`               | mixed partial           | domain-specific reasoning miss, compounded by grader/corpus ambiguity | reviewer + grader/corpus (undisentangled) |
| `post-bootstrap-module-load`        | correct control         | —                                                                     | reviewer (correct)                        |
| `process-isolation-assertion`       | false-alarm instability | stochastic search-order or anchoring failure                          | reviewer                                  |
| `session-continuation-summary`      | correct control         | —                                                                     | reviewer (correct)                        |
| `stale-claim-release-guard`         | confident miss          | failure to test verification sufficiency                              | reviewer                                  |

**`dependency-strictness-propagation`** — `mean_recall: 0.0`,
`ever_referred_root_cause_ids: []`, `false_positive_attempts: 5/5`,
`finding_stability`/`verdict_stability: 1.0`. Root cause
`rc.sibling-call-site-keeps-permissive-mode`: the change hardens one caller of
`dependency_finalized` and leaves a sibling caller on the permissive path; the
added tests exercise only the hardened caller. Confirmed independently against
`review-suite/evals/strata/s1-correctness-orchestrator/private/expectations/dependency-strictness-propagation.json`.
Zero ambiguity across all 5 attempts: a repeatable, demonstrated failure to
traverse to a sibling consumer of a changed shared contract. Classified **weak
change/consumer/negative-space traversal**, not verification-sufficiency,
because the reviewer never reasoned about the second call site at all — the gap
is discovery, not test-adequacy judgment (the added test's narrowness is a
compounding symptom of the same missed traversal, not an independent cause).

**`stale-claim-release-guard`** — `mean_recall: 0.0`,
`ever_referred_root_cause_ids: []`, `false_positive_attempts: 5/5`, stability
1.0/1.0. Root cause `rc.guard-skipped-when-snapshot-owner-absent`: the ownership
check in `_release` is conditional on the snapshot having had an owner, so the
exact scan-then-claim interleaving the change exists to guard against skips the
comparison and releases a live claim. Confirmed against the same expectations
directory. The added test "starts from an owned entry, so it exercises the
branch that was already safe and passes" — the reviewer accepted a passing,
happy-path test as sufficient evidence for a concurrency/ownership edge case it
never exercised. Classified **failure to test verification sufficiency**, not
traversal — the miss is single-file and single-function; no consumer walk would
have found it, only asking whether the test could actually fail for this trigger
would have.

**`optional-tool-probe`** — `mean_recall: 0.2` (1 of 5 attempts fully matched),
`ever_referred_root_cause_ids: ['rc.probe-checks-status-not-absence']`,
`finding_stability: 0.8`, `verdict_stability: 1.0`. Root cause: the probe checks
the tool's status rather than its absence, so a missing executable raises
instead of skipping, and the failure only reproduces on the one environment (CI)
the skip exists for. Unlike the two confident misses, this case is **not**
zero-ambiguity: one attempt matched fully, and it is a genuine domain-specific
reasoning question (does a status check detect absence?) rather than a pure
traversal or verification-sufficiency gap. Because 4 of 5 attempts landed in the
referred bucket rather than a flat miss, and because `LIMITATIONS.md` items 3–4
document that the reference grader's containment matching and one-token surface
rule systematically under-recognize a correctly identified finding phrased a
fifth way, this case's true reviewer-behavior component cannot be cleanly
separated from a grader/corpus confound with only 5 attempts. **This case does
not, by itself, justify a new mechanism** and is not cited as evidence for any
#51–#57 disposition; it is recorded as an open question for whoever next
calibrates or recalibrates this expectation, per #59's own instruction not to
prescribe a change until a failure is separated from grader and corpus defects.

**`process-isolation-assertion`** — a negative control
(`expected_root_cause_ids: []`), re-raised in 2 of 5 attempts
(`false_alarm_attempts: 2`, `verdict_stability: 0.6`), while every other clean
control in this stratum scored `verdict_stability: 1.0`. The underlying
observation (a test named for process freshness actually asserts executor
identity) was adjudicated not material because the packet states no process
identifier is observable at all and the assertion is the strongest available
proxy — but LIMITATIONS.md item 15 also records that this case's first
adjudication came from the review suite under evaluation itself, which is weaker
evidence than an independent human disposition. Classified **stochastic
search-order or anchoring failure**: the same packet and prompt produced a
stable `blocking`/`strong_recommendation` re-raise on 2 of 5 independent fresh
processes and a correct pass on the other 3, with no change in evidence between
attempts. This is real, repeatable verdict instability on an already-adjudicated
finding, not a corpus or grader artifact — the case is not evidence for a new
mechanism, but it is evidence that a v2 gate must keep measuring false-alarm
stability on adjudicated-rejected findings rather than assuming the current
suite already has zero false-alarm risk.

**Correct controls** (`dependency-hint-parser-coverage`,
`post-bootstrap-module-load`, `session-continuation-summary`): all three have
`expected_root_cause_ids: []`, `false_positive_attempts: 0`, and
`verdict_stability: 1.0`. Each pairs a real adjudicated-not-material observation
(recorded as an `accepted_non_finding` in its expectations file) with a reviewer
that correctly declined to gate on it in all 5 attempts. No failure of any kind;
recorded here only so every case in the stratum is accounted for.

## s2-solution-simplicity-lens (4 cases, 5 attempts each, 20 attempts total)

| case                             | outcome              | primary category        | bucket             |
| -------------------------------- | -------------------- | ----------------------- | ------------------ |
| `reconciliation-outcome-type`    | correct control      | —                       | reviewer (correct) |
| `record-status-transition-guard` | correct control      | —                       | reviewer (correct) |
| `registry-client-layering`       | referred, not missed | grader/corpus ambiguity | grader/corpus      |
| `setup-service-path-gateway`     | referred, not missed | grader/corpus ambiguity | grader/corpus      |

Both material cases show `mean_recall: 0.0` with a non-empty
`ever_referred_root_cause_ids` that names the expected root cause exactly
(`rc.three-client-concepts-duplicate-binding` for `registry-client-layering`,
`rc.gateway-abstracts-a-pure-function-with-one-implementation` for
`setup-service-path-gateway`). Per the owner-settled three-way grading method
(`LIMITATIONS.md` item 14) and the deliberate-non-calibration policy for scored
cases, a referral this consistent — the grader recognizes the finding's surface
and root cause every time but the shipped formulation never matches the
reviewer's actual prose — is the corpus/grader behaving exactly as designed for
an intentionally uncalibrated scored expectation, not a demonstrated reviewer
defect. **Neither case is treated as evidence of a solution-simplicity lens
failure.** `setup-service-path-gateway` additionally shows
`false_positive_attempts: 4/5`; this is not independently confirmed as a
distinct false-alarm defect — `LIMITATIONS.md` items 3–4 document the same
containment/one-token confound producing exactly this shape — and is recorded
here as an open measurement question for the corpus/grader owner, not folded
into any #51–#57 disposition.

The two correct controls (`reconciliation-outcome-type`,
`record-status-transition-guard`) both show `expected_root_cause_ids: []`, zero
false positives, and `verdict_stability: 1.0` across all 5 attempts:
requirement-justified near-misses the lens correctly left clean.

## s3-code-simplicity-lens (4 cases, 5 attempts each, 20 attempts total)

| case                                   | outcome                                   | primary category                                     | bucket             |
| -------------------------------------- | ----------------------------------------- | ---------------------------------------------------- | ------------------ |
| `compat-accessor-boundary-duplication` | correct control                           | —                                                    | reviewer (correct) |
| `env-inventory-bullet-format`          | correct control, low discriminating power | rubric ambiguity or overbreadth (measurement design) | evidence/rubric    |
| `metrics-label-formatting-duplication` | referred, not missed                      | grader/corpus ambiguity                              | grader/corpus      |
| `watcher-check-policy-duplication`     | referred, not missed                      | grader/corpus ambiguity                              | grader/corpus      |

`metrics-label-formatting-duplication` and `watcher-check-policy-duplication`
both show `mean_recall: 0.0` with `ever_referred_root_cause_ids` matching their
expected root cause exactly (`rc.label-expression-copied-into-two-new-functions`
and `rc.local-policy-duplicated-across-call-sites`), zero false positives. Same
disposition as the s2 pair: intentionally uncalibrated scored expectations
behaving as designed, not a demonstrated code-simplicity lens defect.

`metrics-label-formatting-duplication` (this stratum's case 7) and s2's
`registry-client-layering` (case 3) trace to the same source PR comment read at
two levels (`LIMITATIONS.md` item 32, confirmed by the owner). **Their recall
figures are correlated, not independent, and must never be combined or presented
as two independent samples in any aggregate figure this decision record or the
v2 gate manifest reports.**

`env-inventory-bullet-format` is a correct control
(`expected_root_cause_ids: []`, zero false positives), but `LIMITATIONS.md` item
28 records that it is a pure Markdown-formatting diff and
`review-code-simplicity`'s own rubric instructs unconditional omission of
formatting concerns — so a fully compliant reviewer returns clean regardless of
whether it ever reasoned about the near-miss judgment the case was built to
test. Classified **rubric ambiguity or overbreadth**, specifically a
measurement-design limitation in the control itself, not a reviewer defect: the
case cannot currently discriminate a reviewer that reasons about justification
from one that reflexively ignores all formatting. Recorded as an open item for
whoever next curates this stratum, per item 28's own recommendation; no #51–#57
disposition depends on it.

`compat-accessor-boundary-duplication` is a correct control with zero false
positives and `verdict_stability: 1.0` — no failure.

## Runtime/tooling behavior

Zero attempts across all 75 graded attempts (35 + 20 + 20) recorded any
`spawn_failure`, `timeout`, `runtime_failure`, `output_too_large`,
`malformed_output`, or `protocol_mismatch` status; every `statuses` block in
every `per_case` entry across all three reports reads `{'review_result': 5}`.
**No runtime or tooling failure occurred anywhere in this baseline.** This
bucket is closed for v1 with zero material findings, and no #51–#57 mechanism is
justified by a runtime/tooling cause.

## The deferred connector stratum

`frozen-configuration.json`'s `connector-escape` stratum entry is
`state: deferred_not_satisfied` with `target_skill: null` and no cost ceiling.
Zero connector-escape attempts exist anywhere in this baseline. This is not
classified as a correct control, a miss, or any other outcome — it is simply
absent evidence, and per `LIMITATIONS.md` item 1 must never be read as zero
connector-escape risk. See `DECISION-RECORD.md`'s entry for #56 for how a
separate, owner-authorized connector-outcome source is used in this v2 cycle
without retroactively touching this deferred stratum.

## Summary rollup (acceptance criterion 1)

| bucket                               | cases                                                                                                                                                                                                    |
| ------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| reviewer (demonstrated failure)      | `dependency-strictness-propagation`, `stale-claim-release-guard`, `process-isolation-assertion`                                                                                                          |
| reviewer (correct, no failure)       | `dependency-hint-parser-coverage`, `post-bootstrap-module-load`, `session-continuation-summary`, `reconciliation-outcome-type`, `record-status-transition-guard`, `compat-accessor-boundary-duplication` |
| evidence/rubric (measurement design) | `env-inventory-bullet-format`                                                                                                                                                                            |
| grader/corpus ambiguity              | `registry-client-layering`, `setup-service-path-gateway`, `metrics-label-formatting-duplication`, `watcher-check-policy-duplication`                                                                     |
| reviewer/grader, undisentangled      | `optional-tool-probe`                                                                                                                                                                                    |
| runtime/tooling                      | none observed                                                                                                                                                                                            |

Every one of the 15 scored cases across the three strata appears in exactly one
row above. Only three cases — the two confident misses and the false-alarm
control — are used as evidence in `DECISION-RECORD.md`. The rest are either
correct behavior, a corpus/grader confound explicitly out of this ticket's
non-goals to fix, or an open question recorded for a future corpus-curation
ticket rather than resolved here.
