# How two independent adjudications can honestly be satisfied

A proposal, not a decision, and nothing here has been executed. The context that
curated this corpus is contaminated with respect to it and cannot serve as
either adjudicator for any case it authored.

## The requirement is not one question

#58 asks for two independent adjudications of four different objects: each
material root cause, each accepted non-finding, each severity, and each allowed
equivalent formulation. Treating those as one act is the main way this gate gets
faked, because the evidence available for them is wildly different. They
separate into three distinct adjudications with different evidence and different
honest answers.

| adjudication                                                                                                                    | question                                 | can the source review thread answer it? |
| ------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------- | --------------------------------------- |
| **A — ground truth.** Is this a real material defect, and is the stated root cause the right one?                               | judged against the *original* code       | **Yes, as one adjudication**            |
| **B — fidelity.** Does the minimized reproduction still demonstrate that defect, and only that defect?                          | judged against the *retained artifact*   | **No.** The minimization postdates it   |
| **C — grading.** Are the formulations equivalent, tight enough to refuse a wrong finding, loose enough to recognise real prose? | judged against *observed reviewer prose* | **No.** Not even in principle           |

## 1. Do the source threads already constitute a first adjudication?

Partly, and the parts matter.

| object                      | what a source thread actually supplies                                                                                                                                                                                                                                       | usable as adjudication #1?                                                                 |
| --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| **material root cause**     | The reviewer names the defect, its triggering condition, the affected surface, and the consequence, and a follow-up reply names the implementing commit. A recorded human judgment against a real candidate, made before any evaluation existed and with no knowledge of it. | **Yes — strong.** This is the best evidence in the corpus and should not be re-derived.    |
| **severity**                | Usually only *gating vs not gating*. "Please either ... or ..." and "This introduces a regression risk" clearly demand a change; "Should we ...?" and "Consider ..." clearly do not. But `blocking` vs `strong_recommendation` is rarely recoverable from the prose.         | **Thin.** Adjudicates the gating question, not the two-level severity the schema requires. |
| **accepted non-findings**   | Present only when a suggestion was explicitly declined on the merits. A thread records what someone *did* raise, never the set of reasonable observations that should be tolerated without counting as false positives.                                                      | **Insufficient in general.** Available for a minority of cases.                            |
| **equivalent formulations** | One human's wording about the original code.                                                                                                                                                                                                                                 | **No.** See below.                                                                         |

The formulation row is not a judgment call, it is measured. Formulations must
match a *model's* prose about a *minimized* reproduction, and this ticket's
pilot tested that twice on two independent cases:

- `rollback-guidance-render`: formulations written before any run recognised
  nothing. Recall 0.0 while the reviewer found the defect on every attempt.
  After calibration against observed prose, recall 1.0 over five fresh attempts.
- `status-label-normalization`: left deliberately uncalibrated as a control.
  Recall **0.0** over five attempts with **ten adjudication referrals**, while
  verdict stability was 1.0 and the reviewer gated the change every time.

So a source thread cannot supply adjudication C, and a source-derived
expectation that skips C reports a number about itself rather than about the
reviewer. Every expectation now carries a machine-readable `calibrated` flag,
and a test refuses a scored case that is not calibrated and does not ship a
calibration set.

**Recommendation.** Record the source thread as adjudication #1 for **A only**,
with its provenance — repository, pull request, comment id, and the reply naming
the implementing commit. Do not let it count toward B or C, and count it toward
severity only at the gating/not-gating level.

## 2. Is a fresh blind agent context a defensible second adjudicator?

It depends which adjudication, and for the one that matters most the honest
answer is no.

First, a distinction worth keeping: #58's contamination rules exist to keep the
*evaluated reviewer* blind to expected outcomes. An adjudicator has the opposite
job — it must see the expectation to judge it. "Blind" for an adjudicator means
blind to the *first adjudication and the curator's reasoning*, not to the case.

### Conditions that would have to hold

1. It never sees the first adjudication, the source thread, the disposition, the
   expectation file, or any curation transcript.
2. It sees the reviewer-visible packet and independently states what it believes
   the material root causes, severities, and tolerable observations are. A
   **mechanical** comparison, not an agent, then decides agreement with the
   shipped expectation.
3. Its output is recorded verbatim, disagreements included, and is not
   reconciled by whoever authored the expectation.
