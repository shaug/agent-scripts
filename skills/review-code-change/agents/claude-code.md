# Claude Code adapter

Optional discovery metadata for Claude Code and Claude Agent SDK runtimes. It
does not constrain the skill's portable contract.

- Display name: Review Code Change.
- Suggested prompt: "Use the review-code-change skill to build one evidence
  packet and run the complete repository-owned review sequence for this change."
- Read-only enforcement: this skill declares
  `allowed-tools: Read, Grep, Glob, Bash`; run it (and each lens skill) in a
  context that honors that restriction, such as a subagent without file-editing
  tools.
- Lens invocation: run each lens skill sequentially in a fresh subagent seeded
  only with the validated packet; never share the orchestrator's working notes
  or a prior lens's raw reasoning.
