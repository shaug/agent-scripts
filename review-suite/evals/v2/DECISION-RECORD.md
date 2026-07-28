# v2 mechanism decision record

`decision_record_version: 1.0`. Reads `FAILURE-TAXONOMY.md` as its evidence base
and turns each classified cause into an explicit disposition for every mechanism
proposed in #51–#57: retain, narrow, split, merge, defer, or close. Every
threshold below is a **proposal** requiring owner confirmation, not a settled
fact — see the "Why these are proposals, not settled numbers" note at the end of
each entry that carries one.

This record changes no review prompt, schema, rubric, orchestration, or caller
runtime behavior by itself. It specifies what #51–#57 must implement; the child
tickets carry out the actual change.

## #51 — Make clean verdicts require passing validation and current-head lens evidence

**Disposition: retain, unchanged.**

- **Baseline cases and metrics demonstrating the problem.** None from the scored
  stochastic corpus — this is a deterministic protocol/validator defect,
  independently evidenced by the reproduction already documented in #51's own
  body: (1) a schema-valid `clean` result can pair with every focused/full
  validation entry set to `failed`, because pair validation never cross-checks
  packet validation status against aggregate verdict; (2) the orchestrator's
  re-review matrix allows a correctness-fix or code-simplicity-fix path to reach
  a new-head aggregate without a fresh solution-simplicity execution for that
  exact head. Per #59's own text, a known deterministic contradiction may be
  retained without a stochastic recall delta, and this is exactly that case.
- **Why existing behavior or a smaller change is insufficient.** The hole is
  structural: nothing in `review-result.schema.json` v1.0 or
  `review-suite/scripts/validate.py` ties `verdict: clean` to the packet's own
  validation evidence or to a completed, candidate-bound lens execution.
  Documentation alone cannot close a schema-level gap that a well-intentioned
  caller can trip on by construction.
- **Smallest proposed intervention and canonical owner.** Exactly the behavior
  already specified in #51's "Required contract behavior" section: cross-check
  packet validation status against verdict (no `clean` may pair with a `failed`
  or `unavailable` required validation entry), and add a minimal
  `lens_executions` evidence array to the aggregate result recording, for each
  of the three required lenses, its name, head SHA, comparison-base SHA,
  verdict, and freshness. Canonical owner:
  `review-suite/contracts/review-result.schema.json`,
  `review-suite/scripts/validate.py`, and `review-suite/CONTRACT.md`'s
  verdict-semantics section; `review-code-change/SKILL.md`'s orchestration
  matrix.
- **Exact contract/version and compatibility impact.**
  `review-result.schema.json`: `1.0 → 1.1` (additive `lens_executions` array
  plus the packet/verdict cross-check rule; no packet schema change). Atomic
  migration across the bundled skill copies via `just sync-contracts`; no
  dual-schema layer; stale v1.0 aggregate evidence is rejected with a clear
  migration error, exactly as #51 already specifies.
- **Deterministic positive and negative fixtures.** The 11 fixtures already
  enumerated in #51's "Required tests" section (failed focused/full/unavailable
  validation paired with an otherwise-clean result; missing, duplicate, or
  stale-head/stale-base lens execution; the two head-changing-fix restart cases;
  unchanged-head base-drift retention; stale v1.0 rejection).
- **Scored corpus slice expected to change.** None. This is a deterministic
  invariant validated by canonical fixtures, not a stochastic recall target;
  replaying the frozen v1 baseline's 15 scored cases at v1.1 must produce
  byte-identical verdicts and findings for every case, because none of them
  exercises a failed/unavailable validation entry or a stale lens execution —
  the new validator rule only rejects previously-invalid pairs that no v1 case
  contains.
- **Preregistered quality/stability/non-regression target.** Non-regression
  only: the 15 frozen v1 cases must replay identically at v1.1 (see above). No
  quality or stability target applies — there is nothing stochastic to measure.
- **Maximum acceptable latency and cost impact.** Negligible — no new reasoning
  pass, only a structural evidence field and a validator rule. *Proposal:* cap
  any measured latency/cost delta on the `s1` stratum at 5%, as a sanity ceiling
  rather than an expected effect; if a re-run of `s1` at v1.1 exceeds it, treat
  that as a signal the orchestration matrix change did more than intended, not
  as an acceptable cost of the fix.
- **Required ablation and removal rule.** None in the normal sense — a
  deterministic invariant closing a known contradiction cannot be "ablated"
  without reintroducing that contradiction. The only removal condition is proof
  that the contradiction is unreachable through some other structural mechanism,
  which no evidence here supports; #57 verifies the invariant holds rather than
  testing whether removing it changes anything.

