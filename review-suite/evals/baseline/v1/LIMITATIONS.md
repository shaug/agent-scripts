# Baseline limitations

These are explicit inputs to baseline interpretation. Read them before quoting
any figure this directory produces or will produce.

## 1. The connector stratum is deferred, not satisfied

**Connector-escape recall has never been measured.** Nothing in this baseline
says anything about whether the review suite catches defects that a connector
review missed.

This repository has no pull-request review history at all: zero reviews, zero
review threads, and zero comments across every one of its pull requests. There
was no in-repository connector material to curate. A private repository that
does carry connector review history was identified and deliberately excluded on
third-party authority and disclosure grounds; it is not named here, was not
read, and nothing here derives from it. Fabricating escapes was rejected
outright — a baseline frozen against invented cases would reproduce the exact
defect this work exists to correct, and would then miscalibrate every
preregistered gate downstream.

Ground truth therefore comes from real adjudicated **human** review and from
this suite's own delivery history. Consequences:

- every stratum is labelled `human-review` or `repository-history`, never
  `connector`, in `corpus.json` and in every report's `configuration.stratum`,
  which the runner copies verbatim from the corpus so a report quoted on its own
  still states its ground truth;
- a test asserts no shipped corpus claims `connector-review` ground truth, so
  the label cannot drift by accident; and
- **a human-review figure must never be reported as a connector-escape figure,
  and the two must never be blended.**

Human review and connector review are not interchangeable ground truth. They
have different miss profiles, different adjudication standards, and different
incentives. Treat the absence of a connector stratum as an open measurement gap,
not as a gap that the human-review stratum partially fills.

## 2. No aggregate verdict-accuracy rate exists

The per-attempt grade records `verdict_match`, but the aggregate report has no
verdict-accuracy figure. Worse for this purpose: only `review_result` attempts
are graded at all, so a case whose expected verdict is `blocked` enters no
quality denominator — when the reviewer correctly refuses, the attempt is
classified `blocked` and never graded. This was raised twice during the
evaluator's own review and deliberately deferred there.

No scored stratum declared in `frozen-configuration.json` expects a `blocked`
verdict, so the gap does not silently drop a scored case from the baseline. That
is a composition decision, and it has a cost: **the baseline will not measure
refusal behaviour on incomplete evidence**, which is one of the behaviours the
surrounding work most wants to know about. Adding such a case class requires the
metric to exist first.

## 3. Grader matching is textual containment, and does not generalise on its own

The reference grader matches an observed finding to a private root cause when
the finding names the affected surface *and* its prose contains one of the
shipped formulations, after normalisation. Containment is exact. The pilot
demonstrated both halves of what that means:

- **Before calibration**, the shipped formulations recognised nothing. Every run
  found the real root cause and every run scored `partial`, because the
  formulations had been written before any real prose existed. Recall was 0.0
  while the reviewer was, in fact, correct on all three runs.
- **After calibration** against the observed prose, five fresh attempts at the
  frozen version scored recall 1.0 with zero false positives and zero
  adjudication referrals.
- **Confirmed independently on a second case.** `status-label-normalization` is
  carried by the orchestrator pilot stratum and deliberately left uncalibrated
  as a control. Over five attempts it scored recall **0.0** with **nine
  adjudication referrals**, while verdict stability was 1.0 and the reviewer
  gated the change on every attempt. Two cases, ten attempts, one conclusion: an
  uncalibrated expectation reports a number about itself.

That is now a machine-readable property rather than a caution. Every expectation
carries a `calibrated` flag, and a test refuses a scored case that is not
calibrated or that ships no calibration set. **Read the flag before reading any
recall figure.**

The generalisation limit is real: a future run that phrases the same finding a
fifth way — "export is not among the registered subcommands" — matches none of
the four shipped formulations and would be referred for adjudication. Read
`adjudication_required` as a first-class part of any result, not as noise. A
semantic matcher, or a standing adjudication queue, is a candidate mechanism for
whoever owns v2.

## 4. The false-positive rate is only partly measurable, and stays that way

`grader.py` counts a surface hit when the finding's location shares **one**
normalised token with the root cause's `surface`. A finding that hits the
surface but matches no formulation is `partial`, and a `partial` is referred for
adjudication rather than charged as a false positive. So a wrong gating finding
is only ever charged when its location shares **no** word with the surface.

Calibration measured both halves of this on the pilot case, whose surface is now
the symbol `render_rollback_guidance`, tokenising to
`{render, rollback, guidance}`:

| wrong gating finding located at          | classified   | charged as a false positive      |
| ---------------------------------------- | ------------ | -------------------------------- |
| `storectl/cli.py`                        | `unexpected` | **yes**                          |
| `storectl/guidance.py`                   | `partial`    | no — token `guidance`            |
| `tests/test_guidance.py`                 | `partial`    | no — token `guidance`            |
| `storectl/guidance.py:render_apply_plan` | `partial`    | no — tokens `render`, `guidance` |

Writing the surface as a path prefix was worse —
`storectl/guidance.py render_rollback_guidance` also collides on `storectl`,
which appears in nearly every location in the packet — and narrowing it to the
symbol shrank the unchargeable region. **It did not remove it.** The locations
that remain unchargeable are the changed file, its test, and its untouched
neighbours, which is exactly where a real reviewer is most likely to point.

