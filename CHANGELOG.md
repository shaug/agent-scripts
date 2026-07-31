---
summary: Chronological history of repository and skill changes.
---

# Changelog

## 2026-07-31 — Added the review-fix-loop cross-cutting evaluation corpus, recorded the first review-fix-loop `update_pr` fix cycle

- feat(review-fix-loop): add the cross-cutting, result-blind evaluation corpus
  (issue #101, epic #95) covering convergence, repeated findings,
  invalid/incomplete reviews, declined findings, budget exhaustion, interruption
  and recovery, validation failure, reviewer mutation, and publication races
  across both `local_commit` and `update_pr`, plus the fresh-subagent default
  and the explicit in-agent override — twenty scenarios in
  `scripts/evals/corpus.py`, each driving the real engine against a real
  disposable Git repository (and, for `update_pr`, a real disposable bare
  remote) and graded in `scripts/evals/grader.py` against independently derived
  Git evidence (a real commit count, a real file's content at a real commit, a
  real remote ref, a real object's reachability) rather than the returned
  terminal-result document's own claims; `scripts/tests/test_evals.py`
  demonstrates the grader rejecting both a fabricated convergence claim and a
  fixture that cannot actually converge, and runs the whole corpus under
  `just test`; `just eval-review-fix-loop` is the standalone entry point
- fix(review-fix-loop): extract the test fixtures shared between
  `test_local_commit.py` and `test_update_pr.py` (the module loader, a bare
  local repository, the always-passing validation commands, the
  marker-file-driven fake reviewer, and the accepting decider/fixer) into a
  sibling `scripts/tests/helpers.py`, matching
  `carve-changesets/scripts/tests/helpers.py`'s established precedent, closing
  the one code-simplicity gap the first review-code-change pass on #100 found
  (`729135bb11d5bd8f0efa3a66d1c1ab1f978a3f6d`)

## 2026-07-30 — Delivered and evaluated the standalone review-fix-loop `update_pr` workflow, delivered and evaluated the standalone review-fix-loop `local_commit` workflow, implemented the review-fix-loop reviewer isolation and complete-review orchestration and local execution substrate (common-directory locking, isolated attempts, checkpoint persistence, and recovery), defined the review-fix-loop invocation, checkpoint, and terminal-result contracts, removed the unproven verification-sufficiency pass and its required-evidence field from review-correctness, and simplified the review-fix-loop design around local coordination and Git-native publication safety

- feat(review-fix-loop): add and evaluate the standalone `update_pr` workflow
  (`scripts/update_pr.py`'s `run_update_pr`), composing the exact same
  review/fix/converge engine `local_commit.py` already implements — every
  intermediate fix commit stays local — plus one expected-old, fast-forward-only
  Git publish immediately after convergence; resolves and cross-validates the
  fork/remote publication target without assuming "origin" ownership, validates
  `remote_iteration_grants`, and preserves the converged local commit with an
  actionable recovery path when the publication race is lost, the local
  candidate's history does not descend from the expected old head, or the remote
  is unavailable, with disposable-local-remote fixtures for a successful
  converge-then-publish run (with and without a fix cycle), a fork target, a
  competing remote update that cannot be overwritten, non-fast-forward history,
  a misconfigured target, a mismatched remote-iteration grant, an unreachable
  remote, and the remote-target lock actually being exercised end to end;
  generalizes `local_commit.py`'s internal loop into a policy-parameterized
  `_run_engine` both entry points share, with `run_local_commit`'s own behavior
  and its 21 existing tests unchanged
  (`95ccb81142357cc5cc55e78150abd5b39fa0e0b1`)
- feat(review-fix-loop): compose the contract, local-execution, and
  reviewer-orchestration leaves into the end-to-end standalone `local_commit`
  workflow (`scripts/local_commit.py`'s `run_local_commit`), enforcing the
  fix-cycle budget, committing selected fixes in isolated attempts, promoting
  only a converged candidate, and reporting explicit retained-commit and
  operator-action evidence for every non-converged stop, with end-to-end
  fixtures for immediate convergence, one and multiple fix cycles, budget
  exhaustion, validation failure (unavailable/untractable/tractable), operator
  input (declined finding and scope expansion), expanding/oscillating finding
  sets, repeated failed attempts, and interrupted-attempt recovery
  (`eaa1ded44eef0fa29d874d93196ffa7d3e0e1e79`)
- fix(review-fix-loop): remove three subsumed/redundant tests and cut
  `reviewer_orchestration.py`'s docstring/comment density from roughly one line
  of prose per line of code down to sibling-module levels, replacing restated
  rationale with single pointers to `references/reviewer-orchestration.md`,
  closing the two code-simplicity gaps the sixth review-code-change pass on #98
  found (`fd690248670c6acecfb2d335e70e347d4d4390de`)
- fix(review-fix-loop): correct an off-by-one changelog SHA attribution left by
  the previous fix cycle's own rebase cleanup — the duplicate-test entry and the
  `ignored`-comparison entry each carried the other's identity, closing the gap
  the fifth review-code-change pass on #98 found
  (`1945f82979bb3a0e6993c0326fdc9caad7391964`)
- fix(review-fix-loop): rebase onto the merged #97 local-execution substrate,
  document that a mutation attributable to a review pass must stop the
  invocation with `blocked/reviewer_integrity_failure` immediately rather than
  only relying on the `write_isolation`/`converged`-rejection backstop, and
  correct a changelog SHA left stale by that same rebase, closing the two gaps
  the fourth review-code-change pass on #98 found; the extracted
  `review_gate.evaluate_bound` reuse (cycle 1) is kept as the deliberate design
  after correctness confirmed it changes no accept/reject outcome for
  `implement-ticket`/`babysit-pr` (`2596f72cd4886b2d5ba385ee33a51353279fe995`)
- fix(review-fix-loop): remove a byte-identical duplicate test and trim
  history-narrating/triplicated docstring prose in `reviewer_orchestration.py`
  and `reviewer-orchestration.md` down to one owner per rationale, closing the
  two code-simplicity gaps the third review-code-change pass on #98 found
  (`7663b2cb36320287d9c2c9e820d4fb1745f4c5b2`)
- fix(review-fix-loop): stop comparing `ignored` worktree state for reviewer
  mutation (authorized validation commands legitimately create ignored build
  artifacts, which previously made `converged` unreachable), fail closed instead
  of silently passing when a before/after snapshot omits a required capture key,
  and collapse the packet-less `evaluate_review_result` path into the single
  packet-plus-result evaluator (`review-fix-loop`'s own
  checkpoint/terminal-result contract never persists one without the other, so
  no caller can legitimately use the weaker path), closing the two blocking gaps
  and the one strong-recommendation gap the second review-code-change pass on
  #98 found (`18991dd231ce5272b9a4b3335529418e6a717057`)
- fix(review-fix-loop): detect refs mutation (not only `head_sha`) between
  before/after reviewer snapshots, reconcile the packet/result evaluator with a
  contract-legal identity-omitting `blocked` result while still binding the
  packet itself to the current candidate, and extract the canonical
  `review_gate.evaluate_bound` (bundled into `implement-ticket`, `babysit-pr`,
  and now `review-fix-loop`) instead of a second candidate-binding
  implementation, closing the three gaps the first review-code-change pass on
  #98 found (`a519ae9f4e42551feba08146b465c5c526188e8b`)
- feat(review-fix-loop): implement reviewer isolation and complete-review
  orchestration — fixed lens resolution, default fresh-subagent review execution
  with an explicit in-agent override, before/after mutation detection that fails
  a cycle closed, checkpoint-shaped review-record construction, and
  deterministic finding normalization/selection (#98)
  (`086677ab59b219bccc009b9eb08dc67f3f613758`)
- feat(review-fix-loop): add `scripts/local_execution.py` implementing #97's
  local execution substrate — non-blocking common-Git-common-directory candidate
  locking (local-ref lock before the optional `update_pr` remote-target lock,
  released in reverse order), isolated attempt worktrees created from the exact
  canonical head, verified fast-forward-only canonical promotion that fails
  closed and preserves the candidate on a dirty or advanced canonical worktree,
  atomic schema-validated checkpoint persistence and resume reconciliation,
  preserved failed-attempt artifacts, cleanup that only ever removes the
  `review-fix-loop/attempt/` namespace it created, and recovery of an
  interrupted attempt against a checkpoint's own history — with deterministic
  tests against real temporary Git repositories covering contention,
  interruption, stale state, dirty worktrees, promotion races, and cleanup
  safety (`26b4cf47168dc8432f7d6e5e4597439af6391a51`)
- fix(review-fix-loop): reject `converged` when any `review_records` entry — not
  only the final-head-bound one — recorded a mutation attempt, closing the gap
  the tenth (final) review-code-change pass on #96 found
  (`0187dfc77444fbf410b5ed86a42a12e4d088e7b3`)
- fix(review-fix-loop): add a per-pass `reviewer_identity` field to
  `review_records` in both checkpoint and terminal-result, and reject a dirty
  `candidate.worktree` (`staged`/`unstaged`/`untracked`) in
  `validate_invocation`, closing the two gaps the ninth review-code-change pass
  on #96 found (`4daa2a67a38be3baa7741380eb689581ce31a1db`)
- docs: record the ninth review-fix-loop fix cycle in the changelog
  (`80690173571678bb14d14703451a8ab6d29b2cba`)
- fix(review-fix-loop): complete the terminal-result schema against the design's
  Terminal result contract field list (`worktree`, `resume_status`,
  `unresolved_or_deferred_findings`) and require `ahead_by`/`behind_by`
  alongside the head fields whenever a source is `bound`, closing the gaps the
  eighth review-code-change pass on #96 found
  (`adf2ef5062038836d750b01e19f1549373ce1aad`)
- docs: record the eighth review-fix-loop fix cycle in the changelog
  (`65a256a32b3087d064efb5e4a24725cfb1762467`)
- fix(review-fix-loop): complete the checkpoint schema against the design's
  durable-checkpoint field list (`preserved_failed_attempts`, `pull_request`)
  and extend the optional pull-request identity cross-check to both
  cross-document functions, closing the gap the seventh review-code-change pass
  on #96 found (`e7a955a321bafab1cd6f20b77758aa26670567bc`)
- docs: record the seventh review-fix-loop fix cycle in the changelog
  (`f6d1adccea4ee1e6571c911b10053aa4c27e00ba`)
- docs: record the sixth review-fix-loop fix cycle in the changelog
  (`31789481f000567a4b69cb0a1d5ba77b8d8c4dba`)
- fix(review-fix-loop): systematically close cross-document identity checks and
  commit provenance, enumerating the complete invariant field set
  (`invocation_id`, `repository`, `branch`, original fix-cycle budget,
  `publication.policy`, initial head, initial comparison base) that must agree
  across invocation, checkpoint, and terminal-result, closing the one remaining
  gap (`branch` in `validate_checkpoint_against_invocation`) plus the
  commit-provenance gap (`created_commits`/`fix_commit_sha` linkage) the sixth
  review-code-change pass on #96 found
  (`040ae824fae708efe46ca772f378c30378c9c695`)
- fix(review-fix-loop): add the missing repository/branch/publication.policy
  checkpoint cross-check, the design-enumerated `allowed_remediation_scope`,
  `worktree`, and `validation_outcomes` schema fields, and correct a
  misattributed changelog SHA, closing all three items the fifth
  review-code-change pass on #96 found
  (`a6178b8da086fab80bd52596babb0208304163a1`)
- docs: record the fifth review-fix-loop fix cycle in the changelog
  (`e71ea93ad98beec7b39cf6bb6c2a123743e820cf`)
- fix(review-fix-loop): add validate_checkpoint_against_invocation cross-check,
  symmetric to the existing `validate_terminal_against_checkpoint`, closing the
  gap the fourth review-code-change pass on #96 found: nothing inside a
  checkpoint document alone could prove `base_revision_history[0]` was the
  invocation's real original comparison base
  (`c625bb87b7aefb2371b992b20e4ce07b12b1c270`)
- docs: record the coordinator-authorized fourth fix cycle in the changelog
  (`2f3addbdceefb0a952fa1fb035475d0a9d31ebfb`)
- fix(review-fix-loop): require non-empty scoped validation and full base
  history match, closing two remaining gaps the third review-code-change pass on
  #96 found: an empty or scope-incomplete `validation_summary` could still claim
  `converged`, and the checkpoint/terminal-result cross-check compared only the
  final comparison base, never the initial one
  (`3d240c6be6a33bf131aa7ccee2544c59a36614c1`)
- docs: record the third review-fix-loop fix cycle in the changelog
  (`86c7df20d44d0c398c34bee5b8272dca4b239cf7`)
- docs: record the comparison_base cross-check fix in the changelog
  (`7d206acd32151405865c4ade4e9e7399ea739f57`)
- fix(review-fix-loop): check comparison_base in the checkpoint/terminal-result
  cross-check, closing a gap where `validate_terminal_against_checkpoint`
  silently omitted the base-identity leg CONTRACT.md already documented it as
  covering, found by the second review-code-change pass on #96
  (`e18f1469cf6d5f5cff1d99045dd041cdc5e77b71`)
- docs: record the converged-evidence fix in the changelog
  (`1c9fcdc5f4ae5765414f4b25839c07122c3bb151`)
- fix(review-fix-loop): reject converged results with non-clean embedded
  evidence, closing a gap where `validate_terminal_result` never inspected
  `review_records` or `validation_summary`, found by the initial
  review-code-change pass on #96 (`fc701b0bb29047af7b2ad24f25fb1db739718f89`)
- docs: record the review-fix-loop contracts changelog entry
  (`461db19fdd89e65afdf1c13fb870c5c427c00b67`)
- feat(review-fix-loop): define invocation, checkpoint, and terminal-result
  contracts, adding the skill-local schemas, a dependency-free validator, and 62
  unit tests covering valid, invalid, boundary, cross-document, and
  round-trip/determinism cases for both `local_commit` and `update_pr` (#96)
  (`0689cda71833751249ebc5e65b766d231cf2c093`)
- feat(review-suite)!: remove the verification-sufficiency pass and its
  mandatory `verification_sufficiency_evidence` field from `review-correctness`
  and the shared review-result contract, advancing `schema_version` `1.3 → 1.4`;
  the traversal (consumer/impact) pass and `consumer_impact_evidence` are
  unchanged, per #57's ablation matrix and #89's harder-case validation finding
  no demonstrated value for the removed pass plus a confirmed, twice-reproduced
  false-positive regression when it ran without the traversal pass (#93)
  (`b91e12b063ea6d7ed49f152ee359f1f0eb326363`)
- docs: simplify the review-fix-loop design
  (`2e7a8cd93af9f2c8cec36d6c393694f7849adedb`)

## 2026-07-29 — Sourced two harder discriminating cases for the traversal and verification-sufficiency passes, designed the review-fix-loop skill, migrated implement-ticket and babysit-pr to consume the final review-result contract, rechecked the s2/s3 strata under grader 1.1 for the same surface-in-prose defect, added connector-outcome curation and promotion tooling, added a skill-root override for mechanism ablation runs, ran the preregistered v2 ablation and integration closeout, and confirmed the session-continuation-summary verification-only regression with an independent rerun

- docs(review-suite): validate the two new discriminating cases with-pass and
  without-pass, fixing a construction defect found in the traversal case along
  the way, and report the traversal pass discriminates while the
  verification-sufficiency pass still does not (#89)
  (`5e9b3de63335e23d80781a85de49c43c231d9d07`)
- feat(review-suite): source two harder discriminating
  `s1-correctness-orchestrator` cases for the traversal and
  verification-sufficiency passes and preregister their validation ceiling (#89)
  (`bfec2910a81422df365ddc3ba4c70672a9ebe269`)
- docs: design the review-fix-loop skill
  (`06538e5c097ff8e6ef15b12d5fbf61b3d959abf7`)
- docs(review-suite): add a confirming rerun of the session-continuation-summary
  verification-only regression (#57 follow-up)
  (`cd8efa444018d036a5749a1955e1f34ebe06b51f`)
- docs(review-suite): run the preregistered v2 s1 ablation matrix and
  integration closeout (#57) (`b4e061f7847b3fc911a05fe4c8e50218f4f957b7`)
- docs: add the CHANGELOG entry for the skill-root ablation override
  (`e2c56f68fe56094a6c92fd4a220539f47d6f9f98`)
- feat(review-suite): add a skill-root override for mechanism ablation runs
  (`8e959ffbff00152341a961350d3fbdd12d01b5df`)
- refactor(review-suite): simplify duplicate-chain resolution and unify its
  membership check (`16fc32a90eaea16ac98ff2a34bbabafed7a4681f`)
- fix(review-suite): resolve a duplicate's disposition through its duplicate_of
  chain (`07baa7dfdf06bfa19428bb9ba80a8317f8ff78d0`)
- feat(review-suite): add connector-outcome curation and promotion tooling,
  including the mechanical disclosure guardrail
  (`d7357ee17a616ad374e6bb033a4c9adef6e5cc0a`)
- docs: fix stale CHANGELOG SHAs left by the main rebase
  (`51cc734fc56a97dfa7a754fd046206dd62b375ba`)
- docs: backfill the CHANGELOG entry for the review_gate.py canonicalization fix
  (`e2310bff8cc9c3a38b690a57844436d5357fa471`)
- fix: canonicalize review_gate.py through the existing sync-contracts mechanism
  (`161424571551676c5e8009c2de2c2a102ab7c305`)
- feat: migrate implement-ticket and babysit-pr to the schema 1.3 review-result
  contract (`016ffaa826dddf72a822e555796827a396a4041f`)
- docs(review-suite): recheck s2/s3 strata under grader 1.1 for the same
  surface-in-prose defect (`7cf4a3b3fe3dd38f3d1a9da2e6ab82058a77f064`)

## 2026-07-28 — Added correctness traversal and verification-sufficiency passes, consumer/impact-traversal evidence, and required passing validation and current-head lens evidence for a clean review verdict

- feat: add correctness traversal and verification-sufficiency passes
  (`85ccf13b45bad8f162d81963a3ac910ea0b49590`)
- feat: add consumer/impact-traversal evidence to the shared review contract
  (`8e4fdbdaad8f70751d45f8c2ca87e88288f8ba5b`)
- feat: require passing validation and current-head lens evidence for a clean
  review verdict (`b1e51979628652e4ef60adad44089bf54f4551e7`)

## 2026-07-27 — Made database comparison output ephemeral, enforced untrusted-content boundaries, bound epic delegation, hardened command execution, populated the solution-simplicity and code-simplicity strata, enforced acceptance-gated closeout, populated the correctness stratum, recovered carved suffixes, folded owner adjudications, and ran the frozen v1 baseline

- fix: keep database comparison output ephemeral by default
  (`2f13a2d6c27fda2ced66558460a72c11c4d43c26`)
- feat: enforce untrusted content boundaries
  (`ff3f4b9cca9b062a7113b95ab08bd1d36331a27c`)
- docs: record the small-sample caveat the frozen protocol's step 6 requires
  (`e720e656cd3729a857aa4bcb6f6592fae1facc57`)
- fix: enforce owner_disposition exactly when owner_confirmed
  (`e0027dd24be391706a8269d84a9766abb95ca95b`)
- feat: run the frozen v1 baseline and record real scored results
  (`28fb2e57474fbf776beff50f3fc3f0f5cedfcd6a`)
- docs: freeze the v1 configuration for scoring, before any scored output
  (`07066d22a64bb218938a60d905e52745ca717c1a`)
- feat: fold owner adjudications into the corpus and mark all strata scored
  (`bf99b86b3844bea2bd248bd0828283158bee85dd`)
- fix: score a partial or ambiguous match as referred, not a silent
  reviewer-miss (`732e975391d0ea1b92d6d1ec312bdf4fb44d5948`)
- feat: bind epic delegation to trusted ticket skill
  (`569b11ec60977c19c66092690ffdada0dbac1eb4`)
- fix: execute carve commands from explicit argv
  (`7da1a75ad585bddec6be1cc4743e77a1744c4e98`)
- fix: correct a stale reference, a stale validation entry, and an inverted case
  (`c7a80c0e05ea76c0a7626c02dbf0b1605da37739`)
- fix: make the last two before-state and sanitization defects actually resolved
  (`41de65daadc5d53bfbb299cb4ecd6d040ac47ab9`)
- fix: sanitize the repository-history case and correct the changelog order
  (`3d9fe4925c8908a311453c87ae740bfcf4de20bd`)
- fix: reconcile records after folding s2 and s3 into one delivery
  (`5070cf1bbea438e74149dfe0cf9b171a6f7cdb92`)
- docs: record the code-simplicity delivery and close out corpus population
  (`875091c32301eafd807d2d5a3e2b402e7ffaca53`)
- feat: populate the code-simplicity stratum with four adjudicated cases
  (`f3c064a7bbaf3f89f7a6a5495846b254a54e9a0b`)
- fix: sweep sanitization across every reviewer-visible field, not only the diff
  (`ab3921a904ec7835bc4d03ed40b7c8a28d12d2c1`)
- fix: make every s2 packet internally consistent after the sanitization rename
  (`1ec231bb17cd0c1db82258756aa7a78e8e7f63ab`)
- fix: sanitize the solution-simplicity cases against source-vocabulary leakage
  (`2b56c022c91a925b574a5748112e63bdcbbbf8f2`)
- docs: record the solution-simplicity delivery and settle the grading method
  (`da8f53b06072ba0380d01ce06fc4f4a324a6219e`)
- feat: populate the solution-simplicity stratum with four adjudicated cases
  (`3105b8e84da78c691f4f93883f39887ff9ae784f`)
- feat: require acceptance evidence for workflow closeout
  (`a3597c25ee2d76135d1f0c8642a620e673fc8e57`)
- fix: make every packet diff a valid patch, and gate the adjudication record
  (`06a5679643a0a5bcb1944c8bff4bd4986f4f77e1`)
- fix: stop a grader formulation being quotable from its own packet
  (`fa772a7d770bd3d07f3fdd9bdc45a0c237b1d14e`)
- docs: record the batch-2 delivery, the clean-control standard, and its limits
  (`e83da75687f06ec9ff6a82df5ac4845c6e6fb23f`)
- feat: adjudicate the correctness cases by executable oracle
  (`6dcfeabc7acd325d1dcaae4ed341fa780df94bc9`)
- feat: populate the correctness stratum with seven adjudicated cases
  (`43deec617ee06e22e1a937234eea2a4d99b5d836`)
- feat: recover corrected carved suffixes
  (`ba12e0744a938fc71af16eeeaa0eea98e7c2c63e`)

## 2026-07-26 — Added the replay evaluator, then froze the v1 baseline configuration

- fix: reconcile every recorded figure with its retained artifact
  (`d013507956aa0ab328140a72c87fdbb151f2b1ec`)
- fix: attribute the pilot to a reproducible commit and correct the records
  (`3a8388d42e355e4bc9731b98b6dcd42ffd13ff2f`)
- feat: report the stratum a run evaluated
  (`2ae0d23c18f247f49d3cc5e76f26d1cf9610c83e`)
- fix: make the frozen baseline record auditable, and measure the envelope
  (`f7787dcba681db1de079f57ce1f2f2941e0923b2`)
- feat: add baseline strata, grader calibration, and the frozen v1 record
  (`16b77e447dbcc844edd8f3fb58728d96826e177c`)
- fix: skip the recipe-execution tests when `just` is absent
  (`f544aa0c19d97dd4f1aabd7dfab3df08b2ee6a6b`)
- feat: record the evaluated skill closure with every run
  (`b605051a7385dd310b0eff9dbf14c10dda87c633`)
- docs: record the measured smoke evaluation and its variance
  (`87ec303d949301c908c3a29cb220bed22d44c775`)
- fix: evaluate the target skill's whole declared closure
  (`62a9ed8fab166c7d380724e426449f0585714b07`)
- docs: pin the recorded smoke evaluation to its run
  (`f00ce2db80ed3a7bed6afb4962cf0bb5a68390fe`)
- fix: complete the evaluated skill text and the audit ordering
  (`67efd94339034674de6ca250f2b03e4a0213fc8b`)
- fix: close the replay evaluator's review-gate gaps
  (`6ef8e25ce2e0183ef270111549660461493da5f4`)
- fix: stop misattributing review failures in the replay evaluator
  (`e46184d6e856199fe0792d43e7f6e0c5a86e131f`)
- feat: add the result-blind review replay evaluator
  (`8f0e9d646ec4e959d7adc7448f5fc7a82f4334d8`)

## 2026-07-25 — Added coordinator-neutral delegated ticket execution

- fix: pin CI to the established Ruff rule set so dependency drift cannot
  redefine the repository-wide lint gate
  (`901dc3596207a88b6c8edcf548b5be3151ca7ab2`)
- feat: add a versioned delegated-execution contract for `implement-ticket`
  (`b53efa674e929c181bdaac63ff0306cb756386db`)

## 2026-07-21 — Completed carve-changesets and integrated ticket publication

- feat: package the workflow suite as a plugin
  (`b7ec1b593b9d211cd91101d94d0406c355b2ecd7`)
- fix: fail closed on invalid carved handoffs
  (`dc4f5c1f3e33c25ad6258f7365506bd33255ed82`)
- feat: integrate carved ticket publication
  (`54c67f7cd7ace3269eee4fe628f974b090a4d699`)
- refactor: derive the eval action vocabulary from expectations
  (`e30b5f1021538d673eb931b2978287cfd21ae4ae`)
- fix: require the two-part source freshness override
  (`eb8612300d75d1483995677d75f54fe1a32b60d7`)
- test: complete the carve-changesets verification suite
  (`f669d322985c435daf9b0c7296889d8a3bdd270c`)
- feat: package the carve-changesets skill
  (`a8e19110380e048e0aaf85e820c114fe2a07cc7f`)
- docs: define carve-changesets suite handoffs
  (`2df5136e2a7226666bc136e30905c2442a579c78`)
- feat: add stateless changeset merge and propagation
  (`925affa807c203824127a0fe5e0fb084f14f378d`)
- refactor: make strict apply use one proof
  (`c8ca89566562d7d154bfe1a1711140323e3ba9f8`)
- fix: bind GitHub operations to the selected remote
  (`cfdddb0aeb792fabfb4021173e25738b45329083`)
- fix: close consolidated carve CLI review gaps
  (`d4b071ff46b7b4f2bf8b256f9071d76325e4d146`)
- feat: add the consolidated carve-changesets CLI
  (`0d942c50cff2d9472b664e74d423661c9f1693cb`)
- fix: bind changeset validation to current live refs
  (`721a1ea07c0e8d8af1265bbf70326afaf286aa4a`)
- feat: validate changeset chains from live git
  (`df24771983819b05110670a8d03d43e003d23d28`)
- feat: add self-describing changeset identity
  (`e88bf87e9cb1a4e04bdf8b051ce8ca0f0dcb96e6`)
- fix: clarify published terminal evidence
  (`edeb2f5f5f7b4cfa4e73e8289d34157b192f92ab`)
- docs: define the carve-changesets operating contract
  (`77865c25190e7205142318229f17c1d3f18e1fef`)

## 2026-07-20 — Portability, watcher resilience, and Claude adaptation

- refactor: route the clear predicate through `has_failed_pr_checks` — the
  code-simplicity lens on PR #27 flagged the last inline copy of the
  failed-PR-check policy inside `is_github_candidate_clear`; all three agreement
  sites now structurally share one predicate
  (`93516194388116f4841fc191a8c78c191d0da5b1`)
- fix: share one failed-PR-check predicate across the watcher — the initial
  `review-code-change` pass on PR #27 found the retry gate refusing retries that
  `recommend_actions` recommends for failed-runs-only states; extract
  `has_failed_pr_checks` and use it in both sites, and match repository case
  insensitively in state-target validation
  (`625dae641a9652368f03b6be825f48d9addab056`)
- fix: close the final low-severity review findings — mirror the clear predicate
  in `has_failed_pr_checks` so a PR-check-backed failed run never reads as
  `idle`, case-normalize repositories before deriving state files and locks,
  match fragment run links, reject `--repo` without an explicit `--pr`, make
  boolean schema constants reject numeric one, and document `--poll-seconds` and
  `--max-flaky-retries` (`f79266a390e970cd25cf8af1bed6b9bd9cf154ee`)
- fix: align retry gating and delegation tooling with review round four — accept
  cancelled-only check failures in the retry gate so a recommended retry is
  never refused, grant the review orchestrator the subagent and skill tools its
  Claude adapter requires, reject `--once` with `--retry-failed-now`, match
  query-string run links, add a repo digest to default state filenames, keep
  `diagnose_ci_failure` visible after retry exhaustion, and document zero-check
  `--stop-when-clear` pairing (`ddb29d0ce0409554cec61ed54b2c6e7ed6d84c6a`)
- fix: close adversarial-review findings — resolve bundled-validator schemas in
  both layouts and execute every bundled copy in place, scope failed workflow
  runs to the PR's own checks so push/schedule failures cannot wedge the
  watcher, emit `resolve_draft_state`/`resolve_merge_conflict` instead of
  `idle`, complete `forbidden_actions` on all forward expectations with a
  vocabulary-spam canary, stop backfilling `target_skill` in the Claude
  executor, reject `--once --watch`, handle `OSError` cleanly, import bundled
  validators in review-skill tests, and document eval flag pre-classification,
  the gh 2.37 floor, and state-file durability
  (`48b6f614d15d50dae4ba5c63d7b3e3471647dd1a`)
- fix: close independent-review findings — count cancelled checks and failed
  runs/jobs in the watcher's clear predicate, run review-suite tests in CI,
  bundle the dependency-free packet validator into each review skill, make
  `--stop-when-clear` imply `ready_to_merge` and test every documented CLI
  invocation, fail closed on empty `gh pr checks` payloads, surface ghost-author
  comments, move watcher state into a per-user 0700 directory, add
  forbidden-action forward grading, unify `observed_sequence` tokens, and rename
  `agents/claude.md` to `agents/claude-code.md` to avoid the case-insensitive
  CLAUDE.md memory-file collision (`b5bf81b81a6dd521edcdfc561988ca621a566d39`)
- fix: make skills self-contained and adapt the suite to Claude runtimes —
  bundle the review-suite contract into each review skill with a
  `just sync-contracts` target and drift test, use skill-root-relative watcher
  paths, survive transient watcher failures with bounded backoff, add
  `--max-polls`/`--stop-when-clear` bounded watch modes and a
  `confirm_feedback_disposition` action, move eval answer keys out of
  reviewer-visible input directories, add a Claude headless forward-eval
  executor, add `agents/claude.md` adapters, `allowed-tools` on review skills,
  and trigger-oriented skill descriptions, and trim contract tests to
  load-bearing invariants (`474756bea51237376b81ad7d593eef2d8de273f1`)

## 2026-07-20 — Composed ticket and PR execution

- fix: execute result-blind forward evaluations in fresh contexts
  (`f452db4cf47e56b3f8fea560977a3ce98ca26caa`)
- feat: delegate the `implement-ticket` PR lifecycle to `babysit-pr`
  (`d5838d49587ab34a00973441a870cd525cfcd773`)

## 2026-07-20 — Repository-owned PR babysitting

- fix: bind each watcher lock to an immutable repository and pull request target
  (`3666b3d5beb9182b3dab221d2489a7acf23323b7`)
- fix: validate the locked PR state path before any snapshot read or write
  (`322a83c6b31d5668e6648df8f0fabe3732c3e74f`)
- fix: serialize every watcher state mutation through one repository/PR lock
  (`8c64b05daa9cde6832fb128c7c6786896fb57108`)
- fix: serialize retry mutation and durably reserve each per-head retry cycle
  (`4ecdd65767164e7f0f112d4049a856c6e8ea53ed`)
- fix: scope CI retries to explicitly diagnosed current-PR runs
  (`7f559ead6a4373bc2f0bd441b5af853d66260753`)
- fix: fail closed on partial review data and remove inert polling state
  (`b14dca750337eacd0f34f5b705afbe81591174b7`)
- fix: hide pending inline review threads until publication
  (`76ed0f6090f23e7a9c0aae14897ae48948922a37`)
- feat: add the portable `babysit-pr` skill with candidate-bound CI, feedback,
  review, and merge gates (`b57bd0f3625d7aba9fe4ba32e2abb3f2c7b0df91`)

## 2026-07-20 — Portable ticket and epic execution

- feat: make ticket and epic execution runtime agnostic
- feat: compose epic execution through implement-ticket
  (7c4e500a35d48b5dba311094b4d34d8ca97f25a1)

## 2026-07-19 — Epic workflow and review contract cleanup

- feat: add standalone ticket implementation skill
  (7113afd5ab04d0200c2bfa6b5008d9fcd2b2f7f6)
- feat: integrate repository-owned review into epic execution
  (28c3945b3db8f84a812cd2e498d54a6912bcd934)
- feat: compose repository-owned code review
  (556fea80b6970b97c31e819693f43c251b7b3796)
- feat: add local code simplicity review
  (d6ed890f6924a2ae7ae4b04fa95072ee853c9b97)
- feat: add whole-solution simplicity review
  (8459402e95888047587cf423454f9f8ac42f6881)
- feat: add goal-first correctness review
  (33feab3570363f8bf0d24ed4295495dc05fa3abf)
- feat: define shared code review contracts
  (5600132585c502b21434a938e0319ba58521ee67)
- feat: add epic sequence implementation skill
  (06bd81f4293a24e12cde1f0e466596b41095e8f4)
- revert: remove modular code review contract
  (b889fe4dc313dc50320dcb20f98980b993062c9a)

## 2026-02-24 — Modular code review contract specification

- feat: specify modular atelier-agnostic code-review skill contract
  (062a1a328e6a1b2e0835d16be742fc2c36dbd9dd)

## 2026-01-27 — Incremental changesets and workflow reliability fixes

- docs: clarify cognitive load guardrails and mechanical exception
  (a2a926a4bedf1abc560051551c3a5cefded7a6ec)
- fix: resolve repo default merge method for non-interactive merges
  (148c88bc437d6bbdc9a3fe232e37199b9e3b7878)
- fix: default merge-propagate to repo merge method
  (1322dd79d2201c16b03e8459582898d35edd990f)
- feat: add cherry-pick propagation strategy
  (72a6fc893a3b943d6c0d4172a0d89b0e5f782928)
- docs: require pushing changeset branches before PR creation
  (47a92e5e418f75dcf773c54ab8c8e7bb7e29a30f)
- fix: require recordkeeping directories to be ignored in preflight
  (efe0a3c676bd168a2b3a8b93c20adcd7541cf40b)
- fix: avoid staging plan artifacts and ignore AGENTS metadata
  (a7b9c29aa312f9432368fbd66994fe69389ba056)
- feat: enforce source branch freshness before preflight
  (76602f9233d8faff52437a58fb29a6a13f1f0b14)
- feat: all-hunks selectors and strict apply checks for hunk mode
  (e743c706bd5d7b1429f4967b794a1b5cc4ce54c5)
- feat: rename-aware hunk selection and rename-first guidance
  (998000f86f607740b242d042fc7d77793753725a)
- feat: hunk-based changesets with strict validation and patch support
  (7fb3d61890767a4085132a69dd2020ea5e1b8810)
- feat: incremental changesets with squash-check and mdformat 1.0 tooling
  (797e56fcb2bc41fd8e84491866c86a2af1dd31f9)
- fix: CI agentskills install and changelog workflow rules
  (460a81780211264cdc568e42e3f8e4b73ca2bcea)
- feat: add AGENTS-aware test command discovery
  (1730fb654885f4ea1a5448e18bab1f558b5063ad)
- chore: initialize agent-scripts monorepo
  (420d1cdacb2855d3d9c494e57447954995043c42)
