# Discriminating-case validation (#89)

This validates whether the two new, harder `s1-correctness-orchestrator` cases
sourced for #89 actually discriminate between the relevant pass enabled and
disabled - the question #57's ablation matrix left open for
`dependency-strictness-propagation` and `stale-claim-release-guard`. It does not
modify `S1-ABLATION-MATRIX.md`, `FROZEN-V2-CONFIGURATION.md`,
`CLOSEOUT-REPORT.md`, `gate-manifest.json`, `DECISION-RECORD.md`,
`FAILURE-TAXONOMY.md`, `audits/`, or `baseline/v1/`. It does not modify
`skills/review-correctness/`, the traversal pass, or the verification-
sufficiency pass, and it does not decide #52/#53's disposition - see
`discriminating-case-validation-frozen-configuration.md` for the preregistered
configuration and cost ceiling this run held to.

## Result, stated plainly up front

**One candidate discriminates; the other does not.**

- `artifact-promotion-environment-shortcut` (traversal-pass sibling): a real,
  reproducible gap. `mean_combined_recall` 1.0 with the traversal pass enabled
  vs. 0.4 with it disabled, 5 runs each, zero evaluation failures either way.
- `audit-log-flush-keyword-probe` (verification-sufficiency-pass sibling): no
  gap. `mean_combined_recall` 1.0 in both configurations, 5 runs each, zero
  false positives or evaluation failures either way - the same pattern
  `S1-ABLATION-MATRIX.md` already reported for `stale-claim-release-guard`.

This is reported exactly as it came out: an asymmetric result, not forced into a
uniform conclusion in either direction.

## A defect found and fixed before trusting the traversal-case result

The first scored run of `artifact-promotion-environment-shortcut` under the
verification-only (traversal-disabled) configuration produced a result that
looked like a discriminating gap by the numbers (`mean_combined_recall` 1.0 ->
0.2) but was not trustworthy evidence: 4 of 5 attempts raised a `blocking`
finding unrelated to the intended root cause, claiming that `decide_promotion`'s
own `ledger.lookup(record.external_ref)` call could return `None` for an
artifact with no `external_ref`, causing `artifact_promotable`'s
`external_proof is not None` check to fall through to the permissive marker-only
path. Reading the raw attempts directly (not just the aggregate) surfaced this:
none of the four false positives said anything about the rollout module at all -
they were entirely about a different, unintended ambiguity in the packet's own
gate function, and none of the five attempts under the real, unablated
configuration raised it even once.

The packet never stated what `ledger.lookup` returns for a record with no
`external_ref`, so "returns `None`" was a reasonable inference, and the diff's
own added test
(`test_decide_promotion_holds_a_verification_required_artifact_without_ledger_proof`)
only proves the outcome (`artifact.held`), not the mechanism - a reviewer
reading it can't rule out the `None`-fallthrough reading from the diff alone.
This was an integrity gap in the case's construction, not evidence about either
pass, and reporting the contaminated `0.2` figure as "the traversal pass
discriminates" would have been exactly the kind of false-looking-real result
this ticket exists to avoid.

