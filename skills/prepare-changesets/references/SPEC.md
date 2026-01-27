# prepare-changesets

## Skill Specification

### Purpose

The `prepare-changesets` skill takes an **existing, review-ready branch of
work** and deconstructs and recomposes it into an **ordered sequence of
intentional, reviewable changesets**, preserving behavior while improving
reviewability, with each changeset represented as its own branch and pull
request.

The goal is to transform a large, monolithic branch into a **set of cohesive,
incrementally mergeable deliverables** that:

- reduce reviewer cognitive load,
- preserve correctness at every step,
- allow incremental integration where possible,
- and, when fully merged, are functionally equivalent to the original branch.

This skill works *backwards* from an already-implemented solution, capturing the
invariants required for trust-first, agent-assisted development.

______________________________________________________________________

## Inputs and Preconditions

The skill operates on:

- a **source branch**:
  - contains all intended changes,
  - believed to be logically correct and complete,
  - may span many commits;
- a **base branch** (typically `main`);
- a clean working tree.

Preconditions:

- The source branch must be rebased or mergeable onto the base branch.
- The source branch must build and pass tests (to the extent applicable).
- The working tree must be clean before starting.

______________________________________________________________________

## Changeset Model

A **changeset** is:

- a cohesive, intentional unit of work,
- designed to be reviewed and reasoned about independently,
- ordered relative to other changesets,
- mergeable once all prior changesets have been merged.

Each changeset corresponds to:

- one Git branch,
- one pull request,
- one reviewable deliverable.

______________________________________________________________________

## Rule-of-Thumb for Changeset Size

Changesets should be sized to minimize **cognitive overhead**, not to satisfy
arbitrary metrics.

Guidelines:

- A few hundred *new or changed* lines is ideal.
- Raw deletions typically do **not** introduce significant cognitive overhead,
  provided:
  - it is clear *why* the code is being removed,
  - and what replaces or obsoletes it.

Exceptions are acceptable for:

- purely mechanical refactors,
- systematic renaming,
- low-level changes with minimal semantic impact.

The primary focus is:

- **cohesiveness of intent**, and
- **reviewability**, not raw line counts.

______________________________________________________________________

## Decomposition Preferences

When creating changesets, the skill should prefer:

- separating **renames** from **behavioral changes** into distinct changesets;
- introducing **additive changes first**, before modifying or removing existing
  behavior;
- deferring user-visible or API-exposed changes until later changesets;
- avoiding changesets that mix unrelated concerns.

Wide refactors should either:

- be isolated into an early changeset, or
- be deferred entirely.

______________________________________________________________________

## Branch Creation and Naming Strategy

Given:

- base branch `B`,
- source branch `S`,

the skill must:

1. Create a new ordered sequence of changeset branches.
2. Each changeset branch must:
   - be branched from its immediate predecessor (or from `B` for the first
     changeset),
   - contain only that changeset’s work,
   - exclude work intended for later changesets.

### Branch Naming Convention

Each changeset branch name must:

- retain the original source branch name, and
- append a suffix of the form:

```
-<x>-of-<y>
```

Where:

- `x` is the 1-based index of the changeset,
- `y` is the total number of changesets.

Example:

```
feature/cloud-host-migration-1-of-4
feature/cloud-host-migration-2-of-4
feature/cloud-host-migration-3-of-4
feature/cloud-host-migration-4-of-4
```

This naming is mandatory and exists to make ordering explicit and human-legible.

______________________________________________________________________

## Pull Request Requirements

Each changeset must have a corresponding pull request.

### PR Titles

- All changeset PRs must share **the same base title**, summarizing the overall
  feature.
- The title must append:

```
(x of y)
```

Example:

```
Cloud host migration (2 of 4)
```

This reinforces that each PR is part of a unified whole.

______________________________________________________________________

### PR Bodies

Each PR body must:

1. **Summarize the overall feature** first.
2. Clearly explain **what part of the feature this changeset provides**.
3. Explicitly document:
   - any temporary scaffolding,
   - any feature flags,
   - any intermediate correctness accommodations that are introduced to support
     decomposition.

The PR body must make it clear:

- what is intentionally incomplete at this stage,
- and how later changesets will complete or clean up the work.

This documentation is critical for reviewer trust.

______________________________________________________________________

## Incremental Mergeability Requirements

Each changeset branch must be:

- mergeable into the base branch **once all prior changesets are merged**;
- non-breaking to existing functionality at that point in the sequence.

