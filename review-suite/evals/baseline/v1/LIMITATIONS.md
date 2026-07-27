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
  `connector`, in `corpus.json` and in every report;
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
- **After calibration** against the observed prose, three fresh runs at the
  frozen version scored recall 1.0 with zero false positives and zero
  adjudication referrals.

The generalisation limit is real: a future run that phrases the same finding a
fifth way — "export is not among the registered subcommands" — matches none of
the four shipped formulations and would be referred for adjudication. Read
`adjudication_required` as a first-class part of any result, not as noise. A
semantic matcher, or a standing adjudication queue, is a candidate mechanism for
whoever owns v2.

## 4. A root cause's `surface` must name a symbol, not a path prefix

Surface matching is token-level and file-level. Calibration found that a surface
written as `storectl/guidance.py render_rollback_guidance` shares the token
`storectl` with essentially every location in the packet, which made a
deliberately wrong gating finding at an unrelated file score `partial` instead
of being charged as a false positive. **With a broad surface, the false-positive
rate is not measurable**, because nearly every wrong finding is referred instead
of counted.

Narrowing the surface to `render_rollback_guidance` restored the boundary. Any
stratum populated later must write surfaces as the smallest identifying symbol,
and its calibration set must include a `plausible_false_positive` probe that
actually classifies as `unexpected`.

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

## 9. Cost figures are runtime-reported, and cache-sensitive

Cost comes from what the runtime reports, not from an independent meter. The
pilot also showed per-attempt cost varying three- to fourfold within a stratum
purely from prompt-cache state. Any cost figure is a report about one run's
caching behaviour as much as about the work done.

## 10. A stratum boundary is not a rounding difference

A change of runtime, runtime version, model, target skill, dependency closure,
or run count creates a new stratum. Comparing across one of those boundaries is
an invalid comparison, not a noisier one. Every report records its closure
membership and digest so a stratum can always state what it evaluated.