**Fix applied** (both committed in the same revision, before any further
scoring): the packet's `context.data` now states the `ledger.lookup` contract
explicitly - it always returns a proof object, `verified: False` for a missing
or unconfirmed ref, never bare `None` - and the executable oracle's `_Ledger`
was corrected to match (it previously modelled `lookup(None)` as returning
`None`, inconsistent with the packet's own added test). Both changes are visible
in this same commit's diff, under
`reviewer/artifact-promotion-environment-shortcut/` and
`scripts/evals/oracles/`, and the case's `head_sha` was re-minted to mark the
revision. `python3 -m unittest review-suite.scripts.tests.test_eval_oracles` and
`python3 review-suite/scripts/evals/audit_corpus.py` both pass against the
corrected packet.

The original (contaminated) run's raw reports were not committed; only the
corrected rerun's reports are retained as evidence, per the table below.

## Sourcing and sanitization (per #58's discipline, reused exactly)

Both cases are minimized from real, adjudicated, public review findings in
`shaug/atelier` - the same public source #58's corpus draws from - rewritten
from scratch against fictional subjects, carrying no business logic, domain
identifier, customer context, credential, or hidden reasoning. Neither case was
sourced from, derived from, or informed by the private connector-review source
referenced in #56; that source was not consulted, named, or considered at any
point in sourcing either case.

| Case                                      | Source                                                                     | Disposition                                                                                  | Sanitization                                                                                                                                                                                                                                                                                                                                                                      |
| ----------------------------------------- | -------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `artifact-promotion-environment-shortcut` | `shaug/atelier` PR 315, review comment 2866874599 (owner-authored, public) | Accepted in reply 2866898151 ("Good catch; this is now aligned"), naming the two tests added | Rewritten against a fictional artifact-release system. Untouched sibling path is two calls deep (`resolve_rollout_environment` -> `_pick_rollout_defaults` -> `artifact_promotable`) in a module named for staging/rollout defaults, not dependency/promotion checking - deliberately less salient than `dependency-strictness-propagation`'s one-hop `pipeline/dependencies.py`. |
| `audit-log-flush-keyword-probe`           | `shaug/atelier` PR 755, review comment 3031027866 (owner-authored, public) | Accepted in reply 3031075465, describing the tightened regression                            | Rewritten against a fictional audit-log flush module. Test insufficiency is carried by a mocked session that grants success on a keyword match in the request text, rather than by the test's initial state (the original case's shape) - deliberately less visually obvious than `stale-claim-release-guard`'s owned-entry-only test.                                            |

Full provenance records (retention authority, adjudication trail, sanitization
statement) are committed at
`review-suite/evals/strata/s1-correctness-orchestrator/private/provenance/artifact-promotion-environment-shortcut.json`
and `.../audit-log-flush-keyword-probe.json`. Each case's materiality is also
independently adjudicated by an executable oracle
(`review-suite/scripts/evals/oracles/artifact_promotion_environment_shortcut.py`,
`.../audit_log_flush_keyword_probe.py`), confirming the stated requirement fails
against the candidate reproduction and holds once corrected - verified by
`python3 -m unittest review-suite.scripts.tests.test_eval_oracles`.

## Validation runs and figures

Configuration, runtime, and cost ceiling frozen in
`discriminating-case-validation-frozen-configuration.md` before any scored
output was examined. All four runs below: `grader_version 1.1`,
`corpus_version 0.2-s1-populated`, `runs_per_case 5`, `runtime claude 2.1.92`,
`model claude-opus-4-6[1m]`, zero evaluation failures of any kind in any run.

### `artifact-promotion-environment-shortcut` (traversal pass)

| Configuration                                            | `mean_recall` | `mean_combined_recall` | False positives | False-clean | `verdict_stability` |
| -------------------------------------------------------- | ------------- | ---------------------- | --------------- | ----------- | ------------------- |
| Both passes together (traversal enabled, real `skills/`) | 0.0           | **1.0**                | 0/5             | 0/5         | 1.0                 |
| Verification-only (traversal **disabled**)               | 0.0           | **0.4**                | 0/5             | 3/5         | 0.6                 |

Raw attempts confirm the shape directly: with the traversal pass, all 5 attempts
named the untouched `_pick_rollout_defaults`/`resolve_rollout_environment` call
chain (referred, surface-relevant). Without it, only 2 of 5 attempts found it;
the other 3 returned `clean`, missing the defect entirely rather than raising it
incorrectly or elsewhere - a clean, uncontaminated miss, unlike the pre-fix run.
Committed raw reports:
[`discriminating-case-artifact-promotion-both-together.report.json`](discriminating-case-artifact-promotion-both-together.report.json),
[`discriminating-case-artifact-promotion-verification-only.report.json`](discriminating-case-artifact-promotion-verification-only.report.json).

