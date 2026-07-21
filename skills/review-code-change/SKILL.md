---
name: review-code-change
description: Review a code change, diff, PR, branch, or patch with the complete repository-owned review suite. Use when asked to review a change or run code review; builds a trustworthy evidence packet, invokes solution simplicity, correctness, and code simplicity in order, reconciles their results, and returns one bounded aggregate verdict. Fails closed when evidence or local lens skills are missing, remains read-only, and never depends on a third-party review skill.
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

- After solution redesign, restart the full sequence.
- After a correctness fix, rerun correctness and every downstream lens whose
  assumptions changed.
- After a code-simplicity fix, rerun code simplicity and then targeted
  correctness.
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
- `clean`: every required lens completed and no gating finding remains.

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
