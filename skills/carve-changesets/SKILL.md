---
name: carve-changesets
description: Recompose a large review-ready source branch into an ordered chain of intentional, independently reviewable changesets while preserving its final behavior. Use when asked to split, carve, decompose, publish, review, merge, or propagate an oversized branch as stacked GitHub pull requests; keeps proposal state ephemeral, promotes truth into git and GitHub, delegates repository review and PR lifecycle work, and requires explicit authority for every remote mutation.
---

# Carve Changesets

Turn one existing review-ready source branch into a plain-git, plain-GitHub
changeset chain. Preserve the source branch, keep each intermediate result safe
and reviewable, and prove that the fully merged chain is equivalent to the
source candidate.

This skill owns decomposition, truth promotion, chain mechanics, whole-chain
equivalence, and downstream propagation. It delegates per-changeset review to
`review-code-change` and a published PR's lifecycle to `babysit-pr` without
copying either skill's workflow.

## Load the references

- Always read [the normative contract](references/SPEC.md) before planning or
  mutating a chain.
- Read [the plan schema](references/plan-schema.md) before creating or editing
  `.carve-changesets/plan.json`.
- Read [the CLI reference](references/cli.md) before invoking a subcommand or
  selecting flags.
- Read [the suite handoffs](references/suite-handoffs.md) before reviewing a
  changeset, publishing PRs, or delegating a PR lifecycle.

Use `scripts/cli.py` as the single command surface. Resolve script and reference
paths from this skill's root, not from a repository-relative installation
assumption.

## Require compatible capabilities

Require a runtime that can:

- resolve exact git refs, inspect ancestry and trees, and create isolated local
  branches or worktrees without mutating the source branch;
- run Python 3 and separately approved repository validation commands;
- reach GitHub over the network and use an authenticated `gh` session whenever
  publication, live PR state, review, merge, or propagation is in scope;
- load repository-owned `review-code-change` for required per-changeset review;
- load repository-owned `babysit-pr` and retain task ownership while waiting
  whenever a published PR lifecycle is delegated; and
- read current checks, reviews, comments, reactions, and resolved-thread state
  before a readiness or merge claim.

Return `blocked` before the affected mutation when a required capability is
missing. Do not download a substitute workflow, bypass review, publish a PR that
has no lifecycle owner, or treat partial GitHub data as clean.

## Resolve the operating contract

Before mutation, discover or receive and verify:

- repository identity, current checkout, worktree state, and applicable
  repository instructions;
- exact source and base branches and SHAs, their merge base, source freshness,
  and the complete candidate diff;
- the immutable source outcome and the behavior, schema, constraints, public
  interfaces, migrations, and rollout properties the final chain must preserve;
- an explicitly approved test command and any required database, build,
  integration, or manual validation commands;
- cognitive-load guardrails, acceptable intermediate states, decomposition
  order, feature-flag policy, and database-migration requirements from the
  normative contract;
- the requested terminal boundary: proposal only, local chain, published PRs, or
  fully merged chain; and
- authority for local decomposition, validation execution, publication,
  candidate repair, review communication, merge, propagation, and cleanup.

Treat discovered validation commands as proposals until the user explicitly
approves them. The source branch is immutable throughout the workflow. Stop if
the source is behind the base unless the contract's explicit override and
confirmation are both present.

### Authority levels

- **Decompose-only** permits the ephemeral plan, local changeset branches and
  commits, required trailers, and separately approved validation. It forbids
  every remote write.
- **Publish** additionally permits pushing exact changeset branches, opening or
  updating their correctly based PRs, and delegating each PR to `babysit-pr`
  with `ready_to_merge`. Merge and force-push authority remain withheld.
- **Merge-and-propagate** additionally permits `merge_when_ready`, sequential
  changeset merges after all gates pass, and exact-lease downstream propagation.
  It never permits force-pushing the base, source, merged upstream, or an
  unowned branch.

Pass authority to delegated skills without expansion. Reply and thread
resolution authority remain separate from branch mutation and merge authority.

## Execute the phase workflow

### 1. Propose

Run `preflight` against the exact source and base with the approved test
command. Use `init-plan` to create `.carve-changesets/plan.json`, then replace
every placeholder with cohesive boundaries, ordering, intent, extraction
selectors, validation, and intentional incompleteness. Use `hunk-preview` when
textual hunk selection needs inspection, and require `validate --strict` before
promotion.

