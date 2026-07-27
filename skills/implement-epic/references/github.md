# GitHub epic graph adapter

Use this adapter only for parent, child, dependency, selection, refresh, and
epic-closeout state owned by GitHub. `implement-ticket` owns GitHub PR-host and
single-ticket mechanics.

## Read native graph state

- Resolve the repository and live epic identity.
- Read epic and child titles, bodies, issue types, states, scope-affecting
  comments, acceptance criteria, and required verification items.
- Read native `parent`, `subIssues`, `blockedBy`, and `blocking` relationships
  through GraphQL or an equivalent structured API.
- Read relevant closed-blocker dispositions and verify their delivered outcomes
  in the authoritative source.
- Read criterion-specific acceptance ledgers for every required child regardless
  of native state.
- Inspect existing open and merged PR identities only to prevent duplicate child
  selection; delegate detailed PR state to `implement-ticket`.

Do not derive graph ownership or dependency order from issue number, title,
label, Markdown task list, or prose when native relationships exist.

## Select and refresh

Choose an in-scope child whose native `blockedBy` set has no open issue, whose
required closed-blocker outcomes exist, and that is either open or auto-closed
with required acceptance still missing. Route the latter through
`implement-ticket` with its closeout observation and granted or withheld reopen
authority. Do not select an accepted, superseded, or otherwise terminal closed
child. Treat canceled or not-planned blockers with missing outcomes as
unresolved.

After every caller-verified merge, delivery, or GitHub issue transition, reread
the complete graph regardless of the returned terminal state. Verify the live
transition first, then separately decide which edges require delivery and which
require the child's complete current acceptance ledger. A `ready_pr`,
`ready_prs`, or merged delivery with acceptance pending remains incomplete but
still changes graph state. For a stacked delivery, also verify reported
topology, every completed PR transition, and full-chain representation on the
base without taking ownership of decomposition mechanics.

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
shared closeout reference passes, every required child ledger passes, and live
native relationships show no required open child or blocker. Record the ledger
evidence in the issue when authorized and useful. Never infer parent completion
from `CLOSED` children or merged PR count.
