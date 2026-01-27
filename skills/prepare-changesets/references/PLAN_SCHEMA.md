# Prepare Changesets Plan Schema

Use a single JSON plan file to define the ordered changeset chain and make the
mechanical steps deterministic. Store it under `.prepare-changesets/plan.json`
and keep it out of PRs.

The plan is append-only. You can add new changesets at the end as you learn
more, but do not renumber or reorder validated changesets.

## Minimal Example

```json
{
  "feature_title": "Cloud host migration",
  "base_branch": "main",
  "source_branch": "feature/cloud-host-migration",
  "test_command": "npm test",
  "changesets": [
    {
      "slug": "rename-config-types",
      "description": "Rename config types without behavior changes.",
      "include_paths": [
        "src/config/**",
        "src/types/**"
      ],
      "exclude_paths": [],
      "commit_message": "refactor: rename config types",
      "pr_notes": [
        "No behavior changes.",
        "Separates renames from functional changes."
      ]
    },
    {
      "slug": "add-dual-write-path",
      "description": "Add additive dual-write path guarded by a flag.",
      "include_paths": [
        "src/migration/**",
        "src/flags/**"
      ],
      "exclude_paths": [
        "src/migration/cleanup/**"
      ],
      "commit_message": "feat: add dual-write path behind flag",
      "pr_notes": [
        "Introduces temporary flag: enableDualWrite.",
        "Cleanup happens in the final changeset."
      ]
    }
  ]
}
```

## Field Reference

Top-level fields:

- `feature_title` (string, required): The shared PR title base.
- `base_branch` (string, required): Usually `main`.
- `source_branch` (string, required): The review-ready branch to decompose.
- `test_command` (string, optional): A repo-specific validation command.
- `changesets` (array, required): Ordered changesets.

Changeset fields:

- `slug` (string, required): Short identifier used in logs and plan review.
- `description` (string, required): Intent and scope of the changeset.
- `include_paths` (array of strings, required): Glob-like patterns used to pull
  file changes from `source_branch` into this changeset. Patterns are matched
  against the `base_branch..source_branch` file list.
- `exclude_paths` (array of strings, optional): Patterns removed from the
  included set.
- `commit_message` (string, optional): Defaults to `"changeset N: <slug>"`.
- `pr_notes` (array of strings, optional): Bullets describing scaffolding,
  flags, and intentional incompleteness for the PR body.

## Important Constraints

- Keep changesets cohesive by intent, not by line count.
- Prefer additive-first changesets and defer user-visible changes.
- Separate renames from behavioral changes when possible.
- Treat the plan as append-only output. Do not renumber or reorder validated
  changesets after creation.

See `references/SPEC.md` for the full behavioral rules and invariants.
