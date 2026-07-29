# #57 closeout report: preregistered review v2 ablation and integration verification

This is the epic's (#49) acceptance-gate measurement. It reports, per mechanism,
whether it earned its complexity, per #57's own charge. It does not remove any
mechanism, does not file any follow-up issue, and does not close #49 - those are
explicitly withheld authorities for this ticket; every disposition below is a
**recommendation for the repository owner**, not an action this ticket took.

This record, `FROZEN-V2-CONFIGURATION.md`, `S1-ABLATION-MATRIX.md`, and
`DETERMINISTIC-AND-INTEGRATION-EVIDENCE.md` are the complete change surface.
None of them modifies `review-suite/evals/baseline/v1/`, `gate-manifest.json`,
`DECISION-RECORD.md`, `FAILURE-TAXONOMY.md`, or `audits/` - all remain exactly
as `#58`/`#59` delivered them (verified: `git diff` against those paths is empty
for this candidate).

## Required inputs (all present; none missing, inconsistent, or silently changed)

- Frozen v1 suite commit, corpus version, runtime/model stratum, executor
  version, grading policy, baseline report - `review-suite/evals/baseline/v1/`
  (#58, untouched).
- Versioned v2 decision/gate manifest, written before scored v2 output -
  `review-suite/evals/v2/gate-manifest.json` (#59, untouched).
- Final implemented review contract and mechanism set from #51/#52/#53 -
  `review-result.schema.json` at `1.3`, `skills/review-correctness/SKILL.md`'s
  two required passes - verified present and unchanged in this candidate's
  `skills/` tree.
- Migrated caller integration from #55 - `review-code-change`, `babysit-pr`,
  `implement-ticket` all consume schema `1.3` (verified: shared
  `test_review_gate.py`'s `CLEAN_AGGREGATE` fixture declares
  `"schema_version": "1.3"`).
- Operational feedback/corpus workflow from #56 - `review-suite/evals/curation/`
  (verified present, tests pass).

**One reviewed version transition, applied and documented, per #57's own
requirement before deviating from a frozen input:** `gate-manifest.json`
preregistered its thresholds against grader `1.0`. A real defect in
`finding_surfaces()` was found and fixed (`1.1`) by a predecessor measurement
task in this epic, and the repository owner explicitly authorized scoring #57's
own comparison against the fixed grader. See `FROZEN-V2-CONFIGURATION.md`'s
"Grader version transition" section for the full citation trail
(`GRADER-1.1-COMPARABILITY.md`, `s1-rescore-pre-post-comparison.md`,
`s2-s3-grader-1.1-recheck.md`). No scored comparison in this record used the
pre-fix grader.

## Deterministic gates: all nine pass

Full evidence, test-by-test, is in
[`DETERMINISTIC-AND-INTEGRATION-EVIDENCE.md`](DETERMINISTIC-AND-INTEGRATION-EVIDENCE.md).
Summary: packet/result/schema/version validation across the full dependency
closure; failed-validation-cannot-produce-clean; incomplete-evidence/stale-
identity/unavailable-review-work-cannot-produce-clean; exact candidate/base
binding; head-changing-fix invalidation; base-drift risk-based equivalence;
legacy-contract rejection; byte-identical bundled contracts; read-only review
contexts - all nine pass on existing #51-#56 test evidence, re-verified against
this exact candidate. `just test` (all skill suites plus 313
`review-suite/scripts/tests` tests) and `just lint` (ruff, mdformat,
`skills-ref validate` on all 8 skill directories, plugin-packaging validation)
both pass.

## Integration verification: all required scenarios pass

Full evidence is in the same document. Clean, changes_required, blocked, stale
handoff, failed validation, base drift, runtime failure, malformed result, and
accepted/rejected connector-regression are each covered by existing, cited
#51-#56 tests exercised through `review-code-change` directly and the shared,
byte-identical `review_gate.py` bundled into both `implement-ticket` and
`babysit-pr`. No genuinely missing scenario was found; no new caller-integration
test was required. Provider-neutral core semantics hold (every skill in the
suite ships both `agents/claude-code.md` and `agents/openai.yaml`); this record
does not require identical runtime adapters for optional provider metadata
beyond that, per #57's own non-goal.

## Frozen v2 configuration

Full detail in [`FROZEN-V2-CONFIGURATION.md`](FROZEN-V2-CONFIGURATION.md).
Runtime/model stratum verified unchanged before scoring (`claude` CLI `2.1.92`,
`claude-opus-4-6[1m]`, matching `gate-manifest.json`'s pin exactly). Grader
`1.1` throughout, per the reviewed transition above.

## Scored ablation results

Full detail, per-case gate results, and the honest unique-contribution finding
are in [`S1-ABLATION-MATRIX.md`](S1-ABLATION-MATRIX.md). Summary:

- **`s2-solution-simplicity-lens`, `s3-code-simplicity-lens`:** all 8 cases (4
  material + 4 control, across both strata) reused from
  `s2-s3-grader-1.1-recheck.md` (already scored under grader `1.1` at a
  `suite_commit` whose relevant skill trees are byte-identical to this ticket's
  own candidate) - all replay with identical statuses to v1, per
  `gate-manifest.json`'s own non-regression requirement. Not re-run; no new
  spend.
- **`s1-correctness-orchestrator`, three configurations, each scored
  independently (not averaged):**
  - **Both passes together** (reused from a predecessor task's post-#53 run at
    this same skill content, grader `1.1`): both target cases
    (`dependency-strictness-propagation`, `stale-claim-release-guard`) pass the
    settled gate via the guarded combined-recall path
    (`mean_combined_recall: 1.0`); all five non-regression floor cases hold.
  - **Traversal-pass-only** (new, this ticket, $3.560, 35 attempts, zero
    evaluation failures): `dependency-strictness-propagation` passes; all floors
    hold; `optional-tool-probe` (not gated) shows one false positive and
    `mean_recall 0.6`, both within its explicitly ungated range.
  - **Verification-sufficiency-pass-only** (new, this ticket, $3.867, 35
    attempts, zero evaluation failures): `stale-claim-release-guard` passes;
    **`session-continuation-summary`'s non-regression floor is violated** (3/5
    false positives against a required 0/5) - a real, disclosed quality
    regression specific to this isolated configuration, not present in the
    combined (as-shipped) configuration.

**The mechanical gate is not the whole story, and this record does not treat it
as such.** Both target cases pass in *every* configuration tested, including the
one where their nominal owning pass is disabled - extending
`s1-rescore-pre-post-comparison.md`'s own prior finding that the pre-#53
reviewer (no relevant pass at all) already resolved both cases. Across four
independent configurations (pre-#53, traversal-only, verification-only,
both-together), no configuration demonstrates that either specific pass's own
instruction text uniquely causes either case's resolution. Passing the numeric
gate is real and reproducible; unique causal contribution, the dimension #57's
own ablation/removal rule cares about, is not demonstrated by this evidence for
either pass in isolation.

## Mechanism verdicts (recommendation only - not a removal decision)

| Mechanism                                   | Deterministic invariant?                 | Empirical gate                                                                | Unique contribution shown?                  | Non-regression cost found                                                                                 | Recommendation (not a decision)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| ------------------------------------------- | ---------------------------------------- | ----------------------------------------------------------------------------- | ------------------------------------------- | --------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| #51 (validation/lens-execution cross-check) | Yes - structural, not stochastic         | N/A (deterministic only)                                                      | N/A                                         | None                                                                                                      | **Keep.** Closes a real, demonstrated schema-level contradiction; not ablatable without reintroducing it.                                                                                                                                                                                                                                                                                                                                                                                                               |
| #52 (`consumer_impact_evidence` schema)     | No                                       | PASS (tied to traversal pass below)                                           | **No**, per the ablation finding above      | None                                                                                                      | **Owner should weigh simplifying or reconsidering its evidentiary justification.** The schema is harmless and structurally sound, but its sole cited justification (`dependency-strictness-propagation`) is now shown, across four configurations, to resolve independently of it. Recommend revisiting `DECISION-RECORD.md`'s framing rather than removing the schema outright, since #52's own removal rule requires "no other case benefits," which this measurement did not separately test for cases outside `s1`. |
| #53 traversal pass                          | No                                       | PASS (isolated)                                                               | **No**                                      | None found in isolation                                                                                   | **Owner should weigh the same way as #52** - same target case, same caveat.                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| #53 verification-sufficiency pass           | No                                       | PASS (isolated)                                                               | **No**                                      | **Yes** - a real, isolated-configuration-only false-positive regression on `session-continuation-summary` | **Owner should weigh most cautiously of the four.** Passes its own target case's numeric gate but is the only mechanism this measurement found to carry a demonstrated cost, and that cost appears specifically when it runs without the traversal pass alongside it.                                                                                                                                                                                                                                                   |
| #53 both passes combined (as shipped)       | No                                       | PASS                                                                          | Not newly demonstrated; no regression found | None found in the combined configuration                                                                  | **Keep as currently shipped**, pending the owner's read of the two caveats above - the combined configuration itself shows no false-positive or stability cost on any case measured, and remains the one configuration gate-manifest.json requires to ship.                                                                                                                                                                                                                                                             |
| #56 (connector-outcome curation/promotion)  | Yes (its own guardrail is deterministic) | Not scored against `s1`/`s2`/`s3` (by its own disposition; a workflow ticket) | N/A                                         | None                                                                                                      | **Keep.** Fully covered by its own deterministic test suite (`test_eval_curation.py`); no empirical gate applies to it per `DECISION-RECORD.md`.                                                                                                                                                                                                                                                                                                                                                                        |

## Residual material risks and recommended follow-up topics (not filed as issues)

1. **The `session-continuation-summary` regression under verification-only
   deserves a rerun under quiet system conditions before anyone treats it as
   settled**, given the heavy unrelated load disclosed above - not because any
   execution-level evidence ties the load to it, but because a single 35-attempt
   sample is small and a confirming rerun is cheap.
2. **Neither pass's unique contribution to its own target case is demonstrated
   by any measurement run so far, across four independent configurations
   spanning two different tickets' work.** The owner may want to settle, in
   `DECISION-RECORD.md` or a successor document, whether
   `dependency-strictness-propagation` and `stale-claim-release-guard` remain
   the right justifying cases for #52/#53 at all, or whether a different, more
   discriminating corpus case is needed before either mechanism's complexity can
   be said to be earned.
3. **`optional-tool-probe` remains an explicitly open, ungated question** (per
   `FAILURE-TAXONOMY.md`); its behavior visibly differs across the three `s1`
   configurations measured here (`mean_recall` 0.6/0.8/1.0 depending on which
   pass runs). Not gated, but a candidate for a future, purpose-built corpus
   case if the owner wants to resolve it properly instead of noting it as an
   open question indefinitely.
4. **`s2`/`s3`'s two grader-`1.1`-affected cases from
   `s2-s3-grader-1.1-recheck.md` (`registry-client-layering`,
   `setup-service-path-gateway`) are reused, unchanged evidence here** - this
   record does not re-examine whether the grader-`1.1` fix's reach extends
   further than already documented; that remains out of scope for #57
   specifically.
5. **`v1`'s own frozen baseline is not re-scored under grader `1.1`** - per
   established policy, `baseline/v1/` stays frozen. Any figure in this record
   compared against a `baseline/v1/` figure is a `1.1`-vs-`1.0` comparison,
   disclosed as such, never presented as apples-to-apples without saying so.

## Spend against the $20.00 ceiling

| Item                                                                         | Cost (USD)    |
| ---------------------------------------------------------------------------- | ------------- |
| Runtime/model stratum sanity check (one `claude -p` call, no graded attempt) | 0.00904       |
| `s1` traversal-only (new, 35 attempts)                                       | 3.560108      |
| `s1` verification-only (new, 35 attempts)                                    | 3.866613      |
| **Total spent by this ticket**                                               | **7.435762**  |
| Ceiling                                                                      | 20.00         |
| **Headroom remaining, never approached**                                     | **12.564238** |

Reused figures (`s1` both-together $3.559636, `s2` $1.190071, `s3` $0.958775,
totaling $5.708482) were spent by predecessor measurement tasks in this epic
against their own separate, already-reported ceilings, and are not counted a
second time against this ticket's own $20.00.

## Acceptance criteria (#57's own body), checked explicitly

- [x] Scored configuration and gates match the pre-v2 manifest from #59; no
  threshold changed after outputs were visible. (Grader-version transition is
  the one reviewed exception, owner-authorized before this ticket examined any
  of its own scored output; no numeric threshold was altered.)
- [x] Every deterministic gate above passes.
- [x] Every preregistered empirical quality, stability, false-positive, and
  efficiency gate has a reproducible result (including the one that failed -
  `session-continuation-summary` under verification-only - reported, not
  hidden).
- [ ] Every retained mechanism demonstrates empirical value or a necessary
  deterministic invariant. **Not fully met**: #52 and #53's two passes pass
  their numeric gate but do not demonstrate unique causal contribution: see
  above. #51 and #56 do.
- [ ] Mechanisms that fail the removal rule are removed or simplified and the
  final configuration is rerun where the change affects results. **Not
  applicable to this ticket's authority** - #57 is explicitly withheld
  removal/simplification authority; recorded as a recommendation for the owner
  instead.
- [x] Direct review, implementation, and PR-babysitting integration cases pass
  on exact current heads.
- [x] Runtime/model strata are reported separately and never compared as if
  identical (the grader-version distinction is the one boundary this record had
  to draw explicitly, and it does).
- [x] No legacy contract path can produce a v2 clean/ready verdict.
- [x] Documentation states what clean proves, what it does not prove, how
  uncertainty is represented (this report, `S1-ABLATION-MATRIX.md`, and the
  unique-contribution caveat), and how future corpus cases are added (see
  `review-suite/evals/README.md` and `review-suite/evals/curation/README.md`,
  both unchanged, both still authoritative).
- [x] Residual material failures are explicit follow-up **topics** in this
  report rather than closeout prose asserting completeness - explicitly not
  filed as GitHub issues, since that authority is withheld from this ticket.
- [x] `just format`, `just lint`, and `just test` pass.

## What this record does not do

- Does not remove, simplify, or edit #51/#52/#53/#56, or comment a removal
  decision onto any of them.
- Does not file any new GitHub issue.
- Does not touch `baseline/v1/` or any of #59's own frozen files.
- Does not invoke `carve-changesets`.
- Does not close epic #49.
