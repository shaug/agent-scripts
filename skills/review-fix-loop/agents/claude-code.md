# Claude Code adapter

Optional discovery metadata for Claude Code and Claude Agent SDK runtimes. It
does not constrain the skill's portable contract.

- Display name: Review Fix Loop.
- Suggested prompt: "Use the review-fix-loop skill to validate this
  invocation/checkpoint/terminal-result document, or to run and record one
  complete review pass for the current candidate."
- Fresh read-only review context: invoke repository-owned `review-code-change`
  in a subagent (Agent tool) restricted to
  `Read, Grep, Glob, Bash, Agent, Task, Skill` — no `Edit`, `Write`,
  `NotebookEdit`, or other file-mutating or remote-write tool — giving it only
  the raw evidence packet `build_reviewer_briefing` and the packet builder
  produce, never the implementation transcript. Spawn a new subagent for every
  review pass; never reuse one across passes or reuse the mutating
  implementation context as the reviewer.
- Explicit in-agent override: only when the invocation's `review_execution.mode`
  is `in_agent_override` with a recorded `override_authorization`, run the same
  complete review in the current agent's own context instead of a subagent.
  There is no automatic fallback from `fresh_subagent` to in-agent when subagent
  spawning is unavailable; return `blocked/missing_capability` instead.
- Nested lens sharing: `review-code-change`'s own three lens invocations may run
  inside the one aggregate-review subagent this skill spawns; do not spawn an
  additional subagent per lens from this skill's side.