**This is a real, reproducible discriminating gap.** It is the first evidence
anywhere in this epic that the traversal (consumer/impact) pass changes reviewer
behavior on a case built to need it - the two prior target cases
(`dependency-strictness-propagation`, and this same case's own owning
mechanism's other target) never showed this. Sample size is 5 attempts per
configuration; a gap this size (1.0 vs 0.4, 5/5 vs 2/5) is unlikely to be pure
noise but a larger run would sharpen the estimate.

### `audit-log-flush-keyword-probe` (verification-sufficiency pass)

| Configuration                                                           | `mean_recall` | `mean_combined_recall` | False positives | False-clean | `verdict_stability` |
| ----------------------------------------------------------------------- | ------------- | ---------------------- | --------------- | ----------- | ------------------- |
| Both passes together (verification-sufficiency enabled, real `skills/`) | 0.0           | **1.0**                | 0/5             | 0/5         | 1.0                 |
| Traversal-only (verification-sufficiency **disabled**)                  | 0.0           | **1.0**                | 0/5             | 0/5         | 1.0                 |

All 10 attempts (5 per configuration) named the retry-reuses-a-stale-script root
cause, referred and surface-relevant, with zero false positives and zero misses
in either configuration. Committed raw reports:
[`discriminating-case-audit-log-flush-both-together.report.json`](discriminating-case-audit-log-flush-both-together.report.json),
[`discriminating-case-audit-log-flush-traversal-only.report.json`](discriminating-case-audit-log-flush-traversal-only.report.json).

**This candidate does not discriminate**, even after a genuine, disguised-mock
construction and a full validation pass. Reported as a plain null result:
disguising the test-insufficiency shape behind a mocked session rather than the
original case's initial-state shape was not, on this evidence, enough to make
the verification-sufficiency pass's own explicit instruction the deciding factor
\- a capable reviewer already reasons about retry safety and mock fidelity
without being told to run a named "verification-sufficiency" pass, on this case,
at this sample size.

## What this means for #52/#53 (report only, no disposition decided here)

- **Traversal pass (consumer/impact-traversal, #52/#53):** now has one real,
  demonstrated case behind it - `artifact-promotion-environment-shortcut` shows
  a reproducible recall drop (1.0 -> 0.4) when the pass is disabled, unlike
  either of its two prior target cases. This does not retroactively validate
  `dependency-strictness-propagation` or the schema's original justification in
  `DECISION-RECORD.md`; it is new, independent evidence found by deliberately
  sourcing a harder case.
- **Verification-sufficiency pass (#53):** still has no case in this corpus
  demonstrating unique causal contribution, even after a genuine, disguised
  construction specifically designed to be harder than
  `stale-claim-release-guard`. Combined with `S1-ABLATION-MATRIX.md`'s existing
  finding of a real false-positive regression (`session-continuation-summary`,
  3/5, independently reproduced in the confirming rerun) when this pass runs in
  isolation, the evidentiary case for this specific pass, as currently
  instructed, is weaker after this validation than before it - a candidate built
  to be more likely to need it did not need it.
- Whether to keep, simplify, or remove either pass, and whether to revise
  `DECISION-RECORD.md`'s wording, is the repository owner's decision. This
  record only reports what a genuine attempt to find harder, discriminating
  evidence actually found.

## Cost ceiling and actual spend

Preregistered ceiling: **$5.00** (see
`discriminating-case-validation-frozen-configuration.md`). Six scored
real-runtime runs were executed against this ceiling - four trustworthy final
runs plus the two-run pre-fix pass whose result was discarded as contaminated
(its cost still counts against this ticket's own spend, since real money was
spent, even though its output was not used as evidence):

| Run                                                    | Attempts | Cost (USD)    | Kept as evidence?        |
| ------------------------------------------------------ | -------- | ------------- | ------------------------ |
| Traversal case, both-together (pre-fix, discarded)     | 5        | 0.3689225     | No - contaminated packet |
| Traversal case, verification-only (pre-fix, discarded) | 5        | 0.74949       | No - contaminated packet |
| Verification case, both-together                       | 5        | 0.627549      | Yes                      |
| Verification case, traversal-only                      | 5        | 0.67492525    | Yes                      |
| Traversal case, both-together (post-fix)               | 5        | 0.59849175    | Yes                      |
| Traversal case, verification-only (post-fix)           | 5        | 0.6463319999  | Yes                      |
| **Total**                                              | **30**   | **3.6657105** | -                        |

**$3.67 spent against a $5.00 ceiling, $1.33 headroom remaining, ceiling never
approached.** The extra 10 discarded-pre-fix attempts (about $1.12) were a real,
disclosed deviation from the original 20-attempt estimate, caused by finding and
fixing a genuine construction defect in the traversal case rather than by any
change in scope; the ceiling still held. No threshold, gate value, or the
ceiling itself was adjusted after seeing any scored output.