Consequences, and they are not cosmetic:

- **`false_positive_rate` is a lower bound, not a rate.** It counts only wrong
  gating findings that share no word with any root-cause surface.
  `frozen-configuration.json` records it as partially measurable rather than
  measured, and #59 must not read it as a measured rate.
- Any stratum populated later must still write surfaces as the smallest
  identifying symbol, and its calibration set must carry a
  `plausible_false_positive` probe that genuinely classifies `unexpected` and
  charges a false positive. The calibration test asserts that outcome per probe
  kind rather than accepting the set's own claim.
- The `surface_token_collision` probe in the shipped calibration set pins the
  residual gap in place, so it stays visible instead of being rediscovered.

The one-token rule is `grader.match_strength`, which is #50 infrastructure this
ticket's non-goals forbid repairing. Requiring every surface token instead of
any is a small change with a real trade-off — it would turn some correct
findings that name only part of a surface into misses — so it is **escalated to
#59 as a candidate preregistered v2 gate**, not recorded here as solved.

## 5. An expectation is target-specific

The three pilot strata carry one byte-identical case so that the declared skill
closure is the only variable. The case's expectation is calibrated for the
orchestrator target, and the two lens strata consequently graded it as a miss —
correctly, since a correctness root cause is not a defect a code-simplicity lens
is contracted to report. Their graded output is therefore **not** a quality
signal; only their payload size, latency, cost, and protocol outcomes are.

The rule this yields for the scored strata: expectations must be authored for
the lens the stratum targets. Sharing one case list across strata with different
targets would grade contract-faithful reviewers as wrong and invalidate the
affected stratum.

Because the two lens pilot reports are committed and machine-readable, and they
do carry `material_finding_recall: 0.0` and `false_clean_rate: 1.0`, the caveat
is also recorded where a reader reaches them rather than only here: each
mismatched corpus declares `stratum.grading_is_signal: false`, a test forbids a
scored stratum from declaring it false, `frozen-configuration.json` annotates
each pilot report entry, and `pilot/README.md` sits beside the reports. **Do not
quote the recall or false-clean figure from
`pilot-solution-simplicity.report.json` or
`pilot-code-simplicity.report.json`.**

## 6. Severity is required but not measured

`expectation.schema.json` requires a `severity` on every root cause, and no
metric consumes it. Severity agreement is not measured. Either score it or drop
the requirement; do not assume it is being measured.

## 7. The scored corpus is not yet populated

`frozen-configuration.json` declares three scored strata in state
`declared_unpopulated`. No scored case exists yet, so **no baseline figure
exists yet**. The corpus-population batches, their sourced ground truth, and the
case classes each will carry are recorded in [SOURCING.md](SOURCING.md). Every
case class required of the corpus is named there; none has been silently
omitted.

## 8. Independent adjudication is outstanding

Every private expectation currently shipped was authored by one context. That
does not satisfy the requirement for two independent adjudications per material
root cause, accepted non-finding, severity, and allowed formulation, and it is
not presented as satisfying it. See [CALIBRATION.md](CALIBRATION.md) for exactly
what has and has not been adjudicated.

[ADJUDICATION-PLAN.md](ADJUDICATION-PLAN.md) proposes how the gate can honestly
be satisfied, and reaches one conclusion worth surfacing here: a fresh blind
agent context is a legitimate second adjudicator for whether a minimized case is
faithful and whether a formulation is well drawn, but **not** for whether a
defect is materially real when it shares a model family with the reviewer being
measured. Those errors are correlated, so two such adjudications are not two
independent observations, and recall would rise without the reviewer improving.
Where a minimized reproduction can be made to run, an executable oracle is a
stronger second adjudication than any opinion — the corpus already identifies
one case adjudicated exactly that way, by CI. The simplicity strata have no
oracle at all and need human adjudication.

A third open decision is recorded there: **neither identified clean-control
candidate is an adjudicated clean review.** Until the owner settles what a clean
control must be, the false-alarm rate has no honest denominator.

## 9. Cost figures are runtime-reported, and cache-sensitive

Cost comes from what the runtime reports, not from an independent meter. The
pilot also showed per-attempt cost varying three- to fourfold within a stratum
purely from prompt-cache state. Any cost figure is a report about one run's
caching behaviour as much as about the work done.

Two further measurements bear on any cost figure quoted from here:

- **Cost tracks output volume, not packet size.** The orchestrator stratum's
  larger packet raised input tokens 3.0% and raised cache-read cost 21% and
  cache-read latency 22%, because cache-read output grew 29%. A case's cost
  therefore depends on how much a reviewer has to say about it, which tracks the
  number of findings it warrants. A stratum's cost is not predictable from its
  packet sizes alone.
- **Reported input tokens include runtime-side prompt overhead.** The same
  case's reported input drifted across batches — 32,507, 32,955, 33,166, then
  32,464 — with the payload unchanged. Treat within-batch differences as
  measurements and absolute counts as approximate.

## 10. A stratum boundary is not a rounding difference

A change of runtime, runtime version, model, target skill, dependency closure,
or run count creates a new stratum. Comparing across one of those boundaries is
an invalid comparison, not a noisier one. Every report records its closure
membership and digest so a stratum can always state what it evaluated.
