# Code review suite contract

This directory is the canonical, non-skill foundation for the repository-owned
code review suite. Review skills consume these contracts; they must not copy or
silently redefine them.

## Contract ownership

- `contracts/review-packet.schema.json` owns the packet shape.
- `contracts/review-result.schema.json` owns the finding and result shapes.
- This document owns the cross-field semantics that JSON Schema cannot express
  clearly.
- `scripts/validate.py` enforces both schemas and these semantic rules without
  third-party dependencies.
- `fixtures/` contains raw review inputs and separate expected material outcomes
  for deterministic tests and independent forward tests.

## Review packet

A review packet binds the review to one candidate and states what that candidate
must accomplish. Required evidence is deliberately distinct from optional
context.

Required packet sections are:

1. `repository`: repository identity and base branch.
2. `candidate`: the captured head, the comparison base or merge base, and the
   complete candidate diff.
3. `change_contract`: observable goal, non-empty acceptance criteria, explicit
   non-goals, and behavior or invariants to preserve.
4. `sources`: applicable repository instructions, named design or contract
   documents, and representative nearby patterns. Arrays may be empty only when
   the caller has established that no such source applies.
5. `validation`: at least one `focused` and one `full` validation entry, with
   every required command's exact result or an explicit reason that the command
   is unavailable.

Optional `context` records public API, data, authorization, compatibility, and
operational concerns when applicable. Optional `worktree` records tracked,
staged, unstaged, untracked, and ignored state when candidate integrity depends
on it. Optional `base_drift` records why evidence was retained or reset after
the base advanced.

Do not infer missing intent. Missing repository identity, goal, acceptance
criteria, candidate identity, a complete diff, or required validation evidence
prevents a trustworthy review and must yield a `blocked` result.

## Finding semantics

Every material finding contains:

- a stable identifier;
- its owning lens;
- severity and confidence;
- the requirement, non-goal, invariant, or repository rule involved;
- concrete evidence;
- the concern and material impact;
- the smallest sufficient proposed change; and
- the expected behavioral or complexity effect.

Use these severities:

- `blocking`: a demonstrated correctness, security, authorization, acceptance,
  architecture, compatibility, or validation failure that prevents merge.
- `strong_recommendation`: a material, tractable, ticket-scoped improvement
  supported by concrete evidence and a sufficiently specified correction.
- `defer`: a real concern intentionally outside the active ticket, dependent on
  an unresolved decision, or not justified strongly enough to change the
  candidate.

Do not emit aesthetic preferences, praise, generic resources, numerical quality
scores, imagined compatibility needs, speculative hardening, or abstractions
that merely move complexity behind another name.

## Verdict semantics

- `clean`: no `blocking` or `strong_recommendation` finding remains. Deferred
  findings may be retained without failing the gate.
- `changes_required`: at least one actionable `blocking` or
  `strong_recommendation` finding remains.
- `blocked`: essential evidence or a product or architecture decision is
  missing, so no trustworthy merge verdict is possible. Include at least one
  concrete `blocking_reason`.

`clean` and `changes_required` results must include complete candidate identity
and must not include `blocking_reasons`. A `blocked` result may omit candidate
fields that the caller could not establish and may preserve already-demonstrated
findings, but those findings do not convert the blocked review into a merge
verdict.

## Candidate identity and base drift

Bind every result to the packet's captured head and comparison base. Any edit,
rebase, conflict resolution, or update operation that changes the head
invalidates head-bound evidence and requires a new packet.

When only the base advances, inspect the effective merge candidate. Retain prior
head-bound evidence only when all of these are true:

- the effective diff is unchanged;
- the resulting tree is unchanged;
- no conflict exists;
- no relevant base code overlaps the candidate; and
- repository policy does not require a complete reset.

Record the decision and reason in `base_drift`. Otherwise reset affected or all
evidence as repository policy and the changed candidate require.

## Fixture use

Each fixture keeps `expected.json` separate from `prompt.md` and `packet.json`.
Give a forward-testing reviewer only the prompt and raw packet. Do not expose
the expected outcome, implementation transcript, prior conclusions, or suspected
finding.