4. Its model identity is recorded, exactly as an evaluated attempt's is.

### Where it is legitimate

**Adjudication C, grading — yes.** Whether a formulation is loose enough to
credit a wrong finding is a question about an artifact, it is cheaply checkable,
and being wrong is recoverable. The calibration set already makes each such
claim executable.

**Adjudication B, fidelity — yes, with a caveat.** "Does this minimized packet
still demonstrate the stated defect, and carry no domain content?" is answerable
from the packet alone, which is precisely what a blind context has. It is also
the adjudication no source thread can ever supply, so this is where a blind
context adds the most.

### Where it is not legitimate

**Adjudication A, ground truth — no, when the adjudicator shares a model family
with the evaluated reviewer.** This is not a contamination-rule problem and
blinding does not fix it.

The baseline exists to measure whether the review suite finds real defects. If
the standard for "material defect" is set by the same model class being
measured, the measurement partly closes on itself: a defect that model class
systematically cannot see becomes a defect the adjudicator agrees is not
material, the case is dropped or reworded, and **recall rises without the
reviewer improving**. The errors are correlated, so two such adjudications are
not two independent observations. Presenting them as satisfying the gate would
be the same class of mistake as asserting review quality through expected JSON
that the same change authored — the mistake this whole epic exists to correct.

Three things do make an acceptable second adjudication for A:

1. **A second human who is not the source reviewer.** Strongest, and possibly
   unavailable.
2. **An executable oracle, where one exists.** This is the strongest option
   available here and is stronger than any opinion, human or model. Where a
   minimized reproduction can be made to *run*, materiality stops being a
   judgment: the defect either reproduces as a failing check or it does not. The
   [SOURCING.md](SOURCING.md) already identifies a candidate adjudicated exactly
   this way — `f544aa0` in this repository survived an aggregate `clean` review
   verdict and was then caught by CI, so its second adjudication is a machine,
   with full provenance and no retention question. Both pilot cases are
   mechanically checkable in principle: an emitted subcommand can be compared
   against a registered command surface, and a flag contradicting a canonical
   status can be asserted directly.
3. **A blind context in a different model family from the evaluated stratum**,
   with the correlation limitation recorded. Weaker than the first two,
   materially better than same-family, and never sufficient on its own for a
   case whose materiality is contested.

**Recommendation.** Make each minimized reproduction executable wherever the
defect admits a mechanical check, and use that as the second adjudication for A.
Route the remainder to a human. Use a blind agent context for B and C, never as
the second adjudicator for a contested A.

This is exactly where the simplicity strata are weakest, and it should be said
plainly: "this is over-engineered" and "this complexity is
requirement-justified" have no executable oracle at all. Every root cause and
every near-miss control in `s2-solution-simplicity-lens` and
`s3-code-simplicity-lens` therefore needs human adjudication, or must be
reported with the correlated-judgment limitation attached.

## 2b. Outcome: the oracle method, applied

The proposal above was adopted for `s1-correctness-orchestrator` and it settled
every case in it. `review-suite/scripts/evals/oracles/` ships one runnable
module per case, and `test_eval_oracles.py` asserts the polarity each expected
verdict demands: the requirement must **fail** against a gating candidate and
**hold** once the stated root cause is corrected, and must **hold** against a
clean candidate.

| case                                | second adjudication | what the oracle settled                                                                                  |
| ----------------------------------- | ------------------- | -------------------------------------------------------------------------------------------------------- |
| `dependency-strictness-propagation` | oracle              | The two decision paths disagree on the closed record; correcting the sibling call site makes them agree. |
| `stale-claim-release-guard`         | oracle              | The unowned-at-scan interleaving releases a live claim; an unconditional owner comparison prevents it.   |
| `optional-tool-probe`               | oracle              | The probe raises instead of skipping; catching `OSError` restores the skip.                              |
| `session-continuation-summary`      | oracle              | The loop continues and the reporter never claims a session, so the contract holds.                       |
| `dependency-hint-parser-coverage`   | oracle              | The canonical field is read and both retired aliases are ignored.                                        |
| `post-bootstrap-module-load`        | oracle              | The module binds after selection, which a module-level import cannot do.                                 |
| `process-isolation-assertion`       | oracle              | One retained artifact per attempt, attributable to its executor.                                         |

