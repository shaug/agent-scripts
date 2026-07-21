---
summary: Chronological history of repository and skill changes.
---

# Changelog

## 2026-07-21 — Carve-changesets operating contract

- fix: clarify published terminal evidence
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
- feat: AGENTS-aware test command discovery for prepare-changesets
  (1730fb654885f4ea1a5448e18bab1f558b5063ad)
- chore: initialize agent-scripts monorepo
  (420d1cdacb2855d3d9c494e57447954995043c42)
