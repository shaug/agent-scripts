# Epic closeout

Use current tracker, repository, and PR evidence. Do not close a parent from
merged-PR count or stale graph state.

## Verify every required outcome

- Reread the complete native child and blocker graph.
- Confirm every required child disposition and every required outcome from a
  closed, canceled, duplicate, or superseded blocker.
- Confirm every required PR result is represented on the current remote base.
- Verify parent acceptance criteria against resulting behavior, not ticket
  labels or administrative state.
- Run required clean-main validation and any parent-level smoke check.
- Verify required documentation, migration, compatibility, rollout, deployment,
  and cleanup outcomes. Deployment and production mutation still require their
  own authority.

Keep the parent open when a not-planned or canceled child leaves an unsatisfied
outcome.

## Sweep late feedback

Before closeout, reread conversation comments, formal reviews, connector
feedback, and thread state for every merged PR in scope. Record a disposition
for every late actionable item.

When late feedback reveals a required correctness, security, acceptance,
architecture, or validation gap:

- keep the epic open;
- use or propose the correctly owned ticket;
- invoke `implement-ticket` from a fresh branch based on current remote state
  when implementation is authorized; and
- require the normal one-ticket validation, review, merge, transition, and
  cleanup result before retrying closeout.

Never reopen or reuse a merged feature branch as the fix path. Do not reproduce
single-ticket review or merge mechanics here.

## Apply close authority

Parent-close authority is separate from child merge and manual child-transition
authority. Without explicit close authority, report that every closeout gate
passes and leave the parent open.

Close each epic separately. For a series or umbrella, verify all component epics
and umbrella acceptance criteria before the umbrella transition.

## Report closeout

Record child dispositions, merged PRs and base representation, clean-main and
acceptance evidence, late-feedback dispositions, remaining deferred or blocked
work, the parent transition performed or withheld, and the exact reason any
parent remains open.
