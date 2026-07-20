---
name: review-solution-simplicity
description: Review a code change for whole-solution over-engineering by mapping its major mechanisms to stated requirements and proposing a materially smaller requirement-complete design. Use for architecture-level simplicity review of a PR, branch, or patch, either from raw ticket and repository evidence or from the shared review packet. Preserve justified safety and operational complexity, return only the shared result shape, and never modify the candidate.
---

# Review Solution Simplicity

Determine whether the candidate's implementation strategy is materially larger
than its real problem. Review only; leave redesign and workflow mutations to the
caller.

## Load the contracts

1. Read the canonical review contract at `../../review-suite/CONTRACT.md` and
   its packet and result schemas.
2. Read
   [the solution-simplicity rubric](references/solution-simplicity-rubric.md).
3. Treat the canonical contract as authoritative for evidence, finding fields,
   severity, confidence, verdicts, candidate identity, and base drift.
4. Return `blocked` with the missing dependency when the canonical contract is
   unavailable. Do not invent or copy a local replacement.

## Establish the candidate

- Validate a supplied shared review packet before reviewing it. Convert missing
  essential evidence into a conforming `blocked` result.
- From raw evidence, establish repository and candidate identity, the complete
  diff, observable goal, acceptance criteria, explicit non-goals, preserved
  behavior, applicable repository sources, and exact validation results before
  judging the design.
- Do not infer product requirements, compatibility promises, operational
  constraints, or historical data from the implementation. Return `blocked` when
  a requirement-complete comparison depends on a missing decision.
- Bind the result to the captured candidate and follow the shared base-drift
  rules.

## Compare whole solutions

1. Restate the observable change contract without implementation terminology.
2. Inventory the candidate's major mechanisms: services, abstractions, states,
   data models, compatibility paths, queues, caches, frameworks, migrations,
   configuration, repair logic, and operational machinery.
3. Map each mechanism to a stated requirement, verified invariant, repository
   architecture rule, or evidenced current operational constraint.
4. Challenge only unsupported or disproportionate mechanisms.
5. Construct the smallest concrete alternative that still satisfies every real
   requirement and preserves required failure semantics.
6. Compare concepts, states, branches, ownership boundaries, migration and
   operational burden, and failure modes. Do not use line count as the measure.
7. Report a change only when the alternative is specific and
   requirement-complete.

Correctness, security, concurrency, migration, compatibility, rollout, and
recovery requirements override simplicity. Treat the signals in the rubric as
questions, not automatic findings.

## Apply the finding threshold

Every finding must identify the unsupported mechanism, cite the requirements and
repository evidence used for comparison, describe a concrete smaller design,
show how it preserves required behavior and failure semantics, and name the
material reduction in concepts, states, ownership, or operational burden.

- Use `blocking` only when the design violates ticket scope or required
  architecture, or creates a demonstrated correctness or operational hazard.
- Use `strong_recommendation` for a clear, tractable, requirement-complete
  simplification with material cognitive or operational value.
- Use `defer` only for an evidenced concern outside the active ticket or
  awaiting a named decision.
- Omit aesthetic disagreement, vague requests to simplify, numerical complexity
  rules, speculative product direction, and alternatives that merely relocate
  complexity.

Do not perform line-level DRY, naming, formatting, or helper-extraction review.
Do not duplicate the correctness lens or remove explicit tests to shrink a
change.

## Return the shared result

Return only JSON conforming to
`../../review-suite/contracts/review-result.schema.json` with lens
`solution_simplicity`.

- Return `clean` when every major mechanism is justified and no gating finding
  remains.
- Return `changes_required` when a blocking or strong-recommendation finding
  remains.
- Return `blocked` when missing requirements or decisions prevent a trustworthy
  comparison.
- Keep deferred findings non-gating and do not add prose outside the result.

## Preserve read-only integrity

Do not edit or format files, apply the alternative, create repository artifacts,
commit, push, resolve threads, post reviews, or update tickets. Run only safe
read-only inspection and validation commands. Preserve supplied pre-review
candidate state exactly and report unexpected mutation as an integrity failure.
