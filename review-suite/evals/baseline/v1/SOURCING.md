# Ground-truth sourcing, sanitization, and the population batches

Every case in this corpus must come from a review that really happened and
really adjudicated the finding. Nothing may be invented: a corpus of fabricated
escapes would reproduce the exact defect this work exists to correct, and would
then miscalibrate every gate that reads the baseline.

## Sources used

| source                | visibility | what it supplies                                                                                                                   |
| --------------------- | ---------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `shaug/atelier`       | **public** | 899 pull-request review comments, all authored by the repository owner, across ~354 pull requests.                                 |
| `shaug/agent-scripts` | **public** | This suite's own delivery history, including a defect that survived an aggregate `clean` review verdict and was then caught by CI. |

In `shaug/atelier` the reviewer is the repository owner and the candidates are
in their own repository. This is human review of a real candidate with a real
adjudication trail — the review comment states the concern and the required
outcome, and acceptance is evidenced by a follow-up reply naming the
implementing commit. It is *not* two-party review, and it is not connector
review. Both facts are stated in every stratum label and in the limitations
record.

## Sources deliberately not used

### The private connector-bearing repository

A private repository that does carry genuine connector review history was
identified and **deliberately excluded** on third-party authority and disclosure
grounds. It is not named here, it was not read, and nothing here derives from
it. The consequence — the connector stratum is deferred, not satisfied — is
limitation 1 in [LIMITATIONS.md](LIMITATIONS.md).

### `shaug/eldritchdark`

`shaug/eldritchdark` was available as a source (roughly 361 reviews) and was
**not read at all**. Only its visibility was checked: it is **private**, while
this repository is public.

This was a deliberate choice, not an oversight. Retention requires that a case
carry no business logic, domain identifier, customer context, credential,
secret, or hidden reasoning, and when a case cannot be minimized without losing
the behaviour it demonstrates it must be dropped rather than have the rule
weakened. `shaug/atelier` is public and supplies every required case class with
clean provenance, so reading a private repository would have added disclosure
risk for no coverage gain. When in doubt, exclude.

**No content from any private repository reached any artifact in this
repository.** No review comment, diff, or file from a private repository was
opened.

## Sanitization rule applied to every case

Even with public sources, no case reproduces source text. Each case is rewritten
from scratch against a fictional subject that preserves only the *failure
shape*: the requirement, the triggering condition, the surface kind, and the
material consequence. No identifier, path, symbol name, prose, or diff from the
source is copied. Provenance records the real source; the retained artifact does
not carry it.

## Case record

### `rollback-guidance-render` — pilot, unscored

| field                  | value                                                                                                                                                                                                                                                      |
| ---------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| strata                 | `pilot-orchestrator`, `pilot-solution-simplicity`, `pilot-code-simplicity` (byte-identical)                                                                                                                                                                |
| source                 | `shaug/atelier` pull request 492, review comment 2882160198, authored by the repository owner. Public.                                                                                                                                                     |
| adjudication           | The reviewer required the change; the follow-up reply (comment 2882224395) names the implementing commit and the regression tests added. Accepted, not deferred.                                                                                           |
| failure shape retained | Rendered operator guidance emits a subcommand the tool does not register, so the documented procedure fails at its first step. The accompanying test asserts the rendered shape rather than command validity, which is why a green suite did not catch it. |
| origin                 | `minimized_reproduction`                                                                                                                                                                                                                                   |
| sanitization           | Rewritten against a fictional `storectl` CLI. No source identifier, path, symbol, prose, or diff copied. No business logic, domain identifier, customer context, credential, or hidden reasoning.                                                          |
| retention authority    | Public repository, owner-authored review, no third-party or customer material.                                                                                                                                                                             |

### `status-label-normalization` — pilot, unscored, deliberately uncalibrated

