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

| field                  | value                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| ---------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| strata                 | `pilot-orchestrator` only, so the case shared with the lens strata stays byte-identical across all three                                                                                                                                                                                                                                                                                                                                                                     |
| source                 | `shaug/atelier` pull request 278, review comment 2861937742, authored by the repository owner. Public.                                                                                                                                                                                                                                                                                                                                                                       |
| adjudication           | The reviewer required the change; the follow-up reply (comment 2861947492) names the implementing commit and the regression coverage added for the exact migration shape. Accepted, not deferred.                                                                                                                                                                                                                                                                            |
| failure shape retained | A normalization step drops one legacy flag and returns early for an inactive status, leaving a second legacy flag that contradicts the canonical status, with a live consumer that admits work on that flag alone. The added tests all start from records that never carried the second flag, so the one shape the change exists to fix is untested.                                                                                                                         |
| origin                 | `minimized_reproduction`                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| sanitization           | Rewritten against a fictional record registry. No source identifier, path, symbol, prose, or diff copied. No business logic, domain identifier, customer context, credential, or hidden reasoning.                                                                                                                                                                                                                                                                           |
| retention authority    | Public repository, owner-authored review, no third-party or customer material.                                                                                                                                                                                                                                                                                                                                                                                               |
| why it exists          | Two purposes. Its packet is materially larger than the other pilot case, which separates the fixed cost of a stratum's skill closure from the variable cost of the packet — the measurement behind the cost-ceiling proposal. And it is **deliberately left uncalibrated** (`calibrated: false`) as the control for what an uncalibrated expectation reports: recall 0.0 over five attempts with ten adjudication referrals, while the reviewer gated the change every time. |

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

### Batch 2 — `s1-correctness-orchestrator`, 7 cases — **DELIVERED**

Populated but not scored. Every case is minimized, every case names its source
disposition, and every case is adjudicated a second time by executable oracle.

| case                                | class                           | source disposition                                                                                            | expected |
| ----------------------------------- | ------------------------------- | ------------------------------------------------------------------------------------------------------------- | -------- |
| `dependency-strictness-propagation` | multi-file / untouched consumer | atelier PR 335, comment 2867594627 — **accepted**, commit `5cb0333`                                           | gating   |
| `stale-claim-release-guard`         | concurrency / data integrity    | atelier PR 373, comment 2869270760 — **accepted**, with a regression test for the collect/apply window        | gating   |
| `optional-tool-probe`               | validation gap                  | this repository's `f544aa0` — survived an aggregate `clean` verdict, **caught by CI**                         | gating   |
| `session-continuation-summary`      | clean control                   | atelier PR 486, comment 2881737041 — **declined on the merits**; flag kept, only operator wording changed     | clean    |
| `dependency-hint-parser-coverage`   | clean control                   | atelier PR 279, comment 2862025661 — **declined on the merits** in reply 2862037362                           | clean    |
| `post-bootstrap-module-load`        | negative control, polish-only   | atelier PR 710, comment 2961766206 — **comment added, no behaviour changed**                                  | clean    |
| `process-isolation-assertion`       | negative control, deferred      | this repository's #50 — raised by a real review, **dispositioned `defer`**, item 4 of PR #61's preserved list | clean    |

Five carry multi-file diffs; three are only decidable by reading a consumer the
diff does not touch, which satisfies #58's multi-file minimum.

Sanitization: all five atelier-sourced cases are `minimized_reproduction`,
rewritten from scratch against fictional subjects, retaining only the failure
shape. The two sourced from this repository are `repository_history`, also
rewritten against fictional subjects so neither can be mistaken for this suite's
own code. No source identifier, path, symbol, prose, or diff was copied into any
case. Retention authority is public in every case.

#### The clean-control standard, and what it cost

The owner settled the standard after batch 1: a clean control must be an
**adjudicated-rejected finding** — a case where a finding was actually raised
and dispositioned as not material. The recorded rejection is the evidence, and a
reviewer that re-raises it is charged a false alarm. "No review comments" is
explicitly not evidence of cleanliness, because absence of comment is ambiguous
between reviewed-and-clean and nobody-looked, and a control resting on it would
charge a false alarm against a reviewer that correctly found a real unnoticed
defect.

Encoding: each clean case records its rejected concern as an accepted
non-finding carrying the formulations a reviewer would actually use. That
tolerates a non-gating mention while a gating one is still charged as a false
alarm at the verdict level. The rejected concern is deliberately **not** a root
cause — raising it is the error being measured, not the answer.

**Four candidates were dropped for failing this standard.** Both of the
clean-control candidates batch 1 had identified, and two of the negative-control
candidates:

| dropped candidate                  | why it fails the standard                                                                                                                                                             |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| atelier PR 335, the hardening hunk | Its cleanliness rested on the reviewer praising the hunk, not on any rejected finding, and it was cropped from a pull request that did carry a finding. Not an adjudicated rejection. |
| atelier PR 417, comment 2870710594 | An accepted **fix**, not a rejected finding. Acceptance says the concern was material, which is the opposite of what a clean control needs.                                           |
| atelier PR 333, comment 2867594626 | Verified on re-check: the concern was **accepted** ("Included now"), with blocked epics added and coverage extended. Not immaterial.                                                  |
| atelier PR 356, comment 2868540467 | Verified on re-check: also **accepted** ("good catch"), with the recompute added and a regression test. Not immaterial.                                                               |

One further candidate was assessed and dropped: atelier PR 160, comment
2849318292, where a one-liner suggestion was initially declined on readability
grounds. Following the thread, the reviewer pushed back and the underlying
preference was ultimately **implemented** via a shared helper. The disposition
is therefore acceptance in another form, not rejection, so it fails the standard
too.

The correction is worth recording plainly: batch 1's adjudication plan named PR
333 and PR 356 as having *ambiguous* dispositions needing verification, and PR
335 as lacking a verified acceptance. Verification resolved all three — PR 333
and PR 356 were accepted and are unusable as controls; PR 335 **was** accepted,
which makes it a valid escape rather than a valid control.

### Batch 3 — `s2-solution-simplicity-lens`, 4 cases — **DELIVERED**

Populated but not scored, and unlike the correctness stratum, this one has no
executable oracle available for its subject at all: "over-engineered" and
"requirement-justified" are design judgements, not properties a runnable check
can decide. Every case's second adjudication is `owner_required`, each with a
recommended disposition and its own stated residual risk for the owner to weigh.

| case                             | class                                   | source disposition                                                                                     | expected | recommended adjudication |
| -------------------------------- | --------------------------------------- | ------------------------------------------------------------------------------------------------------ | -------- | ------------------------ |
| `setup-service-path-gateway`     | whole-solution over-engineering         | atelier PR 160, comment 2848776499 — **accepted** in `fcbf469`, gateway indirection removed entirely   | gating   | MATERIAL                 |
| `registry-client-layering`       | whole-solution over-engineering         | atelier PR 410, comment 2870262209 — **accepted** in `f631cb0`, three client concepts converged to one | gating   | MATERIAL                 |
| `reconciliation-outcome-type`    | requirement-justified near-miss control | atelier PR 417, comment 2870710594 — accepted, the comment records its own implementation              | clean    | CLEAN / NOT MATERIAL     |
| `record-status-transition-guard` | requirement-justified near-miss control | atelier PR 277, comment 2861848880 — **accepted** in reply 2861868165, naming commit `79703c5`         | clean    | CLEAN / NOT MATERIAL     |

Sanitization: all four are `minimized_reproduction`, rewritten from scratch
against fictional subjects (a setup service, a registry client, a registry
runtime, a planner tool), retaining only the failure shape. All sources are
public, all retention authority is public-repository owner-authored review.

**A first draft of all four cases failed this claim, and review caught it before
merge.** The first draft carried the source's own CLI name and ticket-subsystem
noun verbatim, a real function name, real enum member strings, and expectation
formulations built from the real reviewer's own sentences rather than
independent paraphrases — none of it business logic or a domain identifier, but
all of it the source's own vocabulary rather than a rewrite. All four were
corrected before this record was published; see limitation 21 for what the
defect was and why it matters even though every source is public. The
already-merged `s1-correctness-orchestrator` cases were checked against the same
class of leak and found clean of it.

Two cases reuse source PRs batch 1 or batch 2 also drew from, in a different
framing each time: PR 417 (comment 2870710594) was assessed for `s1` as a
**correctness** clean control and dropped there because acceptance of a *fix*
contradicts what a clean-control standard needs; here it is sourced as a
**solution-simplicity** near-miss control instead, where the same accepted
change is evidence for a different, legitimate question — is the added machinery
requirement-justified — and the standard for that question is not the
adjudicated-rejected-finding standard `s1` uses. Recorded so the reuse is a
decision, not an oversight.

One case id needed renaming during audit: the natural name
`deferred-status-fail-closed-retry` triggered the outcome-revealing-token check
twice (`defer`, `fail`); a second attempt, `changeset-status-transition-guard`,
still matched on `changes` as a substring of `changeset`. It shipped as
`record-status-transition-guard`.

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
- Every case in `s1-correctness-orchestrator` is adjudicated twice: the recorded
  source disposition, and an executable oracle that runs the stated requirement.
  No case in that stratum needs the owner.
- Every case in `s2-solution-simplicity-lens` has no executable oracle and needs
  the owner directly, with a concrete recommended disposition and its residual
  risk recorded per case rather than left as a bare list.
- No case in any populated scored stratum has been run through a runtime. They
  are unobserved, which is what keeps a later baseline result-blind.
