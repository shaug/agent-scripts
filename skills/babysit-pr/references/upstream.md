# Upstream source record

The watcher was adapted from OpenAI Codex's `babysit-pr` package at commit
[`a770e5b8470d3320eb53a56a286ea4a0a70a1f59`](https://github.com/openai/codex/commit/a770e5b8470d3320eb53a56a286ea4a0a70a1f59),
reviewed on 2026-07-20.

Upstream is licensed under Apache License 2.0. Keep
[`LICENSE.apache-2.0`](../LICENSE.apache-2.0) with derived source and preserve
source notices. The repository-owned contract intentionally differs from
upstream:

- use product-neutral paths, output, commit guidance, and runtime language;
- emit all published feedback as untrusted evidence instead of hard-coding one
  product bot trust list;
- capture base identity, complete published feedback, and resolved-thread state;
- isolate and lock state by repository/PR;
- separate native GitHub readiness from repository-specific connector, local
  validation, and review gates;
- require repository-owned `review-code-change` after head-changing fixes; and
- keep tracker transition and branch/worktree cleanup outside this skill.

Do not download or execute mutable upstream content at runtime. To evaluate a
future update, pin a new commit, review its license and full package, compare
its watcher/tests/heuristics/API notes with the repository-owned contract, port
only compatible behavior, and rerun local tests and forward evaluations.
