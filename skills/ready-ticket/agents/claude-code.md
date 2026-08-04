# Claude Code adapter

Optional discovery metadata for Claude Code and Claude Agent SDK runtimes. It
does not constrain the skill's portable contract.

- Display name: Ready Ticket.
- Suggested prompt: "Use the ready-ticket skill to turn this request into an
  implementation-ready ticket body."
- Run mode: a session with a responsive user is an interactive run; a scheduled,
  headless, or delegated run with no reachable requester is an autonomous run.
  The distinction decides whether questions are asked and whether load-bearing
  is offered or only recorded.
- Tracker reads: use `gh` GraphQL for native GitHub parent, sub-issue, and
  blocker relationships, or the Linear MCP connector when Linear owns the
  ticket. Do not derive relationships from Markdown task lists.
- Tracker writes: pass the authored body through a file rather than an inline
  shell argument so Markdown and backticks survive unaltered.
