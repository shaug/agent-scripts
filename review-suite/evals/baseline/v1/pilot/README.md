# Unscored pilot reports

These three reports establish executor compatibility, timeout behaviour, and a
cost and latency envelope **per stratum**. They are not a baseline. No scored
case exists yet, and nothing here measures reviewer quality across a corpus.

Five runs per case. Suite commit `16560d807c66076fcbf3f00d3a87f543c6ae2458`,
model `claude-opus-4-6[1m]`, corpus version `1.3-pilot-*`, grader version `1.0`,
timeout 300 s, no retries, one fresh process per attempt. **20 attempts, zero
evaluation failures, zero timeouts, 1.2266 USD.** Raw output is retained outside
git at `review-suite/evals/artifacts/<stratum>/1.3-<stratum>/`.

## Before reading any recall number, read the case's `calibrated` flag

Recall here is a property of the expectation at least as much as of the
reviewer. The orchestrator stratum carries two cases that differ in exactly that
respect, and the contrast is the most useful thing in this directory:

| case                         | `calibrated` | recall over 5 attempts | verdict stability | referrals | what it means                                                                                                                |
| ---------------------------- | ------------ | ---------------------- | ----------------- | --------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `rollback-guidance-render`   | `true`       | **1.0**                | 1.0               | 0         | Formulations pinned to prose a real reviewer wrote. The grader recognises the finding every time.                            |
| `status-label-normalization` | `false`      | **0.0**                | 1.0               | 9         | Deliberately uncalibrated control. The reviewer gated the change on every attempt and the grader matched neither root cause. |

The aggregate `material_finding_recall: 0.5` in `pilot-orchestrator.report.json`
is the mean of those two. **It is not a capability figure.** It is the measured
cost of shipping an uncalibrated expectation, and it is why a test refuses a
scored case whose expectation is not calibrated.

## Read the quality block in only one of these

| report                                  | quality block                                                                                                                    |
| --------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `pilot-orchestrator.report.json`        | **is** a signal for its target, `review-code-change` — but per case, with the `calibrated` flag in hand, never as the aggregate. |
| `pilot-solution-simplicity.report.json` | **is not** a signal. Do not quote its recall or false-clean rate.                                                                |
| `pilot-code-simplicity.report.json`     | **is not** a signal. Do not quote its recall or false-clean rate.                                                                |

All three corpora carry `rollback-guidance-render` byte for byte, deliberately,
so that the declared skill closure is the only variable between them — which is
the whole point of measuring an envelope per stratum. The consequence is that
the case's expectation, a correctness root cause authored for the orchestrator
target, is the wrong yardstick for a simplicity lens.

Both lens reports therefore record `material_finding_recall: 0.0` and
`false_clean_rate: 1.0`. **That is contract-faithful reviewer behaviour graded
against a target-mismatched expectation, not a reviewer failure.** A
code-simplicity lens is not contracted to report a correctness defect, so
returning clean is correct — and both lenses did so on all five attempts, with
verdict stability 1.0. Each mismatched corpus declares
`stratum.grading_is_signal: false`, and a test forbids a scored stratum from
declaring it false.

## What is a signal in all three

Payload size, input tokens, cost, latency, and protocol outcomes. Those are the
figures [the cost-ceiling proposal](../COST-CEILING-PROPOSAL.md) is built from,
and they are what the pilot exists to measure.

Read [the limitations record](../LIMITATIONS.md) before quoting anything from
this directory.
