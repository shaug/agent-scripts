---
name: review-correctness
description: Review a code change against its stated goal for material behavioral, security, authorization, compatibility, data-integrity, performance, and validation failures. Use for a correctness-focused PR, branch, or patch review, either from raw repository and ticket evidence or from the repository-owned shared review packet. Return only the shared finding and verdict shape and never modify the reviewed candidate.
---

# Review Correctness

Determine whether the candidate satisfies its observable contract without
introducing a material failure. Review only; leave fixes and workflow mutations
to the caller.

## Load the contracts

1. Read the canonical review contract at `../../review-suite/CONTRACT.md` and
   its packet and result schemas.
2. Read [the correctness rubric](references/correctness-rubric.md).
3. Treat the canonical contract as authoritative for required evidence, finding
   fields, severity, confidence, verdicts, candidate identity, and base drift.
4. Return `blocked` with the missing dependency when the canonical contract is
   unavailable. Do not invent a local replacement.

## Establish the candidate

- When given a shared review packet, validate it before reviewing. Reject
  malformed structure. Convert missing essential evidence into a conforming
  `blocked` result.
- When invoked from raw evidence, construct the packet conceptually before
  inspecting implementation details. Establish repository, base, captured head,
  complete diff, observable goal, acceptance criteria, explicit non-goals,
  preserved behavior, source documents, and focused and full validation.
- Do not infer missing intent from the implementation. Return `blocked` when the
  goal, acceptance criteria, candidate identity, complete diff, or required
  validation evidence cannot be established.
- Bind the result to the packet's candidate identity. Never reuse evidence after
  a head change. Apply the shared base-drift rules when only the base advances.

## Review in priority order

1. Compare the observable goal, acceptance criteria, non-goals, and preserved
   behavior with the complete candidate diff.
2. Read applicable repository instructions, named architecture or contract
   documents, representative nearby implementation, and nearby tests.
3. Inspect security and authorization boundaries before lower-risk behavior.
4. Inspect applicable behavioral, failure, concurrency, data-integrity,
   compatibility, validation, and material performance dimensions from the
   rubric.
5. Prefer explicit repository rules and demonstrated local idioms over generic
   advice.
6. Check that tests and exact validation evidence prove success, failure,
   regression, and preserved behavior required by the change contract.

Do not mechanically emit every category. Follow evidence into the dimensions
that can materially affect this candidate.

## Apply the finding threshold

Raise a finding only when concrete ticket, code, test, repository, or runtime
evidence demonstrates a material current concern and supports a smallest
sufficient correction.

- Mark a demonstrated correctness, security, authorization, acceptance,
  architecture, compatibility, or validation failure `blocking`.
- Use `strong_recommendation` only for a material, tractable, ticket-scoped
  safety improvement with demonstrated current risk.
- Use `defer` only for a real, evidenced concern intentionally outside the
  active ticket or dependent on a missing decision.
- Omit style, praise, broad modernization, numerical quality rules, speculative
  hardening, imagined compatibility, and generic best-practice advice.

Do not perform the dedicated whole-solution or local code-simplicity lenses.
Report correctness consequences of complexity only when they create a concrete
failure or make required behavior unprovable.

## Return the shared result

Return only JSON conforming to
`../../review-suite/contracts/review-result.schema.json` with lens
`correctness`.

- Return `clean` when no blocking or strong-recommendation finding remains.
- Return `changes_required` when at least one actionable gating finding remains.
- Return `blocked` when essential evidence or a product or architecture decision
  prevents a trustworthy verdict.
- Keep deferred findings non-gating.
- Do not add praise, a scorecard, generic resources, or prose outside the shared
  result.

## Preserve read-only integrity

Do not edit or format files, create repository artifacts, commit, push, resolve
threads, post reviews, or update tickets. Run only safe read-only inspection and
validation commands. When the caller supplies pre-review candidate state,
preserve it exactly and report any unexpected mutation as an integrity failure.
