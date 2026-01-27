---
name: prepare-changesets
description: >-
  GitHub-specific workflow to recompose a large, review-ready source branch
  into an ordered chain of smaller changesets (stacked branches + GitHub PRs)
  that preserve behavior and improve reviewability. Use when working with
  GitHub PR stacks via the gh CLI to split monolithic branches, create stacked
  PRs, merge reviewed changesets, and propagate/update downstream PR bases after
  merges.
compatibility: >-
  Requires Git and the GitHub CLI (gh) authenticated to a GitHub repo, plus
  network access to GitHub for PR creation, merging, and base updates.
license: MIT
metadata:
  provider: github
  vcs: git
  pr_cli: gh
  workflow: stacked-prs
  phase_model: three-phase
  plan_file: .prepare-changesets/plan.json
  dry_run_default: 'true'
---

# Prepare Changesets

Follow the spec and keep planning separate from mechanical execution.

Always load:

- `references/SPEC.md`
- `references/PLAN_SCHEMA.md`

Use deterministic helpers:

- `scripts/preflight.py`
- `scripts/init_plan.py`
- `scripts/validate.py`
- `scripts/status.py`
- `scripts/create_chain.py`
- `scripts/compare.py`
- `scripts/validate_chain.py`
- `scripts/pr_create.py`
- `scripts/merge_propagate.py`
- `scripts/propagate.py`
- `scripts/push_chain.py`
- `scripts/db_compare.py`

## Phase 0: Preflight

Require a clean working tree and valid base/source branches. Treat the source
branch as immutable reference state. Never modify, rebase, or rewrite it as part
of this process. Preflight simulates merging the source into the base on a
temporary branch and runs the test command on the source branch.

Run:

```bash
skills/prepare-changesets/scripts/preflight.py \
  --base main \
  --source feature/my-large-branch \
  --test-cmd "<repo-specific test command>"
```

If you do not know the test command, ask once. If still unknown, proceed with
`--skip-tests` and explicitly record this in the plan.

## Phase 1: Analyze And Recommend (Plan Only)

Do not create branches or PRs in this phase. Do not interleave planning and
execution phases.

1. Inspect the change surface.

Use:

```bash
git diff --stat main..feature/my-large-branch
git diff --name-status main..feature/my-large-branch
```

Use `rg` to find refactors, renames, and flaggable boundaries. Focus on semantic
and conceptual boundaries of change, not just file counts or diff size.

2. Propose an ordered changeset chain.

Honor the decomposition preferences in `references/SPEC.md`, especially:

- separate renames from behavioral changes
- prefer additive-first changesets
- defer user-visible or API-exposed changes
- keep intent cohesive Do not propose changesets that require future changesets
  to be partially present in order to be understandable or reviewable.

3. Initialize and edit the plan.

Create a plan template:

```bash
skills/prepare-changesets/scripts/init_plan.py \
  --base main \
  --source feature/my-large-branch \
  --title "My feature title" \
  --changesets 4
```

Then edit `.prepare-changesets/plan.json` to reflect the Phase 1 plan:

- define cohesive `slug` and `description` per changeset
- use `include_paths` to pull in only the relevant files
- use `exclude_paths` to prevent accidental overlap
- document scaffolding, flags, and intentional incompleteness in `pr_notes`

Validate:

```bash
skills/prepare-changesets/scripts/validate.py
```

After Phase 1 validation, the plan is immutable. Do not revise, reinterpret, or
extend it in later phases.

## Phase 2: Create And Compare

Use the plan to create the ordered branch chain, then verify equivalence. Do not
revisit Phase 1 planning or reinterpret the validated plan.

1. Create the branch chain.

```bash
skills/prepare-changesets/scripts/create_chain.py
```

This creates mandatory branch names:

- `<source-branch>-1-of-N`
- `<source-branch>-2-of-N`
- ...

The script uses path-based inclusion rules. Expect to refine each branch
manually.

2. Review each changeset branch.

For each changeset branch:

- review the diff relative to its intended base
- run repo-specific tests when practical
- adjust commits to keep the changeset cohesive

3. Open stacked PRs with correct bases.

Base rules:

- changeset 1 base: `base_branch`
- changeset i>1 base: previous changeset branch

Title rule:

- `<feature_title> (i of N)`

Body requirements:

- summarize the overall feature first
- explain what this changeset provides
- call out temporary scaffolding, flags, and intentional incompleteness PR
  bodies should document intent, scope, and temporary compromises only. Do not
  use them for marketing, justification, or speculative discussion.

Use the helper to generate `gh` commands and PR bodies:

```bash
skills/prepare-changesets/scripts/pr_create.py
```

This uses `gh pr create` under the hood and defaults to dry-run. Execute for
real:

```bash
skills/prepare-changesets/scripts/pr_create.py --no-dry-run
```

If `gh` is not authenticated, run `gh auth login` once, then retry.

4. Compare the fully merged chain to the source branch. This comparison
   validates that the fully merged changeset chain is functionally equivalent to
   the source branch, not merely that diffs apply cleanly.

```bash
skills/prepare-changesets/scripts/compare.py
```

If differences appear, fix the chain and re-run the comparison.

Validate incremental mergeability by running tests after each changeset merge:

```bash
skills/prepare-changesets/scripts/validate_chain.py --test-cmd "<repo-specific test command>"
```

## Phase 3: Merge And Propagate

Do not revisit planning. Only merge in order and propagate forward. Do not
interleave planning and execution phases, and do not reinterpret the validated
plan.

Use one of these explicit workflows.

1. Merge a reviewed changeset PR, then propagate and update PR bases.

Dry-run first:

```bash
skills/prepare-changesets/scripts/merge_propagate.py --index i
```

Execute for real:

```bash
skills/prepare-changesets/scripts/merge_propagate.py --index i --no-dry-run
```

2. If the PR was merged separately, propagate and clean up downstream PRs.

If you have already synced the local base branch to include the merged
changeset, skip the local merge simulation:

```bash
skills/prepare-changesets/scripts/propagate.py \
  --merged-index i \
  --skip-local-merge \
  --no-dry-run
```

By default, propagation updates downstream PR bases with `gh pr edit --base`.
Disable that with `--no-update-pr-bases`. Add `--push` to push updated branches
with `--force-with-lease` (remote defaults to `origin`).

## Operational Notes

- Prefer explicit plan edits over clever automation.
- Keep `.prepare-changesets/plan.json` out of PRs.
- Use the script for mechanical steps and Git for judgment calls.
- For database migrations, follow the validation guidance in
  `references/SPEC.md`.
- Use `db-compare` to run schema dump commands on the source branch and the
  fully merged chain, then diff the outputs.
- If judgment or new information conflicts with the validated plan, stop and
  escalate rather than improvising.
