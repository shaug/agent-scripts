# Claude Code adapter

Optional discovery metadata for Claude Code and Claude Agent SDK runtimes. It
does not constrain the skill's portable contract.

- Display name: Implement Epic.
- Suggested prompt: "Use the implement-epic skill to implement this epic through
  its live dependency graph and the repository-owned ticket workflow."
- Delegated children: run each `implement-ticket` execution either inline in the
  primary context or in one exclusively owned subagent per child; never two
  mutating contexts on one candidate. Parallel children require the explicit
  authorization and non-overlap proof from the skill contract.
- Graph reads: use `gh` GraphQL (or the Linear MCP connector when Linear owns
  the graph) for native parent/sub-issue/blocker relationships; do not derive
  the graph from Markdown task lists.
- Long waits: child CI and review waiting belongs to `implement-ticket` and
  `babysit-pr`; keep this orchestrating task alive until the requested scope
  reaches its completion policy.
