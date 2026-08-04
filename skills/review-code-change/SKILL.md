---
name: review-code-change
description: "Use when a code change, diff, PR, branch, or patch should be reviewed with the complete repository-owned review suite, or when asked to run code review. Scope is one candidate, read-only: it never modifies what it reviews and never depends on a third-party review skill. Fails closed when required evidence or a local lens skill is missing. Returns one bounded aggregate verdict reconciled across the repository's solution-simplicity, correctness, and code-simplicity lenses."
allowed-tools: Read, Grep, Glob, Bash, Agent, Task, Skill
---

# Review Code Change

Produce one trustworthy, bounded verdict for one captured candidate. Orchestrate
the repository-owned lenses; do not reproduce their rubrics.

## Load the contracts and dependencies

1. Read the bundled canonical review contract at
   [references/review-suite/CONTRACT.md](references/review-suite/CONTRACT.md)
   and both shared schemas beside it. Inside this skill's source monorepo, the
   repository-root `review-suite/` directory is the canonical origin and the
   bundled copies are kept byte-identical to it.
2. Read [the orchestration protocol](references/orchestration-protocol.md).
3. Verify that `review-solution-simplicity`, `review-correctness`, and
   `review-code-simplicity` are available and readable.
4. Return a conforming aggregate `blocked` result naming every missing skill. Do
   not fall back to another skill or generic self-review.

## Build one evidence packet

Build the shared packet once from raw ticket, PR, repository, candidate, and
validation artifacts. Capture:

- observable goal, acceptance criteria, non-goals, and preserved behavior;
- repository instructions, named specifications, and representative nearby code
  and tests;
- exact head and relevant base or merge-base identity plus the complete diff;
- focused and full validation commands with exact results; and
- worktree state required to prove read-only integrity.

Write the complete diff to a file outside the candidate worktree and record its
absolute location as the packet's `candidate.diff.path`, following the shared
contract's "The candidate diff: inline or referenced by path" section, which
owns that rule and its rationale. Return `blocked` when the file cannot be
written or read back, exactly as for any other missing required evidence.

Exclude implementation transcripts, intended answers, prior conclusions,
suspected findings, and fixture expected outputs. Validate the packet before
invoking any lens. Return `blocked` when required evidence cannot be recovered
safely.

## Run the deliberate sequence

For a full review, invoke the skills sequentially from the same validated
packet:

1. `review-solution-simplicity`
2. `review-correctness`
3. `review-code-simplicity`

Each invocation carries the packet; every lens reads the diff from
`candidate.diff.path` for itself. Do not paste the complete diff into a lens
invocation.

Validate each result before continuing. Stop on a `blocked` result. Stop after a
solution-simplicity result that requires replacing the implementation strategy;
the caller must redesign and start a full review on a new head. For a tractable
in-strategy proposal, invoke correctness with the unchanged packet plus the
validated solution result as separate proposal context. Require one proposal
disposition for each gating simplification finding so correctness can reject an
unsafe proposal without inventing a defect in already-correct candidate code.

Stop after an actionable correctness result; do not spend tokens on local
simplification before the correctness fix. A clean pass through all applicable
lenses ends the review.

## Handle fixes and cycles

The orchestrator is read-only. Return the required fix and next lens; the caller
applies changes and supplies a new packet bound to the new head.

- After solution redesign, a correctness fix, or a code-simplicity fix, restart
  the complete three-lens sequence — solution simplicity, correctness, then code
  simplicity — on the new head. No old-head lens result may contribute to the
  new-head aggregate; a partial rerun cannot produce a valid `clean` aggregate
  (see the shared contract's lens execution evidence requirement).
- Use at most three full fix/re-review cycles by default. On the final cycle,
  return unresolved material findings without requesting another automatic
  cycle.
- Ignore style, praise, speculative hardening, and deferred scope when counting
  cycles.

## Aggregate one result

Follow the protocol to validate, deduplicate, and reconcile results. Correctness
and explicit repository constraints override unsafe simplification. Preserve
deferred findings as non-gating. Preserve proposal dispositions in the aggregate
so every accepted or rejected simplification remains auditable.

Return only JSON conforming to the shared result schema with lens `aggregate`.
Include candidate identity, material findings, blocking reasons, validation
limitations, and the next required action.

- `changes_required`: a blocking or strong-recommendation finding remains.
- `blocked`: evidence, a required dependency, or a lens verdict is
  untrustworthy.
- `clean`: every required lens completed and no gating finding remains, every
  required packet validation entry passed, and `lens_executions` records one
  fresh, current-head, `clean` execution for each of solution simplicity,
  correctness, and code simplicity.

For every `clean` aggregate, populate `lens_executions` from the exact lens
results just validated: each entry names its lens, the aggregate's own head and
comparison-base SHA, its verdict, and `freshly_executed: true`. Never count an
unavailable, skipped, or old-head lens result as clean, and never reuse a prior
aggregate's `lens_executions` for a new head.

Never count an unavailable or skipped required lens as clean.

## Preserve candidate integrity

Bind every packet and result to the captured head. Build a new packet after any
code change, rebase, conflict resolution, or update. For base-only drift, apply
the shared risk-based merge-candidate rules.

Do not edit or format reviewed files, apply fixes, create candidate artifacts,
commit, push, post reviews, resolve threads, approve, merge, or update tickets.
Run only safe read-only inspection and validation commands. Runtimes that
support tool restriction should enforce the `allowed-tools` frontmatter, which
excludes file-editing tools. The shell remains necessary for validation commands
and can still mutate files, so prefer a sandboxed or deny-write shell where
available; the recorded before/after candidate state is the authoritative
integrity check. Verify that the candidate state is unchanged before returning.
