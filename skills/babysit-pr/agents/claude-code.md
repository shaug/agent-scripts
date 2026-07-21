# Claude Code adapter

Optional discovery metadata for Claude Code and Claude Agent SDK runtimes. It
does not constrain the skill's portable contract.

- Display name: Babysit PR.
- Suggested prompt: "Use the babysit-pr skill to monitor this pull request until
  it reaches the requested completion policy."
- Long waits: Claude Code bounds foreground shell commands, so run
  `scripts/gh_pr_watch.py --watch` as a background shell task and read its
  incremental JSONL output between other work, or run bounded foreground windows
  with `--watch --max-polls <n>` or `--watch --stop-when-clear` and re-invoke
  until terminal. Retain ownership of the monitoring task either way; never
  detach and declare monitoring complete.
- Locking: stop the background watcher before `--once` or `--retry-failed-now`;
  all modes share one exclusive state lock per repository/PR.
- Fresh read-only review context: invoke repository-owned `review-code-change`
  in a subagent (Agent tool) restricted to read-only tools, giving it only raw
  candidate evidence.
