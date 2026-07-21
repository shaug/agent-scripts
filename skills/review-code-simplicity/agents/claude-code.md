# Claude Code adapter

Optional discovery metadata for Claude Code and Claude Agent SDK runtimes. It
does not constrain the skill's portable contract.

- Display name: Review Code Simplicity.
- Suggested prompt: "Use the review-code-simplicity skill to find concrete
  behavior-preserving reuse and DRY improvements in this change."
- Read-only enforcement: this skill declares
  `allowed-tools: Read, Grep, Glob, Bash`; run it in a context that honors that
  restriction, such as a subagent without file-editing tools.