## #52 — Evaluate compact review coverage, impact, and risk evidence

**Disposition: narrow.** The full changed-surface ledger, acceptance-trace,
risk-profile, and aggregate-coverage apparatus in #52's current body is **not**
justified by the baseline and is dropped. Only one baseline case demonstrates a
consumer/impact-traversal gap.

- **Baseline cases and metrics demonstrating the problem.**
  `dependency-strictness-propagation` (`s1`): `mean_recall: 0.0`,
  `ever_referred_root_cause_ids: []` across all 5 attempts — a confident,
  zero-ambiguity miss. Root cause `rc.sibling-call-site-keeps-permissive-mode`:
  a changed shared helper (`dependency_finalized`) has two call sites, one
  hardened by the diff and one left permissive, and every attempt missed the
  second one.

- **Why existing behavior or a smaller change is insufficient.** The current
  packet gives a complete diff and repository access but has no structural
  requirement that a reviewer account for other call sites of a symbol whose
  behavior changed. Five for five attempts omitted the same sibling call site,
  which is a systematic, repeatable gap, not incidental variance a prompt-only
  nudge would reliably fix without something for a validator to check.

- **The smallest proposed intervention and canonical owner.** Add exactly one
  small, additive evidence array to the review result —
  `consumer_impact_evidence` — instead of #52's original changed-surface ledger,
  acceptance trace, and risk-profile triad:

  ```jsonc
  "consumer_impact_evidence": [
    {
      "changed_symbol": "string, the changed shared symbol/contract",
      "location": "string, its defining location",
      "consumer_search_evidence": [
        { "location": "string", "detail": "string, what was inspected and found" }
      ],
      "disposition": "all_consumers_consistent | inconsistency_found | no_other_consumers"
    }
  ]
  ```

  #52 owns only the **schema and validator**: the structural shape of this array
  and the rule that `clean` requires it to be non-empty, or explicitly justified
  empty, whenever the correctness lens's own traversal pass (owned by #53)
  determines a changed symbol has other call sites. #52 does **not** own the
  lens behavior that populates it — that ownership boundary is what keeps this
  ticket and #53 from duplicating each other, per the scope/completeness audit
  requirement that no sibling duplicate an owner. No packet schema change is
  needed: the packet already ships the complete diff and live repository access
  is available to the reviewing agent, so no new packet-side ledger is required
  to enable consumer search.

- **Exact contract/version and compatibility impact.**
  `review-result.schema.json`: `1.1 → 1.2` (additive `consumer_impact_evidence`
  array; no packet schema change). Same atomic-migration, no-dual-layer
  precedent as #51.

- **Deterministic positive and negative fixtures.** A sanitized fixture pair
  shaped like `dependency-strictness-propagation`: a changed shared
  permissive/strict helper with a sibling call site. Positive: the result's
  `consumer_impact_evidence` identifies and inspects both call sites → validator
  accepts `clean`. Negative: the same fixture with the evidence array omitted,
  or naming only the hardened call site → validator rejects `clean`.

- **Scored corpus slice expected to change.** None directly from #52 alone — #52
  adds only the structural evidence capability; it ships no new reviewer
  behavior and therefore does not by itself move any case's recall. The slice
  this schema addition exists to enable — `dependency-strictness-propagation` —
  only changes once #53's traversal pass (built on this schema) is implemented
  and re-scored. Recording this plainly here rather than overclaiming #52's own
  effect.

- **Preregistered quality/stability/non-regression target.** Non-regression
  only, and only deterministic: the schema addition must not change any lens's
  verdict on any of the 15 frozen v1 cases, because none of them has a `clean`
  result whose validity should depend on this new field being present (no other
  v1 case involves a changed symbol with sibling call sites per its expectation
  record). No quality/stability target applies to #52 itself.

- **Maximum acceptable latency and cost impact.** Negligible on its own — no new
  model reasoning, only a schema/validator change. *Proposal:* no measurable
  per-attempt cost delta expected from #52 in isolation; any observed delta
  belongs to #53's passes, not this ticket's schema addition.

- **Required ablation and removal rule.** Tied to #53 and #57: if, once #53's
  traversal pass is implemented and `s1` is re-scored,
  `dependency-strictness-propagation` (or an equivalent v2 case) does not move
  from miss toward matched or a genuinely improved referral, and no other case
  benefits from this evidence array, remove it as unjustified single-case
  structural complexity. This is the explicit removal condition #57's ablation
  protocol must check.

## #53 — Evaluate correctness traversal, verification sufficiency, and specialist routing

