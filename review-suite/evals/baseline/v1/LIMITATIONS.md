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
  as a control. Over five attempts it scored recall **0.0** with **ten
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
  case's reported input drifted across the four batches whose raw output is
  retained — 32,573, 32,955, 33,166, then 32,464 — with the payload unchanged.
  Treat within-batch differences as measurements and absolute counts as
  approximate. A fifth value, 32,507, was observed on the earliest batch, whose
  raw output was overwritten before the artifact path was version-scoped; it is
  not re-derivable and is recorded here only for completeness.

## 10. A stratum boundary is not a rounding difference

A change of runtime, runtime version, model, target skill, dependency closure,
or run count creates a new stratum. Comparing across one of those boundaries is
an invalid comparison, not a noisier one. Every report records its closure
membership and digest so a stratum can always state what it evaluated.

## 11. Every measured figure has several hand-maintained homes

The pilot's numbers appear in the committed reports and are then restated in
this record, in the cost-ceiling proposal, in the calibration record, in the
strata README, and in the frozen configuration. Nothing checks those
restatements against the reports, and two review cycles on this candidate each
found a figure that had drifted — a referral count and an input-token series,
both corrected.

The restated **prose** caveats must stay duplicated: a reader who reaches one
report should not have to find another file to learn that its grading is not a
signal, or that the connector stratum is deferred. The restated **numbers**
should not be. Two remedies are open, and neither is done here: give each figure
one canonical home and reference it, or add a test asserting that every
documented figure matches the committed report it came from.

Recorded as a deferred finding and an input to #59 rather than fixed, because
the review that raised it did not gate on it. Until one of those remedies lands,
treat a number in a prose record as a restatement and the committed report as
the source.

## 12. The overwrite guard covers raw artifacts, not every output path

`runner.refuse_to_overwrite_artifacts` fails before launching any attempt when a
run would overwrite a retained raw stdout artifact. The per-attempt records, the
aggregate report, and the baseline report are still written unconditionally.

**Only some of those paths are protected in practice, not all of them.** The
frozen invocations give `--artifact-dir` and `--attempts-out` the same
`<commit>-<corpus_version>` stem, so a re-run into a new stem writes beside the
old records rather than over them. Every `--report-out` is a **stemless fixed
path** — `baseline/v1/pilot/pilot-<stratum>.report.json` and
`baseline/v1/<stratum>.report.json` — so a re-run at a new corpus version
replaces a committed report **without the guard firing**. That is not
hypothetical: it is how this ticket's own committed pilot reports were replaced
between batches.

The only thing protecting a committed report is that `baseline/v1/` is tracked
in git, so an overwrite is visible in `git status` and recoverable from history.
That is a real protection and a weak one, because it depends on someone looking.
Widening the guard to every output path remains a deferred finding.

## 13. False-alarm rate is a lower bound on invention, not a general rate

Every clean control in this corpus is an **adjudicated-rejected finding**: a
case where a concern was actually raised and dispositioned as not material. That
is the owner's settled standard, and it is the right one — the alternative,
treating a comment-free candidate as clean, is ambiguous between
reviewed-and-clean and nobody-looked, and would charge a false alarm against a
reviewer that correctly found a real unnoticed defect.

The standard has a boundary that must travel with every figure derived from it.
**It measures whether a reviewer re-raises a finding a human already rejected.
It does not measure whether a reviewer invents a novel finding on a wholly clean
diff.** Those are different failure modes, and only the first is instrumented
here.

So report false-alarm rate from these controls as a **lower bound on
invention**. A reviewer could score a perfect 0.0 on every one of them and still
gate freely on diffs where nothing was ever raised. Measuring that would need a
different control class — a candidate adjudicated clean by construction rather
than by rejection — which this corpus does not contain and which the standard
above deliberately declines to fake.

## 14. A scored stratum cannot be both calibrated and result-blind

This is the sharpest open question the corpus has, and it blocks scoring rather
than merely qualifying it.

Batch 1 measured what an uncalibrated expectation reports: recall 0.0 over five
attempts against a reviewer that found the defect every time, because grader
matching is containment and the shipped formulations had never met real prose.
Calibration fixed it — recall 1.0 — but calibration requires *observing the
reviewer's prose for that case*. Observing a scored case's prose and then tuning
its formulations is fitting the grader to the answer, which is exactly what the
non-goals forbid.

`s1-correctness-orchestrator` is therefore populated with `scored: false` and
every expectation `calibrated: false`, and **no case in it has been run through
any runtime**. Both states are honest, and neither is a resting place: scored as
it stands, it would report a number about the corpus. Four resolutions exist,
and the owner has to pick one:

1. **Rely on transfer.** Calibrate only on the disjoint pilot cases and accept
   that scored formulations are untuned. Measured to transfer once — the pilot's
   calibrated formulations held on two later runs — but transfer is not
   guaranteed, and untuned formulations bias recall **downward**, so the
   baseline would understate the reviewer.
2. **Split each case class.** Calibrate on half, score the other half. Costs
   corpus size, which the per-stratum minima already constrain.
3. **Report referrals as a first-class bucket.** Score matched, missed, and
   *referred for adjudication* separately, so a containment miss is visible as a
   grader limitation instead of silently becoming a reviewer miss. Cheapest, and
   it makes the existing `adjudication_required` output load-bearing.
4. **Replace containment matching** with semantic matching or a standing
   adjudication queue. A v2 mechanism, so it belongs to #59.

Whichever is chosen, it must be preregistered with the rest of the frozen
configuration, because it decides what recall means.

## 15. An oracle adjudicates a requirement, not a diff

Every case in `s1-correctness-orchestrator` carries an executable oracle as its
second adjudication, and that is genuinely independent of the reviewer being
measured — a machine that runs the code shares no blind spot with a model. But
an oracle asserts only the requirements the change contract states.

- On a gating case it proves the requirement fails and that correcting the
  stated root cause makes it hold, which adjudicates both materiality and the
  identity of the cause.
- On a clean control it proves the stated contract holds. **It does not prove
  the diff is free of every possible defect**, so a clean control means "the
  contract holds and the raised concern was adjudicated immaterial", never
  "nothing is wrong here".
- It cannot adjudicate a judgement about prose. Two cases record this: an oracle
  cannot settle whether a field's name reads as a claim it should not make, nor
  whether a test's name overstates what it asserts.

One case carries a further caveat. `process-isolation-assertion`'s first
adjudication came from the review suite **under evaluation** — a `defer` verdict
from the same contract being measured — which is weaker evidence than a human
disposition and is recorded as such in its provenance.
