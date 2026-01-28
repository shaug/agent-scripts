---
summary: Chronological history of repository and skill changes.
---

# Changelog

## 2026-01-27 — Incremental changesets and workflow reliability fixes

- fix: resolve repo default merge method for non-interactive merges
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