**Owner still required for:** every case in `s2-solution-simplicity-lens` and
`s3-code-simplicity-lens`. "This is over-engineered" and "this complexity is
requirement-justified" have no executable form, so those cases will declare
`owner_required`. Two tests hold them to it: a stratum may not declare `scored`
while any of its cases lacks a recorded second adjudication, and a case that
ships no oracle may not record anything other than `owner_required`.

### The three limits of what was settled

1. An oracle adjudicates the **stated requirements**, not the diff. A clean
   control's oracle proves the contract holds and the raised concern was
   immaterial; it does not prove nothing else is wrong.
2. An oracle cannot adjudicate prose. It cannot settle whether a field's name
   reads as a claim it should not make (`session-continuation-summary`) or
   whether a test's name overstates its assertion
   (`process-isolation-assertion`). Both record this.
3. `process-isolation-assertion`'s **first** adjudication came from the review
   suite under evaluation — a `defer` from the same contract being measured. The
   oracle is independent of it, but the first adjudication is weaker than a
   human disposition and its provenance says so.

### Verification changed three of the expectations below

The disagreement table in section 4 was written before the source dispositions
were re-checked. Checking them resolved three entries, and two resolutions were
the opposite of what the table assumed:

- **atelier PR 335 was accepted** (`5cb0333`). It is a valid escape, not an
  ambiguous one, and it is now the multi-file propagation case.
- **atelier PR 333 and PR 356 were both accepted**, not deferred. Both are
  unusable as negative controls and were dropped.
- **Both clean-control candidates failed** the owner's settled standard and were
  replaced. See [SOURCING.md](SOURCING.md) for all five dropped candidates.

The clean-control question the table flagged as the weakest slot is now settled
by the owner, and the corpus is built to that standard.

## 2c. Outcome: `s2-solution-simplicity-lens`, no oracle available

Every case in this stratum records `adjudication.second: owner_required`, and a
test now enforces that a case with no shipped oracle may not record anything
other than that value. Each case's provenance carries a recommended disposition
and the specific counter-argument that could overturn it, so the owner is
confirming or correcting a stated argument rather than starting from a bare case
description.

| case                             | recommended | the strongest counter-argument, for the owner to weigh                                                                                                                                                                                                              |
| -------------------------------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `setup-service-path-gateway`     | MATERIAL    | A reviewer could value the injected gateway as forward consistency with a future second implementation the packet does not rule out.                                                                                                                                |
| `registry-client-layering`       | MATERIAL    | The diff only touches the queue-message client; a reviewer could argue the mutation-client duplication predates this change and is out of scope for it.                                                                                                             |
| `reconciliation-outcome-type`    | CLEAN       | A reviewer could reasonably propose a smaller fix (a second boolean, or one sentinel) instead of a four-member enum - whether that is "over-shoots the requirement" or "unnecessary machinery" is a distinction this case's own accepted non-finding does not draw. |
| `record-status-transition-guard` | CLEAN       | Retry count and backoff are unspecified in the packet; a reviewer could reasonably ask for that detail without the request being about over-engineering at all.                                                                                                     |

None of these four is settled. They are recommendations, not adjudications, and
the record is explicit about the distinction so a recommendation is never
mistaken for a second party's judgement.

## 2d. Outcome: `s3-code-simplicity-lens`, no oracle available

Same shape as `s2`: every case records `adjudication.second: owner_required`,
enforced by the same test.

| case                                   | recommended | the strongest counter-argument, for the owner to weigh                                                                                                                                                                                                                      |
| -------------------------------------- | ----------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `watcher-check-policy-duplication`     | MATERIAL    | Severity is recorded as strong_recommendation rather than blocking, since the packet shows no currently observed drift, only a stated history of it; a reviewer could argue for blocking given that history.                                                                |
| `metrics-label-formatting-duplication` | MATERIAL    | This case and s2's `registry-client-layering` trace to the same source PR and comment, read at two different levels; the owner should confirm this reuse is deliberate and recorded rather than an unintended duplicate sample of one finding across two strata.            |
| `compat-accessor-boundary-duplication` | CLEAN       | A reviewer could reasonably ask whether the two independently scheduled callers could still share one function with two call sites rather than two functions with one body each - a smaller version of the question this case's own accepted non-finding already tolerates. |
| `env-inventory-bullet-format`          | CLEAN       | A reviewer could reasonably propose a narrower fix (wrapping only the wide cell, or a two-column table) rather than the fully verbose bullet form; this case's own accepted non-finding already flags the repeated owner field as one place that narrower fix could start.  |

