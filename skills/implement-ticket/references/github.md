# GitHub ticket and PR adapter

Use GitHub independently as an issue tracker, a PR host, or both. Apply only the
sections owned by its role for this ticket.

## Ownership boundary

- When GitHub owns ticket state, use the issue preflight, scope, relationship,
  duplicate-work, closing-reference, and transition rules below.
- Whenever GitHub hosts the PR, use PR preflight, review, check, merge, and
  branch rules.
- When Linear owns the ticket and GitHub hosts the PR, route parent, blocker,
  status, and close decisions through the Linear adapter. Do not inspect or
  mutate a same-numbered GitHub issue as a substitute.

## Issue preflight and scope

When GitHub owns ticket state:

- read the live title, body, state, issue type, labels, and scope-affecting
  comments;
- read native `parent`, `subIssues`, `blockedBy`, and `blocking` relationships
  through GraphQL or an equivalent structured tool;
- use native issue type and sub-issues to apply the epic scope guard;
- verify every required closed-blocker outcome in its authoritative source; and
- search open and merged PRs plus plausible feature branches for an existing or
  superseding implementation.

Do not infer ownership, epic status, or dependency state from title, number,
Markdown task lists, or prose when native relationships exist. A label may
support but cannot override contradictory structured state.

For a ticket that belongs to an epic, read the parent outcome and only the
sibling contracts or prerequisite results needed for correctness and independent
shipping. Never select another child or mutate the graph from this skill.

When duplicate branches or PRs exist, compare actual patches or resulting trees
and retain one canonical implementation path. For an open canonical path owned
by another worker, return `blocked` with its identity unless ownership is
explicitly transferred; never claim its candidate as this run's `ready_pr`. When
a merged PR is verified on the base and the ticket is already complete, return
`merged` with that evidence without creating new state. Return `blocked` rather
than creating a competing PR when canonical ownership is unresolved.

## PR-host preflight and contract

- Resolve the repository from the request or checkout and confirm
  authentication.
- Confirm the remote base, current checkout, branch, and worktree topology.
- Inspect open and merged PRs that reference the owning tracker ticket.
- Use one tracker ticket per branch and PR.
- When GitHub owns ticket state, use the repository's closing syntax, normally
  `Fixes #<issue>`.
- Determine whether that syntax will automatically close or transition the
  ticket on merge and disclose the consequence in the resolved completion policy
  before publishing or merging. Use a non-closing reference when automatic
  closure would conflict with that policy.
- When another tracker owns state, use its required reference and avoid GitHub
  closing syntax unless a real GitHub issue is also intentionally in scope.
- Describe the branch as a whole, preserve material non-goals, and report actual
  validation.
- Confirm the PR base and head match the ticket worktree.

Use file-based commit and PR messages when shell interpolation could alter
Markdown.

## Review state

Capture exact PR head and base SHAs. Read conversation comments, formal reviews,
inline comments, and thread resolution state; use GraphQL or another
thread-aware API when flat PR output is insufficient.

For required human review, record reviewer, state, reviewed commit, submission
time, and relevant base. Require current-candidate approval under repository
policy. Apply the generic base-drift gate after a base advance.

For required connector review, discover and record before polling:

- connector identity;
- automatic or request-driven initiation;
- exact initiation action and per-push policy;
- run-start evidence;
- accepted clean signal; and
- polling window and interval.

Fail closed if this contract cannot be discovered. Accept a clean connector
result only when it is tied to the captured candidate by a current-head formal
review, a comment naming the head, a configured reaction on a request/result
naming the head, or another repository-documented completion signal with
equivalent candidate identity. Require zero unresolved connector-authored
threads.

Do not infer current approval from timing, comment order, a generic bot message,
CI success, or a verdict on an earlier head. After every head change, require a
fresh candidate-bound signal. For base-only drift, use the generic drift gate
and the connector's documented retention policy.

For every actionable comment, review, and thread:

1. Verify it against the current code and ticket.
2. Fix it or reject it with concrete evidence.
3. Run affected and required validation.
4. Push when code changed.
5. Reply on the originating surface when possible and record disposition.
6. Resolve a thread only after disposition is complete.

Require zero undispositioned actionable items before merge. Use at most three
connector feedback passes by default; do not spend passes on rejected,
out-of-scope, polish, or hypothetical findings.

## Checks, merge, and ticket transition

- Read required GitHub Actions checks and logs directly.
- Continue monitoring pending checks; ordinary wait time is not a user blocker.
- Separate in-scope failures from infrastructure, dependency, or
  external-service failures.
- Fix only demonstrated ticket-scoped failures, revalidate, push, and restart
  every invalidated current-head gate.
- Immediately before merge, reread head, base, checks, reviews, comments,
  reactions, and threads.
- Apply the generic base-drift gate if the base advanced.
- Use the repository's approved merge method.
- Verify PR state, merged result, base content, and GitHub issue transition
  before cleanup.
- When the ticket is an epic child, reread its affected native `blocking` and
  sibling `blockedBy` relationships after the transition and report newly
  unblocked work without selecting or mutating it.

If local worktree ownership prevents the CLI from switching to the base, merge
through the GitHub API when authorized and perform local cleanup separately.
Never close a parent issue from this skill.
