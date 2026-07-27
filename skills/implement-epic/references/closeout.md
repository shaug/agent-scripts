# Epic closeout

Use current tracker, repository, PR, deployment, and criterion-specific
acceptance evidence. Closed children and merged PRs are delivery/administrative
state, not parent acceptance.

## Verify every required outcome

- Reread the complete native child and blocker graph, including closed children.
- Confirm every required child disposition and every required outcome from a
  closed, canceled, duplicate, or superseded blocker.
- Read every required child's criterion-specific acceptance ledger and reject
  missing, failed, unavailable, stale, wrong-environment, or category-mismatched
  evidence regardless of native state.
- Confirm every required PR result is represented on the current remote base.
- Build and verify the parent's own ledger against resulting behavior, not
  labels or administrative state.
- Verify current-main representation and the exact deployed SHA whenever a
  criterion requires deployment.
- Require screenshot or geometry/computed-layout evidence for explicit visual
  requirements; functional browser checks alone are insufficient.
- Run required clean-main validation and any parent-level smoke check.
- Verify required documentation, migration, compatibility, rollout, deployment,
  and cleanup outcomes. Deployment and production mutation still require their
  own authority.

Keep the parent open when any required outcome or evidence item is unsatisfied.

## Sweep late feedback

Before closeout, reread conversation comments, formal reviews, connector
feedback, and thread state for every merged PR in scope. Record a disposition
for every late actionable item.

When late feedback reveals a required correctness, security, acceptance,
architecture, or validation gap:

- keep or reopen the epic when authorized;
- require a focused corrective ticket and a regression test at the escaped
  boundary;
- invoke `implement-ticket` from a fresh branch based on current remote state
  when implementation is authorized;
- revalidate the full affected customer journey proportionally; and
- require renewed acceptance evidence plus the normal one-ticket validation,
  review, merge, transition, and cleanup result before retrying closeout.

Never reopen or reuse a merged feature branch as the fix path. A merged
corrective child does not justify reclosure until affected-journey evidence
passes. Do not reproduce single-ticket review or merge mechanics here.

## Apply close authority

Parent-close authority is separate from child merge, deployment, protected
verification, and manual child-transition authority. Without explicit close
authority, report that every closeout gate passes and leave the parent open.

Close each epic separately. For a series or umbrella, verify all component child
and parent ledgers before the umbrella transition.

## Report closeout

Record child dispositions, merged PRs and base representation,
criterion-specific child and parent acceptance ledgers, exact deployment
identities, clean-main evidence, late-feedback dispositions, remaining deferred
or blocked work, the parent transition performed or withheld, and the exact
reason any parent remains open.