**Disposition: retain the traversal and verification-sufficiency work; drop
specialist routing entirely.** Nothing in the baseline supports specialist
modules; inventing them now would be exactly the unevidenced expansion #59's own
non-goals forbid.

- **Baseline cases and metrics demonstrating the problem.** Both confident
  misses in `s1`:

  - `dependency-strictness-propagation` (traversal) — see #52's entry above.
  - `stale-claim-release-guard` — `mean_recall: 0.0`,
    `ever_referred_root_cause_ids: []` across all 5 attempts. Root cause
    `rc.guard-skipped-when-snapshot-owner-absent`: the ownership check in
    `_release` is conditional on the snapshot having had an owner, so the exact
    scan-then-claim interleaving the change exists to guard against skips the
    comparison. The added test "starts from an owned entry, so it exercises the
    branch that was already safe and passes" — a happy-path test accepted as
    sufficient evidence for an untested concurrency edge case.

  No baseline case demonstrates a need for the specialist modules (security,
  concurrency-as-a-separate-routed-module, compatibility/migration, operations,
  or UI) as originally drafted in #53. The concurrency miss above is fully
  explained by a verification-sufficiency gap, not by the absence of a routed
  concurrency specialist — the reviewer never needed a separate specialist
  context; it needed to ask whether the existing test could fail for the stated
  trigger.

- **Why existing behavior or a smaller change is insufficient.** Both misses
  were 5-for-5 across independent fresh processes with no partial/referred
  attempts, which rules out incidental prompt variance as the explanation — the
  omission is systematic. Neither omission is addressed by #52's schema addition
  alone; #52 gives the evidence *shape*, but nothing in the current
  `review-correctness` rubric instructs the lens to actually walk to sibling
  call sites or to interrogate whether a passing test could fail for the claimed
  risk.

- **The smallest proposed intervention and canonical owner.** Add exactly two
  required passes to `review-correctness`'s rubric, replacing #53's original
  four-pass draft:

  1. **Impact/consumer-traversal pass** — for each changed shared symbol or
     contract, search for other call sites/consumers and populate #52's
     `consumer_impact_evidence`. This is #53's only claim on #52's schema; #53
     does not add a second schema for the same evidence.

  2. **Verification-sufficiency pass** — for each claimed validation command or
     test touching a materially risky change, ask whether it would actually fail
     for the specific trigger the change addresses, and record the answer in a
     new, small evidence array owned entirely by #53:

     ```jsonc
     "verification_sufficiency_evidence": [
       {
         "claimed_test_or_command": "string",
         "exercises_material_risk": "yes | no | not_applicable",
         "reasoning": "string, what triggering condition was or was not exercised"
       }
     ]
     ```

  **Drop entirely:** the "risk-routed specialist pass" and the "Specialist
  modules" section (security/authorization, concurrency, contracts/migration,
  operations, UI). No case in the baseline demonstrates that a routed specialist
  context — as opposed to the two general passes above — is needed to catch
  either confident miss. Reintroducing specialist routing would need its own
  baseline evidence and its own decision-record entry; it does not get one from
  this ticket's evidence.

  Canonical owner: `skills/review-correctness/SKILL.md` and its references;
  `review-suite/contracts/review-result.schema.json` for the new evidence array.

- **Exact contract/version and compatibility impact.**
  `review-result.schema.json`: `1.2 → 1.3` (additive
  `verification_sufficiency_evidence` array on correctness-lens results; no
  packet schema change). Same atomic-migration precedent.

- **Deterministic positive and negative fixtures.** Two pairs:

  1. The `dependency-strictness-propagation`-shaped pair already specified under
     #52 (owned jointly at the schema level by #52, populated by #53's traversal
     pass).
  2. A new pair shaped like `stale-claim-release-guard`: a guard-release
     function with an owner-absent interleaving edge case. Positive: the
     added/existing test exercises the owner-absent branch, and
     `verification_sufficiency_evidence` records `exercises_material_risk: yes`
     → clean. Negative: the test only exercises the already-safe owned-entry
     branch, and the evidence correctly records `exercises_material_risk: no` →
     the missing coverage produces a gating finding, not a silent `clean`.

- **Scored corpus slice expected to change.** `s1-correctness-orchestrator`'s
  `dependency-strictness-propagation` and `stale-claim-release-guard` — both are
  the direct target of this change and are expected to move from
  `mean_recall: 0.0` at re-scoring.