None of these four is settled. They are recommendations, not adjudications.

## 3. Expected workload

Fifteen scored cases across three strata: roughly 12–16 material root causes,
roughly 30 accepted non-findings, 15 severities, and 60–80 formulations. The
formulation count dominates, and it is also the cheapest to adjudicate, because
each claim is executable against the calibration set rather than argued.

## 4. Where the two adjudications are expected to disagree

More useful than a clean-looking count. Assessed per candidate in
[SOURCING.md](SOURCING.md); every entry still needs its adjudication trail
re-verified at the source.

### Expected agreement

| case                                      | why                                                                                                                          |
| ----------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `f544aa0` validation gap, this repository | Adjudicated by CI. Machine second adjudication, complete provenance. The strongest case in the corpus.                       |
| atelier PR 373, claim-clearing race       | The thread states the exact interleaving window, the wrong guard, and the required regression test. Little room to disagree. |
| atelier PR 674, split atomic write        | Directive, with the partially-applied state named explicitly.                                                                |
| atelier PR 160, injected abstraction      | The reviewer asks outright why any abstraction is needed. An unambiguous over-engineering adjudication.                      |

### Expected disagreement, and on what

| case                                                           | expected disagreement                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Both clean correctness controls**                            | **The weakest slots in the plan.** Neither candidate is an adjudicated *clean review*. PR 335's "Nice hardening here" endorses a hunk inside a pull request that also carried a finding, and PR 417's accepted implementation is an accepted *fix*, not a change adjudicated clean. A second adjudicator may reasonably say the clean control was manufactured by cropping. **The owner must settle the standard**: does `clean` require a review that returned no material finding, or a hunk a reviewer affirmatively endorsed? Until that is settled the false-alarm rate has no honest denominator. |
| atelier PR 335, propagation                                    | Raised as a question — "Should dependency checks mirror strict mode for closed dependencies too?" Materiality and severity are both genuinely arguable. No acceptance reply was verified.                                                                                                                                                                                                                                                                                                                                                                                                               |
| atelier PR 350, two recovery paths                             | Root cause should agree; **severity will not.** `blocking` versus `strong_recommendation` is not recoverable from the thread.                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| atelier PR 410, duplicated client concepts                     | **Lens assignment, not materiality.** Whole-solution over-engineering or local reuse? That decision picks the stratum, so a disagreement here moves the case rather than resolving it.                                                                                                                                                                                                                                                                                                                                                                                                                  |
| All four simplicity near-miss controls (PR 417, 277, 630, 443) | **Highest expected disagreement rate.** "Requirement-justified" is a judgment with no oracle. PR 443 — per-item bullets chosen over a table for formatter stability — may not be a simplicity question at all and should probably be replaced.                                                                                                                                                                                                                                                                                                                                                          |
| `status-label-normalization`, this corpus's pilot case         | Two root causes were authored by one context and deliberately left uncalibrated. Over five attempts the reviewer gated the change every time and the grader matched neither root cause, producing ten referrals. Whether the authored root cause or the reviewer's actual finding is the material one **is** the adjudication question, and the referrals are the evidence.                                                                                                                                                                                                                             |

### Ambiguous source disposition — verify or drop before use

| case                               | problem                                                                                                                                                             |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| atelier PR 333                     | A scope question plus a request for a rationale comment. No disposition verified. May be a polish-only negative control, or nothing.                                |
| atelier PR 356                     | "Possible edge case to validate ... or add a regression test to prove current behaviour is intentional." No disposition verified.                                   |
| atelier PR 335, clean-hunk reading | Used twice, once as a propagation escape and once as a clean control. If both survive adjudication they must be provably different packets, or one must be dropped. |

## 5. What must not be done

- One context supplying both sides, in any framing, including a second context
  spawned by the first and given its conclusions.
- Treating the source thread as both adjudications because it contains both a
  finding and an acceptance reply. That is one party twice.
- Adjudicating after seeing scored output. Adjudication is part of the freeze;
  revising an expectation once results are visible is tuning the grader to the
  answer.
- Recording a case as adjudicated when the disposition was ambiguous. An
  unresolvable disagreement excludes the case or marks it unscorable, and is
  never recorded as a reviewer miss.
