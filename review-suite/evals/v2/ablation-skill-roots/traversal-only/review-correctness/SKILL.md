---
name: review-correctness
description: Review a code change, diff, PR, branch, or patch for bugs and material behavioral, security, authorization, compatibility, data-integrity, performance, and validation failures against its stated goal. Use when asked to find bugs or run a correctness-focused review, either from raw repository and ticket evidence or from the repository-owned shared review packet. Returns only the shared finding and verdict shape and never modifies the reviewed candidate.
allowed-tools: Read, Grep, Glob, Bash
---

# Review Correctness

Determine whether the candidate satisfies its observable contract without
introducing a material failure. Review only; leave fixes and workflow mutations
to the caller.

**ABLATION NOTICE (measurement-only variant, never shipped):** this copy exists
solely to isolate the consumer/impact-traversal pass's own contribution for
`review-suite/evals/v2/gate-manifest.json`'s preregistered `s1` ablation matrix
(`#57`). The verification-sufficiency pass below is deliberately disabled/ no-op
for this measurement configuration only. The real, shipped skill at
`skills/review-correctness/SKILL.md` is unchanged and always performs both
passes; this file is never installed or distributed.

## Load the contracts

1. Read the bundled canonical review contract at
   [references/review-suite/CONTRACT.md](references/review-suite/CONTRACT.md)
   and its packet and result schemas beside it. Inside this skill's source
   monorepo, the repository-root `review-suite/` directory is the canonical
   origin and the bundled copies are kept byte-identical to it.
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
- When an orchestrator supplies a validated simplification result beside the
  packet, assess each gating proposal against the packet's requirements and
  preserved behavior. Keep the packet itself unchanged.

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

## Perform the required traversal pass only (measurement configuration)

Perform this pass on every review and record its evidence in the shared result.
It is a dimension of this single correctness lens, not a routed specialist
module; do not build or delegate to a separate security,
concurrency-as-a-context, compatibility/migration, operations, or UI module.

1. **Consumer/impact-traversal pass.** For each changed shared symbol, public
   contract, or behavior toggle, search the repository for other call sites,
   importers, or consumers — including ones the candidate diff does not touch.
   Inspect material negative space: unchanged consumers or paths that must still
   honor the changed contract. Record one `consumer_impact_evidence` entry per
   changed symbol that requires one: the `changed_symbol`, its defining
   `location`, one or more concrete `consumer_search_evidence` items describing
   what the search actually found, and a `disposition` of
   `all_consumers_consistent`, `inconsistency_found`, or `no_other_consumers`. A
   disposition claiming other consumers exist requires evidence covering more
   than the changed symbol's own location. Treat a genuine inconsistency as a
   blocking correctness finding; recording the disposition alone does not
   satisfy the review.

**This measurement configuration deliberately does not perform the
verification-sufficiency pass.** Do not ask whether a claimed validation command
or test would actually fail for its triggering condition, do not record any
`verification_sufficiency_evidence` entry, and do not raise a finding whose sole
basis is that pass. This is a controlled ablation, not a judgment that the pass
is unnecessary.

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

## Disposition supplied simplification proposals

For every gating proposal supplied by the orchestrator, return one shared
`proposal_dispositions` item:

- use `compatible` when the proposal preserves demonstrated correctness; or
- use `unsafe` when concrete correctness or repository evidence invalidates the
  proposal even though the current candidate may already be correct.

Do not turn a rejected hypothetical edit into a candidate correctness finding. A
proposal disposition does not change the correctness verdict by itself. If the
proposal cannot be assessed from trustworthy evidence, return `blocked`.

## Return the shared result

Return only JSON conforming to the bundled
[review-result schema](references/review-suite/review-result.schema.json) with
lens `correctness`.

- Return `clean` when no blocking or strong-recommendation finding remains.
- Return `changes_required` when at least one actionable gating finding remains.
- Return `blocked` when essential evidence or a product or architecture decision
  prevents a trustworthy verdict.
- Keep deferred findings non-gating.
- Include proposal dispositions when the orchestrator supplied simplification
  proposals, using the shared contract shape.
- Include a `consumer_impact_evidence` entry for every changed symbol the
  traversal pass above examined. Omit an entry only when the pass genuinely
  found nothing applicable to record. Do not include any
  `verification_sufficiency_evidence` entry in this measurement configuration.
- Do not add praise, a scorecard, generic resources, or prose outside the shared
  result.

## Preserve read-only integrity

Do not edit or format files, create repository artifacts, commit, push, resolve
threads, post reviews, or update tickets. Run only safe read-only inspection and
validation commands. Runtimes that support tool restriction should enforce the
`allowed-tools` frontmatter, which excludes file-editing tools. The shell
remains necessary for validation commands and can still mutate files, so prefer
a sandboxed or deny-write shell where available; the recorded before/after
candidate state is the authoritative integrity check. When the caller supplies
pre-review candidate state, preserve it exactly and report any unexpected
mutation as an integrity failure.