To achieve this, the skill may:

- introduce feature flags,
- introduce runtime-configurable toggles,
- introduce deploy-time environment flags,
- introduce temporary scaffolding code.

### Feature Flag Policy

Feature flags should be used **only when necessary**.

Preference order:

1. Additive, non-exposed code paths
2. Runtime feature flags
3. Deploy-time environment variables
4. Code-level conditionals (last resort)

Flags should be:

- minimized,
- centralized,
- documented,
- and removed or fully enabled in the **final changeset** whenever possible.

______________________________________________________________________

## Database Migration Guidelines

Database migrations may be recomposed across **multiple changesets** to reduce
cognitive load and avoid large, coupled changes.

Rules:

- **Data integrity takes precedence over all other concerns.**
- Migrations in the source branch are **not** considered atomic or indivisible.
- Acceptable decomposition strategies include:
  - introducing nullable columns first,
  - backfilling or validating data,
  - applying non-null constraints later,
  - adding foreign key constraints as early as possible to enforce integrity.

The final merged state must reflect the same schema and constraints as the
source branch, modulo ordering differences introduced by decomposition.

### Validation Requirements

The skill should:

- use a resettable test database,
- apply migrations from:
  - the source branch, and
  - the fully merged changeset sequence,
- compare resulting schemas (e.g. via schema dumps),
- and validate that they are equivalent.

______________________________________________________________________

## Recordkeeping and Temporary Artifacts

The skill may introduce **recordkeeping files** to manage decomposition and
tracking, provided that:

- they are clearly documented,
- either live under `.gitignore` *or* are explicitly marked as temporary,
- and are removed by the final changeset.

These artifacts exist solely to support correctness during decomposition.

______________________________________________________________________

## Equivalence Guarantee

A critical invariant:

> **After all changesets are merged in order, the resulting codebase must be
> functionally equivalent to the source branch.**

Acceptable differences include:

- commit history shape,
- additional commits for scaffolding or documentation,
- mechanical differences introduced by decomposition.

Unacceptable differences include:

- missing functionality,
- altered behavior,
- regressions not present in the source branch.

______________________________________________________________________

## Verification and Comparison

It is encouraged that the skill:

- mirror the full changeset chain into a **temporary test base**,
- merge all changesets in order into that base,
- and compare the result against the source branch.

This comparison exists to validate equivalence and catch decomposition errors
early.

______________________________________________________________________

## Pull Request Management Subskills

The skill should include (or delegate to) subskills for:

- creating GitHub pull requests with the correct base branch,
- merging an approved changeset,
- adjusting downstream changeset branch bases,
- propagating review changes forward,
- keeping downstream PRs alive and correctly diffed.

This choreography must be handled mechanically and deterministically.

______________________________________________________________________

## Three-Phase Execution Model

The skill operates in **three strict phases**:

### Phase 1: Analyze and Recommend

- Analyze the source branch.
- Recommend an ordered changeset decomposition.
- Describe each changeset’s intent, scope, and dependencies.
- No branches or PRs are created.

______________________________________________________________________

### Phase 2: Create and Compare

- Create changeset branches.
- Create corresponding pull requests.
- Apply flags and scaffolding as needed.
- Validate incremental mergeability.
- Compare merged changesets against the source branch.

______________________________________________________________________

### Phase 3: Merge and Propagate

- Merge changesets in order as they are approved.
- Propagate changes into downstream changesets.
- Update PR bases and content accordingly.

**Once a phase is completed, the skill must not revisit previous phases.**

______________________________________________________________________

## Non-Goals

This skill does **not**:

- plan new work from scratch,
- reorder, remove, or merge changesets after Phase 1,
- add new changesets mid-execution,
- support inverted merge strategies,
- optimize for minimal number of changesets.

The focus is **trust, reviewability, and correctness**, not cleverness.

______________________________________________________________________

## Why This Skill Exists

This skill exists to address the central asymmetry of agent-assisted
development:

> **Implementation cost has collapsed; trust cost has not.**

By working backwards from real, messy branches, this skill codifies what is
required to make agent-generated work *human-compatible*.

It is a proving ground for the workflows Atelier is designed to support
natively.

______________________________________________________________________

If you want, the next natural step would be to:

- carve this into a formal `SKILL.md`,
- annotate which parts must be structured vs prose,
- or walk through a concrete example branch and pressure-test the spec.

But at this point: **this is extremely solid, coherent, and implementable.**
