# Claude Code adapter

Optional discovery metadata for Claude Code and Claude Agent SDK runtimes. It
does not constrain the skill's portable contract.

- Display name: Review Correctness.
- Suggested prompt: "Use the review-correctness skill to review this code change
  for material correctness, security, compatibility, and validation failures."
- Read-only enforcement: this skill declares
  `allowed-tools: Read, Grep, Glob, Bash`; run it in a context that honors that
  restriction, such as a subagent without file-editing tools.
