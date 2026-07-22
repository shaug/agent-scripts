# GitHub epic graph adapter

Use this adapter only for parent, child, dependency, selection, refresh, and
epic-closeout state owned by GitHub. `implement-ticket` owns GitHub PR-host and
single-ticket mechanics.

## Read native graph state

- Resolve the repository and live epic identity.
- Read epic and child titles, bodies, issue types, states, and scope-affecting
  comments.
- Read native `parent`, `subIssues`, `blockedBy`, and `blocking` relationships
  through GraphQL or an equivalent structured API.
- Read relevant closed-blocker dispositions and verify their delivered outcomes
  in the authoritative source.
- Inspect existing open and merged PR identities only to prevent duplicate child
  selection; delegate detailed PR state to `implement-ticket`.

Do not derive graph ownership or dependency order from issue number, title,
label, Markdown task list, or prose when native relationships exist.

## Select and refresh

Choose only an open in-scope child whose native `blockedBy` set has no open
issue and whose required closed-blocker outcomes exist. Treat canceled or
not-planned blockers with missing outcomes as unresolved.

After a returned `merged` result, verify the GitHub issue transition and reread
the complete parent/sub-issue/blocker graph before selecting another child or
claiming completion. A `ready_pr` or `ready_prs` result does not satisfy a
dependency that requires merge. For a stacked `merged` result, verify the
reported topology, every PR merge, and full-chain representation on the base
without taking ownership of decomposition mechanics.

When duplicate implementation paths exist, do not choose a competing path; pass
the canonical ownership evidence into `implement-ticket` or return `blocked`
when ownership is unresolved.

## Separate tracker and PR host

When GitHub owns issue state and another system hosts code or PRs, retain GitHub
as the graph authority. When Linear owns issue state and GitHub hosts PRs, do
not inspect or mutate same-numbered GitHub issues as graph substitutes; use the
Linear adapter and let `implement-ticket` use its GitHub PR-host adapter.

## Close GitHub epics

With explicit parent-close authority, transition the GitHub epic only after the
shared closeout reference passes and live native relationships show no required
open child or blocker. Record evidence in the issue when authorized and useful.
Never infer parent completion solely from merged PR count.
