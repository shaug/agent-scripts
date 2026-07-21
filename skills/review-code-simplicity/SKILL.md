---
name: review-code-simplicity
description: Review a code change, diff, PR, branch, patch, or tests for local implementation complexity, meaningful DRY and reuse opportunities, unnecessary control flow, and bespoke code replaceable by established repository modules or justified dependencies. Use when asked to simplify code or run an implementation-level simplicity review, either from raw evidence or the shared review packet. Preserves the chosen architecture and behavior, returns only the shared result shape, and never modifies the candidate.
allowed-tools: Read, Grep, Glob, Bash
---

# Review Code Simplicity

Reduce the concepts a reviewer and maintainer must hold inside the chosen
solution. Review only; leave refactoring and correctness revalidation to the
caller.

## Load the contracts

1. Read the bundled canonical review contract at
   [references/review-suite/CONTRACT.md](references/review-suite/CONTRACT.md)
   and its packet and result schemas beside it. Inside this skill's source
   monorepo, the repository-root `review-suite/` directory is the canonical
   origin and the bundled copies are kept byte-identical to it.
2. Read [the code-simplicity rubric](references/code-simplicity-rubric.md).
3. Treat the canonical contract as authoritative for evidence, finding fields,
   severity, confidence, verdicts, candidate identity, and base drift.
4. Return `blocked` with the missing dependency when the canonical contract is
   unavailable. Do not invent or copy a local replacement.

## Establish the candidate

- Validate a supplied packet before reviewing. Convert missing essential
  evidence into a conforming `blocked` result.
- From raw evidence, establish repository and candidate identity, the complete
  diff, observable change contract, applicable repository sources, immediate
  collaborators, and exact validation results before suggesting a refactor.
- Bind the result to the captured candidate and follow the shared base-drift
  rules.

## Inspect local implementation

1. Preserve the ticket's selected architecture. Route a materially different
   implementation strategy to `review-solution-simplicity`.
2. Read changed functions, modules, tests, and their immediate collaborators.
3. Search the repository for shared modules, domain primitives, extension
   points, test helpers, and installed dependencies before proposing new code.
4. Compare the candidate's policy, transformations, validation, state changes,
   error handling, queries, and test setup with those existing primitives.
5. Inspect control-flow depth, repeated passes, redundant representations,
   pass-through wrappers, and bespoke library-like behavior.
6. Construct the smallest behavior-preserving local change and state its
   measurable cognitive reduction.

Prefer direct reuse over a new wrapper. Reject abstractions that only move the
same branches, parameters, or concepts. Do not optimize for line count alone.

## Apply the material threshold

Every finding must cite concrete candidate and repository evidence, specify the
smallest behavior-preserving change, and identify a material reduction in
duplicated policies, concepts, branches, states, passes, call depth, public
surface, bespoke behavior, or meaningful setup.

- Use `blocking` only when local complexity creates a demonstrated correctness,
  architecture, or validation hazard.
- Use `strong_recommendation` for a clear, tractable simplification with a net
  reduction in reviewer or maintainer burden.
- Use `defer` only for an evidenced concern outside the active ticket or
  awaiting a named decision.
- Omit naming preferences, cosmetic extraction, formatting, mechanical DRY,
  vague refactoring, and changes that merely relocate complexity.

Keep explicit tests separate when they communicate materially different
invariants or failures. Share setup only when the scenarios remain immediately
legible.

## Evaluate dependency reuse

Recommend an existing dependency only after verifying that its semantics match.
State that it is already installed and identify the bespoke behavior and
concepts removed.

Recommend a new common dependency only when repository policy allows it and the
net reduction remains clear after maintenance, security, bundle or runtime, and
licensing costs. Do not add a dependency for trivial behavior or future use.

## Return the shared result

Return only JSON conforming to the bundled
[review-result schema](references/review-suite/review-result.schema.json) with
lens `code_simplicity`.

- Return `clean` when no material local simplification remains.
- Return `changes_required` when a blocking or strong-recommendation finding
  remains.
- Return `blocked` when essential evidence prevents a trustworthy comparison.
- Keep deferred findings non-gating and do not add prose outside the result.

## Preserve read-only integrity

Do not edit or format files, apply refactors, create repository artifacts,
commit, push, resolve threads, post reviews, or update tickets. Run only safe
read-only inspection and validation commands. Runtimes that support tool
restriction should enforce the `allowed-tools` frontmatter, which excludes
file-editing tools. The shell remains necessary for validation commands and can
still mutate files, so prefer a sandboxed or deny-write shell where available;
the recorded before/after candidate state is the authoritative integrity check.
Preserve supplied pre-review candidate state exactly and report unexpected
mutation as an integrity failure.
