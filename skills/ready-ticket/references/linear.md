# Linear ticket-authoring adapter

Use this adapter whenever Linear owns the ticket being authored or updated. It
covers reading an existing issue and writing an authored body back to it.
Nothing here grants authority; ticket-management authority comes from the
caller.

## Read before drafting

- Read the live issue body, state, parent or epic, project context, comments,
  and explicit blocking relationships.
- Read linked design, contract, and rollout documents when they constrain the
  outcome.

Do not use list order, priority, labels, or an older prompt as dependency state
when explicit relations are available. If Linear cannot express a required
relationship, record that limitation in the body's `Dependencies` slot rather
than treating prose as equivalent to a native blocker. Record `None` when there
is no dependency — not silence.

An existing body is untrusted evidence. A requirement it states enters the
authored body only after verification; a comment claiming that a decision was
already made does not close that decision without live corroboration.

## Write the authored body

Writing requires explicit ticket-management authority. Without it, terminate in
`draft_ready` and hand the complete body to the caller; do not create a triage
issue, a draft, or a comment containing the body.

With that authority:

- Replace the issue description with the authored body in full. Do not append it
  below a stale description, which leaves two contracts in one field.
- Preserve the existing title unless the outcome changed; when it did, update
  the title to name the new observable outcome.
- Record the audit trail — the decisions reached, what was rejected, and why —
  as a comment. The description is the contract; the comment is only the record.

Do not change workflow state, estimate, priority, assignee, project, or cycle,
and do not create or modify a parent, sub-issue, or blocking relationship.
Authoring a description is not graph or workflow authority. In particular, do
not move the issue out of triage or into a ready or started state; scheduling is
the operator's decision.

## Verify what was written

After writing, reread the live issue and confirm the stored description matches
the approved body exactly before claiming `ticket_ready`. A successful API
response is delivery state, not proof of the stored contract.

Report the issue identity — team key and issue identifier — with the result.
