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

## 14. Grading method — SETTLED by the owner: score three-way, never calibrate a scored case first

This was the sharpest open question the corpus had. Batch 1 measured what an
uncalibrated expectation reports: recall 0.0 over five attempts against a
reviewer that found the defect every time, because grader matching is
containment and the shipped formulations had never met real prose. Calibration
fixed it — recall 1.0 — but calibration requires *observing the reviewer's prose
for that case*, and observing a scored case's prose to tune its formulations is
fitting the grader to the answer, which the non-goals forbid outright.

**Resolution: score every case three-way — matched, missed, or referred for
adjudication — and never calibrate a scored case on its own prose first.** A
grader miss that stems from an unmet formulation is a `referred` outcome, not a
silent reviewer-miss and not a scored match. This reuses the
`adjudication_required` machinery already built by the grading interface rather
than shrinking an already-tight corpus by splitting each case class into
calibrate/score halves, or gambling on untuned transfer as the sole method,
which is unproven at corpus scale and biases recall downward if it fails.

Every populated scored stratum therefore ships `scored: false` and every
expectation `calibrated: false`, with **no case run through any runtime**, until
the owner unblocks scoring under this method. Once enough scored runs exist, a
post-hoc check of whether untuned transfer would have matched the referred
bucket is deferred evidence for #59's v2 grading design — it does not gate this
baseline and is not built here.

