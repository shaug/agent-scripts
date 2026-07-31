# Claude Code adapter

Optional discovery metadata for Claude Code and Claude Agent SDK runtimes. It
does not constrain the skill's portable contract.

- Display name: Review Fix Loop.
- Suggested prompt: "Use the review-fix-loop skill to run the standalone
  review/fix/converge loop for this committed candidate — `local_commit` if
  fixes should stay local for me to publish myself, or `update_pr` if it should
  push once, immediately after convergence — or to validate this
  invocation/checkpoint/terminal-result document, or to run and record just one
  complete review pass."
- Standalone workflows: `scripts/local_commit.py`'s `run_local_commit(...)` and
  `scripts/update_pr.py`'s `run_update_pr(...)` are the two full end-to-end
  entry points (see
  [`references/local-commit.md`](../references/local-commit.md) and
  [`references/update-pr.md`](../references/update-pr.md)). Every intermediate
  fix commit stays local under both policies; only `update_pr` publishes, and
  only once, immediately after the aggregate review comes back clean. A
  non-`converged` terminal result always reports its retained, unpushed commits
  in `unpushed_commits` plus an `operator_action` naming what the operator must
  do next — never silently drop them.
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
