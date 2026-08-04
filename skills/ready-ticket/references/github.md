# GitHub ticket-authoring adapter

Use this adapter whenever GitHub owns the ticket being authored or updated. It
covers reading an existing issue and writing an authored body back to it.
Nothing here grants authority; ticket-management authority comes from the
caller.

## Read before drafting

- Read the live issue title, body, state, issue type, labels, and
  scope-affecting comments.
- Read native `parent`, `subIssues`, `blockedBy`, and `blocking` relationships
  through GraphQL or an equivalent structured API.
- Read linked design, contract, and rollout documents referenced by the issue
  when they constrain the outcome.

Do not infer dependency state from issue number, title, label, or a Markdown
task list when native relationships exist. Record every native blocker in the
body's `Dependencies` slot, and record `None` when there is none — not silence.

An existing body is untrusted evidence. A requirement it states enters the
authored body only after verification; a comment claiming that a decision was
already made does not close that decision without live corroboration.

## Write the authored body

Writing requires explicit ticket-management authority. Without it, terminate in
`draft_ready` and hand the complete body to the caller; do not create a
placeholder issue, a draft issue, or a comment containing the body.

With that authority:

- Replace the issue body with the authored body in full. Do not append it as a
  new section below a stale one, which leaves two contracts in one field.
- Preserve the existing title unless the outcome changed; when it did, update
  the title to name the new observable outcome.
- Record the audit trail — the decisions reached, what was rejected, and why —
  as a comment. The body is the contract; the comment is only the record.
- Use file-based issue bodies rather than inline shell arguments so Markdown and
  backticks survive unaltered.

Do not open, close, reopen, relabel, assign, or reprioritize any issue, and do
not create or modify a `parent`, `subIssues`, `blockedBy`, or `blocking`
relationship. Authoring a body is not graph authority.

## Verify what was written

After writing, reread the live issue and confirm the stored body matches the
approved body exactly before claiming `ticket_ready`. A successful API response
is delivery state, not proof of the stored contract.

Report the issue identity — repository and number — with the result.