The three rejected alternatives, recorded for context rather than
reconsideration: relying on untuned transfer alone (unproven at scale, biases
recall downward); splitting each case class into calibrate/score halves (shrinks
corpus size the per-stratum minima already constrain); and replacing containment
matching itself with semantic matching or a standing adjudication queue (a
genuine v2 mechanism, so it belongs to #59, not to this baseline).

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

## 16. A grader formulation must not be quotable from its own packet

A contamination class that the physical separation of reviewer and private
artifacts does not cover, found by review on this corpus and now gated.

The audit's text search folds case and whitespace but keeps punctuation. The
grader folds punctuation away entirely. So a formulation reading
`subprocess.run raises FileNotFoundError` is invisible to the audit when its
packet says `` `subprocess.run` raises `FileNotFoundError` `` — and is a perfect
match once the grader normalises both. **A case shipped in exactly that state**:
the stratum's only validation-gap escape could have been answered at full recall
by quoting its own input, so it would have measured whether a reviewer echoes
the packet rather than whether it finds the escape.

The general lesson is worth stating beyond this instance: *whatever the grader
treats as the same text is what decides a score, so an audit that uses a
stricter definition of "the same text" than the grader is not auditing the thing
that matters.* The two now share one normalisation, and a regression test echoes
a formulation into its own packet with punctuation between every word to prove
the check survives re-wording.

Scoped to `material_root_causes`. An accepted non-finding's formulation often
does legitimately restate reviewer-visible content, and matching one only makes
the grader more tolerant of an observation already judged immaterial — it cannot
manufacture a correct answer. A second test pins that exemption so it is a
decision rather than an oversight.

What this does **not** cover: a packet that describes the defect in words the
formulations do not use. No mechanical check can catch that, because the packet
is supposed to describe the change. It is a curation judgement, and the oracle
is the backstop — a case whose defect is spelled out in its own packet will
still fail its oracle if the stated root cause is not the real cause.

## 17. An oracle is a hand transcription of its packet, with no mechanical link

Limitation 15 says an oracle adjudicates a requirement rather than a diff. There
is a second, sharper gap in the same mechanism, and this corpus demonstrated it.

An oracle's `candidate()` is written by hand to mirror the packet's diff.
Nothing checks that it does. Review found a case where the diff's corrective
action was guarded on the wrong side of a negation — so the diff's own added
test could not have passed, while the packet recorded that suite as green — and
**the oracle passed anyway**, because it modelled only the two decision
predicates and never the action the test asserts. The packet was corrected, and
that oracle now exercises the corrective action too, but the general hole is
unchanged: an oracle can agree with a packet that says something different.

So an oracle raises the floor without closing it. It proves a requirement is
violated and that correcting the stated cause fixes it; it does not prove the
reproduction it runs is the reproduction the reviewer will read. Two habits
follow, and neither is automatable today:

- read a packet's own added tests as claims that must be *satisfiable* against
  its own diff, since a packet asserting a green suite it cannot have is
  inconsistent evidence a contract-faithful reviewer may refuse; and
- write the oracle from the packet's *acceptance criteria and its tests
  together*, not from the criteria alone.

A mechanical link — generating one from the other, or applying the diff and
running its tests — would close it, and is a candidate v2 mechanism for #59
rather than something this ticket should invent.

## 18. Diff validity is now gated, and was not before

Every packet's diff must parse as a patch. That was asserted only for the
original protocol-proof corpus, so malformed hunk headers shipped in every
stratum added afterwards: eleven of the seventeen packets in this repository
failed `git apply --numstat` when first checked.

It matters more for a scored stratum than it looks. A packet whose diff is not a
valid patch is internally inconsistent evidence, and a reviewer that refuses a
merge verdict on it is behaving correctly under its own contract — which a
scored run would then record as a verdict mismatch, charging the reviewer for a
curation defect. All seventeen now parse, and the check runs across every corpus
rather than one.

## 19. The solution-simplicity stratum has no oracle at all

Every correctness case in `s1-correctness-orchestrator` has an executable oracle
because a correctness requirement is a statement about behaviour, so it can be
run. Nothing in `s2-solution-simplicity-lens` can be, because there is no
runnable form of "this abstraction is unnecessary" or "this machinery is
requirement-justified" — both are judgements about whether a design decision
matches its requirement, not properties a program can check.

Every case in this stratum therefore records
`adjudication.second: owner_required` rather than `oracle`, and a test enforces
that a case may not claim anything else without one. Each case's provenance also
records a recommended disposition and the specific residual risk that could
overturn it, so the owner is confirming or correcting a stated argument rather
than starting from a bare case description. That is not a substitute for the
owner's adjudication — it is scoped as a recommendation precisely so it is not
mistaken for one.

The same will be true of `s3-code-simplicity-lens` in the next batch: local
code-complexity and reuse judgements have the same property.

## 20. Two sources were reused across strata under different questions

`shaug/atelier` PR 417, comment 2870710594, was assessed once for
`s1-correctness-orchestrator` as a candidate clean-correctness control and
dropped there, because the owner's clean-control standard requires an
adjudicated-rejected finding and this comment records an accepted *fix* —
acceptance is the opposite disposition. The same accepted change is sourced
again here, in `s2-solution-simplicity-lens`, as a requirement-justified
near-miss control, where the relevant question is not "was a finding rejected"
but "is the added machinery justified by a stated requirement" — a question the
same accepted change answers cleanly.

This is a deliberate reuse under a different standard, not a retention-authority
question or a double-count: the two corpora measure different lenses against
different criteria from the same real disposition. Recorded here so a reader who
notices the same PR number in two places finds the reasoning rather than an
unexplained coincidence.

## 21. Minimization must replace the source's own identifiers, not just its business logic

Review found a real sanitization defect in this batch, in every one of its four
cases, before it shipped. Each case's provenance claimed no source identifier or
prose was copied. That was false: the packets carried the real product's own CLI
name and ticket-subsystem noun, real enum member strings, a real function name
verbatim, and expectation formulations built from the real reviewer's own
sentences rather than independently phrased equivalents.

None of that is business logic, a domain identifier, customer context, a
credential, or hidden reasoning in the ordinary sense — the earlier sanitization
gate's checklist. It is a narrower and easy-to-miss failure mode: **retaining
the source's own names and words while believing the case has been rewritten
"from scratch."** A case can carry no proprietary logic at all and still leak in
this way, because what leaks is naming, not substance.

Why it matters here specifically, beyond honesty: `shaug/atelier` is public.
Copying its real symbol names and its reviewer's real phrasing into a corpus
that sits in another public repository creates two distinct risks. A retained
identifier is potentially discoverable back to the source PR, which is a
disclosure question independent of whether the source is public. And, more
directly relevant to this baseline's purpose, a reviewer model trained on public
code may have this real text memorized; a packet that echoes it verbatim risks
being answered by pattern-matching a remembered PR rather than by reasoning
about the packet, which would corrupt exactly the measurement this corpus exists
to take.

The four cases in `s2-solution-simplicity-lens` were rewritten before merge:
product-specific CLI names and nouns replaced with fictional equivalents rather
than lightly renamed, a real function name and real enum member strings
replaced, and every equivalent-formulation phrase rewritten as an independent
paraphrase rather than the source reviewer's own sentence. The now-merged
`s1-correctness-orchestrator` cases were checked against the same class of leak
and found clean of it.

No mechanical check catches this today. `audit_corpus.py` proves
reviewer/private separation and outcome-revealing naming; nothing proves a
retained artifact is free of the source's own vocabulary, because the audit has
no way to know what the source's vocabulary was. Curation discipline is the only
defense until one exists: name every symbol as if writing original code for the
fictional subject, and never carry a reviewer's sentence forward as a
formulation without independently rephrasing it.

## 22. A minimization rewrite must update every field that names the changed symbols, not only the diff

The second review cycle on this batch found that the first sanitization fix
(item 21) renamed symbols inside the diff but left two packets' `context.data`
naming the pre-rename symbol — a function or class the diff no longer defines.
That is a narrower defect than a leak: it makes the packet internally
self-contradictory, independent of whether either name is real or fictional. A
reviewer reading `context.data` would be told to look for a symbol its own diff
had already renamed away.

The same cycle also found a packet whose diff had never been consistent in the
first place: it introduced three classes as brand-new code while a downstream
file's hunk implied two of them already existed under different names. That
predates the sanitization fix; renaming inside an already-incoherent diff cannot
make it coherent.

Both are now fixed: `registry-client-layering`'s case was rebuilt as a purely
additive diff — one new class next to two explicitly pre-existing, untouched
ones named only in context — and every context reference across the stratum was
checked against its own diff. The general lesson: **a rename or a fix inside a
diff must be swept across the whole packet, and a packet's diff must be checked
for internal consistency independently of whatever sanitization or grading
concern prompted editing it.** Neither check is mechanical today; both are
curation discipline until a tool exists to enforce them.

## 23. Naming the real source in private provenance is retention, not a leak

The same review cycle raised the real source's class name (`BeadsClient`)
appearing in a case's `retention_authority` and `adjudication.first` fields as a
possible sanitization defect. It is not: those two fields are private,
structurally separated from every reviewer-visible artifact, and their entire
purpose is to record *what the real source actually was* — the PR, the comment,
the accepted commit, and, where useful for a future audit, what that commit's
outcome was named. Every provenance record in this corpus already cites real PR
numbers, comment ids, and commit SHAs for exactly this reason, and this case is
consistent with that established pattern rather than an exception to it.

The sanitization rule in items 16 and 21 governs what reaches a
**reviewer-visible artifact or a grader formulation a reviewer's payload could
echo** — the packet, the equivalent formulations, anything `audit_corpus.py` can
reach. It was never a rule against a private, human-facing provenance record
describing its own real source, and applying it there would make provenance
unable to do the one job it exists for: letting a later reader verify where a
case actually came from.

## 24. Sanitization must sweep every reviewer-visible field, not only the diff and its formulations

The third review cycle on this batch found the sanitization fix (items 21-23)
had covered the diff and the grader's `equivalent_formulations`, and still
missed two other places the same real prose and real domain nouns reached a
reviewer-visible packet: `sources.repository_instructions[].summary` reused the
real reviewer's own phrasing ("abstract away the calls it needs to make",
"deferred-by-default semantics") almost verbatim, and one packet's
`change_contract` kept the real source's own domain noun (`enlistment`) in three
fields the earlier pass never touched.

The same cycle also found a fourth packet (`setup-service-path-gateway`) carried
a no-op diff line — an identical `-`/`+` pair — that made its before-state
impossible: the pre-image called a zero-argument constructor while the very next
line inside the same hunk already referenced a dependency that constructor could
not have had. This defect predates every sanitization commit; it was present in
the very first draft and simply went unnoticed until a cycle checked the diff's
internal coherence rather than its wording.

Both are now fixed. The lesson generalizes past this specific batch: **a
minimization or a rename must be swept across the whole packet - goal,
acceptance criteria, non-goals, preserved behaviors, repository instructions,
named documents, nearby patterns, and context - not only the diff and the
formulations that happen to be the field a grader reads.** A packet has many
prose fields, and a real term or a real reviewer's sentence can hide in any of
them. Nothing mechanical catches this today; it took three independent review
passes on one four-case stratum to find every instance, which is itself evidence
that curation discipline alone is not a durable defense and a future population
batch should expect the same scrutiny.
