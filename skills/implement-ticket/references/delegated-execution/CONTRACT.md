# Delegated execution contract

This optional contract lets an external coordinator invoke `implement-ticket`
while retaining authority over consequential external mutations. It is generic:
the coordinator is opaque to Agent Scripts, and no Atelier concept appears in
the protocol.

The capability identifier is
`agent-scripts.implement-ticket/delegated-execution/v1`.

## Contract ownership

- `capability.json` is the discovery manifest and is validated by
  `capability.schema.json`.
- `invocation.schema.json` owns the invocation shape.
- `checkpoint-request.schema.json` and `checkpoint-response.schema.json` own the
  synchronous fencing exchange.
- `result.schema.json` owns the terminal result shape.
- `validate.py` validates schemas and cross-field semantics without third-party
  dependencies.
- This document owns process semantics that JSON Schema cannot express.

All objects reject unknown fields. An unsupported version, malformed object,
failed validator, failed checkpoint command, or ambiguous response blocks
execution.

## Invocation

The caller validates and supplies one invocation object before any mutation. It
binds the run to:

- one ticket and tracker;
- one repository, exact base ref, and exact base SHA;
- one caller-owned work identifier and revision;
- opaque caller-owned approval evidence;
- intent, scope, non-goals, constraints, and done definition;
- required validation and review expectations;
- a finite authority ceiling;
- one desired delivery outcome;
- the terminal states the caller can consume;
- an argv-style checkpoint command;
- the caller's last consumed checkpoint sequence; and
- an opaque continuation token.

The checkpoint command is an array of executable and argument strings. Agent
Scripts sends one JSON checkpoint request on standard input and requires exactly
one JSON checkpoint response on standard output. It does not invoke a shell,
interpret extra output, persist credentials, or inspect the continuation token.
The first request sequence is exactly one greater than the invocation's
`last_sequence`, so a new delegate can continue an existing caller-owned claim.

The generic terminal states remain `ready_pr`, `ready_prs`, `merged`, `blocked`,
and `requires_epic`. A caller may narrow this set. `implement-ticket` must not
select an outcome the invocation excludes. If its only correct outcome is
excluded, it returns `blocked` without performing the excluded action.

## Consequential mutation checkpoint

Immediately before every consequential external mutation, `implement-ticket`
sends a `pre_external_mutation` request. The finite action vocabulary is:

- `repository.candidate.create`
- `repository.candidate.push`
- `pull_request.create`
- `pull_request.update`
- `review.reply`
- `review.resolve`
- `ticket.update`
- `ticket.dependencies.update`
- `ticket.followup.create`
- `changeset.carve`
- `pull_request.merge`
- `repository.branch.delete`
- `deployment.execute`
- `production.mutate`
- `destructive.execute`

The request includes the invocation identity, current continuation token,
strictly increasing sequence, action, exact current ticket observation, exact
candidate when one exists, and a concise proposed-effect description.

Candidate push, pull-request, review, carving, merge, and candidate-branch
deletion checkpoints require the exact candidate. A push checkpoint describes
the proposed remote URL, full ref, base SHA, and head SHA before publication.

The coordinator must reread its authoritative state and return `allow` or
`deny`. `allow` must name the same invocation and request sequence and return a
new opaque continuation token. `deny` echoes the request's continuation token;
it does not advance durable sequence or token state. Identity mismatch, sequence
mismatch, token mismatch, malformed output, command failure, or unavailable
coordinator blocks the mutation.

An `allow` decision authorizes only that one proposed mutation. It does not
cache authority for a later action.

The bundled validator is stateless. The checkpoint command must atomically
compare the expected sequence and current continuation token with its durable
state before returning `allow`, then persist the returned sequence and token.
For an allowed request it must also persist the invocation ID, phase, action,
proposed effect, exact candidate identity, and acknowledgement before returning.
These records are an append-only authorization ledger; they let the caller
compare the terminal `authority_used` report with every consumed allowance.
Replaying a consumed request must fail. The validator's
`validate_checkpoint_progress` helper checks the sequence and token transition,
but the caller owns atomic persistence and the authorization ledger.

## Candidate publication acknowledgement

Immediately after every successful remote candidate publication or advancement,
`implement-ticket` sends a `candidate_published` checkpoint before any later
mutation or terminal result.

The request contains the verified remote URL, full remote ref, base SHA, and
published head SHA. The coordinator returns `allow` only after it has durably
acknowledged that exact candidate. Its response must repeat the acknowledged
head SHA. A missing or different SHA blocks continuation.

This post-publication acknowledgement closes the unavoidable interval between a
Git push and the coordinator's durable record. The pushed candidate remains a
recoverable project artifact even when acknowledgement fails. A blocked result
may report that verified published candidate whether acknowledgement succeeded
or failed. It becomes shared coordinator state only after the caller records it
in a later verified transition.

## Terminal result

The terminal result is always validated before return. It records:

- terminal state and exact identities;
- whether implementation state is `none`, `local`, or `published`;
- a remotely reachable candidate and publication topology when one exists;
- whether the handoff is transferable;
- checkpoint sequence and final continuation token;
- validation and review observations;
- authority actually used;
- unresolved obligations; and
- one next action or blocking reason.

`ready_pr`, `ready_prs`, and `merged` require published, transferable candidate
state. `ready_pr` requires exactly one PR; `ready_prs` requires a stack.
`requires_epic` requires no implementation state.

Delivery terminals must report every required validation command as passed at
the exact candidate, satisfy requested independent review, and report zero
unresolved material feedback when requested.

Published implementation must report the candidate push in `authority_used`. A
result containing a pull request must also report the corresponding pull-request
create or update action. Validation and review observation names are unique;
duplicate observations cannot override one another by array order. An ordered
`ready_prs` stack contains distinct pull request identities, URLs, and heads,
and its final pull request head equals the reported candidate head. Each PR
records its exact base ref, base SHA, head ref, and head SHA. The first base ref
and SHA equal the invocation base; every later base ref and SHA equal the
previous PR head ref and SHA.

A blocked run with published implementation must return its transferable
candidate. It may have zero pull requests when execution blocked after the push
but before PR creation, including when candidate acknowledgement failed. A
blocked run with only local implementation returns no candidate, sets
`transferable` to false, and explains why no durable handoff exists. It must
never describe a local-only SHA as transferable.

The caller must validate every terminal result against the durable checkpoint
ledger tail, not merely the invocation's starting position. The bundled
`validate_result_checkpoint_state` helper requires the terminal sequence and
continuation token to equal that caller-supplied tail. A stale terminal
checkpoint blocks handoff.

A material ticket-observation change always causes the caller to deny the
current invocation. Eligibility may be reevaluated only before starting a fresh
invocation with a newly observed ticket contract. The current invocation's
terminal result therefore continues to identify its original ticket observation
truthfully.

## Compatibility and failure

Standalone invocations remain unchanged and may return the documented human
handoff. Delegated execution applies only when the caller supplies a valid v1
invocation.

There is no daemon, callback server, or background lease. The checkpoint command
is synchronous and caller-owned. If the caller disappears, execution fails
closed at the next checkpoint and preserves any already-published candidate.

The coordinator identity is cooperative attribution, not authentication.
Operating-system permissions, repository access, and provider controls remain
the enforcement boundaries.