| field                  | value                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| strata                 | `pilot-orchestrator` only, so the case shared with the lens strata stays byte-identical across all three                                                                                                                                                                                                                                                                                                                                                                      |
| source                 | `shaug/atelier` pull request 278, review comment 2861937742, authored by the repository owner. Public.                                                                                                                                                                                                                                                                                                                                                                        |
| adjudication           | The reviewer required the change; the follow-up reply (comment 2861947492) names the implementing commit and the regression coverage added for the exact migration shape. Accepted, not deferred.                                                                                                                                                                                                                                                                             |
| failure shape retained | A normalization step drops one legacy flag and returns early for an inactive status, leaving a second legacy flag that contradicts the canonical status, with a live consumer that admits work on that flag alone. The added tests all start from records that never carried the second flag, so the one shape the change exists to fix is untested.                                                                                                                          |
| origin                 | `minimized_reproduction`                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| sanitization           | Rewritten against a fictional record registry. No source identifier, path, symbol, prose, or diff copied. No business logic, domain identifier, customer context, credential, or hidden reasoning.                                                                                                                                                                                                                                                                            |
| retention authority    | Public repository, owner-authored review, no third-party or customer material.                                                                                                                                                                                                                                                                                                                                                                                                |
| why it exists          | Two purposes. Its packet is materially larger than the other pilot case, which separates the fixed cost of a stratum's skill closure from the variable cost of the packet — the measurement behind the cost-ceiling proposal. And it is **deliberately left uncalibrated** (`calibrated: false`) as the control for what an uncalibrated expectation reports: recall 0.0 over five attempts with nine adjudication referrals, while the reviewer gated the change every time. |

## Cases excluded, and why

| candidate                                                   | class it would have served | why excluded                                                                                                                                                                                                         |
| ----------------------------------------------------------- | -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Every candidate in `shaug/eldritchdark`                     | any                        | Private repository, not read. Public sources cover every required class, so the disclosure risk bought nothing. See above.                                                                                           |
| Every candidate in the private connector-bearing repository | connector-escape stratum   | Excluded on third-party authority and disclosure grounds. Not named, not read, not derived from.                                                                                                                     |
| The evaluator's own protocol smoke run                      | none                       | Its verdicts rest on a denominator of one and its cost accounting predates the usage-accounting fix. It is void as a capability, quality, or cost signal and is not used as a prior, a sanity check, or an estimate. |

No case class has been silently omitted. Every class the corpus must carry is
listed below with the ground truth already identified for it.

## Population batches

The scored corpus is populated in evidence-preserving batches rather than in one
change. This batch delivers the strata layout, the per-stratum pilot envelope,
the grader calibration machinery with one calibrated case and one deliberately
uncalibrated control, the contamination audit over every corpus, the frozen
configuration, and the cost-ceiling proposal. The scored case population
follows, one stratum per batch, because each scored case needs individual
sourcing, minimization, and independent adjudication judgement, and fifteen of
those in one change would not be reviewable.

The candidate ground truth below was identified while sourcing this batch and is
recorded so the evidence is not lost. Each still requires the adjudication trail
to be re-verified at the source and the reproduction to be minimized fresh.

### Batch 2 — `s1-correctness-orchestrator`, 7 cases