- **Preregistered quality/stability/non-regression target (proposal).** Given a
  5-run-per-case sample (`LIMITATIONS.md` item 36 — a single attempt moves a
  per-case `mean_recall` by a fifth), propose: at v2 re-scoring, each of the two
  target cases reaches `mean_recall ≥ 0.6` (at least 3 of 5 attempts matched),
  or the combined matched+referred rate reaches `≥ 0.8` with the referred
  attempts showing real content overlap (not a flat miss). This threshold is a
  genuine judgment call given the tiny sample and is offered as a proposal, not
  a settled number — the owner should confirm or replace it before it gates
  anything. Non-regression: neither target case's `verdict_stability` nor
  `finding_stability` may fall below its v1 floor (both are `1.0` today); the
  three clean controls (`dependency-hint-parser-coverage`,
  `post-bootstrap-module-load`, `session-continuation-summary`) must remain at
  zero false positives; and `process-isolation-assertion`'s false-alarm rate
  must not get worse than its observed 2-of-5.

- **Maximum acceptable latency and cost impact (proposal).** Two added reasoning
  passes will increase output tokens and likely latency on `s1`. *Proposal:*
  raise `s1`'s cost ceiling from $9.00 to $12.00 for the v2 re-score, and be
  prepared to raise the 300 s timeout to 450 s if a pilot run approaches it —
  both flagged explicitly as proposals needing owner confirmation, sized from
  the v1 pilot's worst observed cold cost ($0.2021/attempt) and worst latency
  (51.2 s) rather than invented.

- **Required ablation and removal rule.** #57 must run three configurations
  against `s1`: traversal pass only, verification-sufficiency pass only, and
  both together, each scored against the same two target cases plus the full
  stratum for non-regression. Remove either pass if, in isolation, it does not
  move its target case and does not measurably help any other case — this
  directly implements #57's "unique contribution beyond earlier mechanisms"
  requirement and must not be skipped in favor of only testing the combined
  configuration.

## #54 — Evaluate independent correctness discovery and per-finding validation

**Disposition: defer, unchanged.** #54's own gate text — "a remaining recall or
stability failure that one-pass changes do not solve" — is only measurable after
#53 ships and is scored. No baseline evidence exists yet for or against
independent explorers or a validator topology; inventing one now would violate
#59's own non-goal against choosing mechanisms before reading evidence that does
not yet exist. No schema delta, fixture, or threshold is drafted here. #54 stays
blocked on #53's eventual v2 scoring evidence, not on #59 itself — #59's own
closure does not by itself unblock #54.

## #55 — Migrate caller contracts and prove current-head review integration

**Disposition: defer, unchanged.** Downstream of #54's outcome (its own
"Definition status" already says so); nothing in this decision record changes
that. No schema delta, fixture, or threshold drafted.

## #56 — Operationalize adjudicated connector outcomes as review regressions

**Disposition: retain, now evidence-backed.** #56's existing intake-record and
promotion-workflow design (already specified in its own body) is not
architecturally changed by this decision record. What changes is its evidence
basis and two small guardrails.

- **Baseline cases and metrics demonstrating the problem.** A real
  connector-outcome dataset exists and the repository owner has authorized its
  use for v2-cycle analysis. **Provenance of this claim, stated plainly so it is
  auditable rather than implied:** this authorization was communicated directly
  to this ticket's implementing session by the repository owner, as part of this
  epic's delegated handoff, and is not yet recorded as a GitHub comment or other
  tracker artifact the way every other owner adjudication cited elsewhere in
  this record is (compare `LIMITATIONS.md` items 23 and 33, each of which cites
  a specific comment URL). Unlike those, this authorization has no citable
  tracker trail today. It is recorded here as a session-level owner instruction,
  not fabricated or inferred, and the repository owner should add a
  tracker-visible confirmation (a comment on #56 or #59) if a durable audit
  trail is wanted before this disposition is acted on further.
- **Reconciling this with the v1 baseline's recorded exclusion.**
  `LIMITATIONS.md` item 1 records that a different private repository carrying
  connector review history "was identified and deliberately excluded on
  third-party authority and disclosure grounds" from **#58's frozen v1 corpus**,
  and "was not read, and nothing here derives from it." That exclusion is scoped
  to what #58 curates into `review-suite/evals/baseline/v1/` — a specific,
  frozen, scored corpus with its own sourcing and retention rules — and stays
  exactly as decided; this decision record does not reopen, reverse, or
  contradict it. The authorization described above is a separate, later-granted
  permission scoped only to #56's own v2-cycle intake/analysis workflow, not to
  populating, rescoring, or otherwise touching the v1 corpus. Whether the two
  describe the same underlying source repository or two different ones is
  deliberately not stated here in either direction — doing so would risk
  narrowing the generic description into something identifying, which the
  owner's disclosure boundary forbids regardless of the answer.
- **Explicit non-retroactivity note.** This source is a v2-cycle addition. It
  does **not** retroactively modify, extend, or rescore
  `review-suite/evals/baseline/v1/`, which stays exactly as merged and frozen in
  #58. `frozen-configuration.json`'s `connector-escape` stratum entry remains
  `state: deferred_not_satisfied` with zero attempts; nothing in this decision
  record changes that entry, and any future connector stratum built from this
  new source is separate v2-only work with its own preregistered cost ceiling,
  not a retroactive fill of the v1 gap.
- **Why existing behavior or a smaller change is insufficient.** Before this
  authorization, #56 had no evidence base at all beyond the deferred (and
  explicitly zero-data) connector stratum, which is why it was previously
  provisional. The workflow it already specifies (intake record, promotion
  steps, optional scoped-rule escalation gated on demonstrated need) does not
  need architectural change now that evidence exists — it needs the sourcing
  boundary stated explicitly and one mechanical guardrail added.