At this phase the plan is the only writable truth. Do not create changeset refs
or perform remote operations. Return `plan_ready` when proposal is the requested
boundary.

### 2. Materialize and prove equivalence

Use `create-chain` to create append-only `<source>-N` branches and stamped
commits. Run `validate-chain` with approved validation, `compare` for the
reconstructed tree, and the applicable `squash-check` or `db-compare` evidence.
Use `status --local-only` to inspect live local truth without GitHub.

Construct and run the required `review-code-change` packet for every exact
changeset candidate. The review suite is read-only; this skill applies accepted
fixes and rebuilds invalidated validation and review evidence. Return
`chain_ready` only after every local candidate and the full chain satisfy the
contract.

### 3. Publish

Require publish authority before any remote mutation. `push-chain` and
`pr-create` are dry-run by default; use their execution flag only after
reverifying the exact remote, branches, heads, predecessor bases, metadata, and
exclusive ownership. Use `status` to reconstruct published truth from live git
and GitHub rather than a local cache.

Delegate each exact PR to `babysit-pr` using the policy and evidence in the
suite handoff reference. While delegated, do not run a competing CI, feedback,
review, or mutation loop. Return `prs_open` only when every applicable non-merge
gate at the requested boundary passes and merge is withheld.

### 4. Merge and propagate

Require merge-and-propagate authority. When `babysit-pr` returns `merged`,
independently verify the exact merged candidate on the live base, rehydrate the
chain, use `propagate` to rewrite only the downstream suffix with exact leases,
then hand the next exact PR back to `babysit-pr`.

Use `merge-propagate` only when the resolved workflow explicitly assigns the
direct merge to this CLI and no delegated owner controls that PR. Both execution
paths are dry-run by default and require the merge-and-propagate acknowledgement
before mutation. Resume interrupted work from live git and GitHub state, not
from the plan or a cache.

Return `all_merged` only after every PR, propagation step, final equivalence
check, required validation, and authorized cleanup has been verified.

## Preserve safety and truth

- Keep `.carve-changesets/` ignored and out of commits and PRs.
- Resolve every mutation target to an exact repository, ref, SHA, PR, and
  worktree immediately before acting.
- Keep remote mutation dry-run by default and use explicit refspecs and exact
  leases where the contract permits force-push.
- Never use a plan edit or cached head to override materialized, published, or
  merged truth.
- Never reset away, overwrite, or delete user work, credentials, environment
  files, databases, or non-reproducible artifacts.
- Rebuild candidate-bound validation, review, CI, and feedback evidence after a
  head change; retain evidence across base-only drift only with the documented
  proof.

## Stop conditions

Return `blocked` without widening scope when:

- source, base, repository, candidate, chain, PR, or ownership identity is
  ambiguous, stale, conflicting, or changes unexpectedly;
- the source is dirty, incomplete, mutable, or behind the base without the
  explicit two-part override;
- a proposed changeset cannot remain cohesive, independently understandable,
  safely intermediate, or mergeable in sequence;
- required validation, review, equivalence, migration, or GitHub evidence is
  missing or fails;
- stronger live truth conflicts with the plan or other weaker records;
- safe progress would require rewriting the source, base, merged upstream, or an
  unowned branch;
- required authority, capability, infrastructure, or exclusive ownership is
  absent; or
- a material product, data, architecture, migration, or rollout decision is
  unresolved.

Ordinary CI wait time, difficult decomposition, or an independently ready later
changeset is not a blocker.

## Return one terminal handoff

Return exactly one terminal state with evidence bound to the current source,
base, chain, and PR candidates:

- `plan_ready`: exact source/base identity, complete validated plan and proposed
  validation, with no materialized branch or remote mutation.
- `chain_ready`: exact local branch heads, trailers, ancestry, per-changeset
  validation and clean review, whole-chain equivalence, and no new publication.
- `prs_open`: all `chain_ready` evidence plus exact remote heads, correctly
  based open PRs, current metadata, applicable non-merge gates, and merge
  withheld.
- `all_merged`: every exact PR verified merged on the base, propagation and
  final equivalence verified, required validation passing, and cleanup complete
  or precisely limited.
- `blocked`: one concrete blocker, exact phase and identities reached, preserved
  partial artifacts and last trustworthy evidence, and one action or decision
  needed to resume.

An open PR, green check, local diff, stale review, or plan alone is never enough
to claim a later terminal state.