| class                                                                   | candidate ground truth                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| ----------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| multi-file contract or untouched-consumer propagation failure           | `shaug/atelier` PR 335, comment 2867594627: a strictness flag was added to one call site while a sibling call site kept calling the same helper without it, so a closed dependency could still be treated as finalized through non-strict signals. Alternate: PR 350, comments 2867972061 and 2867993101 — the same coupling defect in two separate files, both recovery paths skipping external-state reconciliation.                                                                                                              |
| concurrency, retry, idempotency, transaction, or data-integrity failure | `shaug/atelier` PR 373, comment 2869270760: a stale-snapshot cleanup guard compared assignees only when the stale assignee was non-null, so a claim taken between collect and apply could be cleared. Alternate: PR 674, comment 2937093107 — one atomic note-plus-status write split into two, so a later failure leaves a fresh blocked reason on a changeset that is not blocked.                                                                                                                                                |
| validation gap where passing tests did not exercise the changed risk    | `shaug/agent-scripts` commit `f544aa0`: a probe for an optional executable checked only the return code, but a missing executable makes the call raise, so the intended skip never happened and the whole suite errored. It **survived an aggregate `clean` review verdict at head `b605051`** and was caught by CI. Complete provenance, this repository, no retention question. Alternate: `shaug/atelier` PR 318, comment 2867098097 — a tautological self-ancestor success when two branch references point at the same branch. |
| clean correctness control                                               | `shaug/atelier` PR 335: the hardening hunk in isolation, which the reviewer explicitly adjudicated as correct in the same thread that raised the sibling gap.                                                                                                                                                                                                                                                                                                                                                                       |
| clean correctness control                                               | `shaug/atelier` PR 417, comment 2870710594: a typed outcome replacing a boolean, implemented and accepted, with the reviewer's stated requirement met.                                                                                                                                                                                                                                                                                                                                                                              |
| adjudicated rejected or declined finding as negative control            | `shaug/atelier` PR 279, comment 2862037362: a reviewer-suggested fallback regression path was **declined on the merits** after the parser was intentionally narrowed to one canonical shape.                                                                                                                                                                                                                                                                                                                                        |
| adjudicated speculative or polish-only finding as negative control      | `shaug/atelier` PR 333, comment 2867594626 (a scope question plus "if exclusion is intentional, a brief rationale would help") or PR 356, comment 2868540467 ("possible edge case to validate ... or add a regression test to prove current behaviour is intentional"). Both are real observations that identify no defect.                                                                                                                                                                                                         |

At least three of these require reasoning across multiple files or an untouched
downstream surface: the PR 335 and PR 350 propagation cases and the PR 674
split-write case all do.

### Batch 3 — `s2-solution-simplicity-lens`, 4 cases

| class                                   | candidate ground truth                                                                                                                                                                                                        |
| --------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| whole-solution over-engineering         | `shaug/atelier` PR 160, comment 2848776499: a service tier given an injected abstraction purely to make calls it could make directly, with the reviewer asking why any abstraction is needed.                                 |
| whole-solution over-engineering         | `shaug/atelier` PR 410, comment 2870262209: three overlapping client concepts threading the same root and working directory through every method, to be converged on one already-bound client.                                |
| requirement-justified near-miss control | `shaug/atelier` PR 417, comment 2870710594: replacing a boolean with a typed outcome looks like extra machinery and is required, because the caller must distinguish an intentional fail-closed block from a genuine failure. |
| requirement-justified near-miss control | `shaug/atelier` PR 277, comments 2861848880 and 2861868165: retry plus fail-closed auto-close after a two-step create looks like defensive scaffolding and is required by deferred-by-default semantics.                      |

### Batch 4 — `s3-code-simplicity-lens`, 4 cases

| class                                  | candidate ground truth                                                                                                                                                                                                                                     |
| -------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| local code-complexity or reuse         | `shaug/agent-scripts` commit `9351619`: **the code-simplicity lens under evaluation itself** flagged the last inline copy of a policy predicate on PR 27; all three agreement sites now share one predicate. Adjudicated by this repository's own history. |
| local code-complexity or reuse         | `shaug/atelier` PR 410, comment 2870262209, read at the local level: the duplicated client concepts and the repeated argument threading at every call site.                                                                                                |
| behaviour-clarifying near-miss control | `shaug/atelier` PR 630, comment 2906875752: compatibility accessors retained at the true downstream edge where untouched callers still need them — apparent duplication that is justified by the migration boundary.                                       |
| non-material near-miss control         | `shaug/atelier` PR 443, comment 2880556753: per-item bullet blocks chosen over a table for formatter stability and diff-friendliness — apparent verbosity that is justified.                                                                               |

## Guarantees this record makes

- Every retained case is sourced from a real adjudicated review; none is
  invented.
- No case is labelled connector, and no connector figure is implied.
- No content from any private repository reached any artifact here.
- Every excluded candidate is listed above with its reason.
- Retention authority is recorded per case, and a case whose authority could not
  be established would be excluded before scoring rather than minimized into the
  corpus.
- Nothing here is adjudicated twice yet. Which of these candidates a second
  adjudication is expected to *disagree* with, and which source dispositions are
  too ambiguous to use without re-verification, is recorded in
  [ADJUDICATION-PLAN.md](ADJUDICATION-PLAN.md) rather than smoothed over here.