- **The smallest proposed intervention and canonical owner.** No schema
  redesign: #56 continues to reuse the corpus/expectation/provenance contracts
  already owned by #50/#58 (`review-suite/evals/contracts/*.schema.json`). Add
  one small, mechanical guardrail to #56's intake validator: when a curation
  record's `provenance.source_class` is `private_authorized`, its public-facing
  `source_description` field must match an allow-listed generic phrase (e.g. "a
  private, owner-authorized connector-review source") and must fail closed if it
  contains a path-like token (`/`), a bare hostname, or any string matching a
  configured deny-list of known-sensitive identifiers. This is a cheap,
  mechanical backstop for a disclosure boundary that is otherwise only enforced
  by curation discipline — consistent with this repository's own observation
  (`LIMITATIONS.md` items 21–24, 29–31) that curation discipline alone does not
  reliably catch every leak.
- **Exact contract/version and compatibility impact.** No packet/result schema
  version change. The corpus/expectation/provenance contracts are unchanged;
  only #56's own intake validator (its own code, not a shared contract) gains
  the guardrail above.
- **Deterministic positive and negative fixtures.** #56's already-specified
  fixture list (positive, negative, duplicate, unresolved, restricted-data,
  promotion-decision) plus one new negative fixture: a `private_authorized`
  curation record whose `source_description` contains a disallowed token →
  intake validation fails closed.
- **Scored corpus slice expected to change.** None directly — #56 is a
  workflow/tooling ticket, not itself scored against `s1`/`s2`/`s3`. Any future
  regression case sourced from the new connector data is separate, later work
  with its own preregistered cost ceiling; #56 does not commit to running one
  now.
- **Preregistered quality/stability/non-regression target.** Unchanged from
  #56's own body: any rubric/instruction change promoted through this workflow
  must independently pass #56's already-specified "measure before changing
  guidance" step and #57's preregistered gates. No new target is added here.
- **Maximum acceptable latency and cost impact.** Not applicable — #56 changes
  no reviewer runtime behavior by itself.
- **Required ablation and removal rule.** Not applicable to #56 itself; any
  rubric change it later promotes is subject to #57's ablation/removal rule, as
  #56's own body already states.

## #57 — Run the preregistered review v2 ablation and integration closeout

**Disposition: defer, unchanged.** Downstream of #55 and #56; #57's own
"Definition status" already names #59 as its gate for the exact scored-v2
configuration, which this record and `gate-manifest.json` provide. One prose
correction is in scope: #57's current body reads "Run the evidence-backed v2
experiment approved by #58" in its Goal section. #58 curated the frozen v1
corpus and baseline; it is #59 — this ticket — that approves the v2 mechanism
set and gate manifest #57 executes against. That single stale cross-reference is
corrected in #57's revised body; #57's disposition, required inputs, and
acceptance criteria are otherwise unchanged.

## Net effect on the dependency graph

Applying the dispositions above to the native graph: `blockedBy #59` is removed
from #51 once #59 closes, leaving #51 with no open `blockedBy` edge. Every other
child (#52 through #57) keeps its existing `blockedBy` edge onto its current
predecessor (#52→#51, #53→#52, #54→#53, #55→#54, #56→#52, #57→#55,#56), all of
which stay open. **#51 is therefore the only open issue in this epic with zero
open blockers once #59 closes** — the expected net effect #59's own text names.
See `audits/dependency-sequencing-audit.md` for the verified read-back
confirming this against the live graph after the edge and body mutations are
applied.
