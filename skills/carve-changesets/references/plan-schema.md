# Decomposition plan schema

The proposal phase stores one ephemeral JSON plan at
`.carve-changesets/plan.json`. Keep `.carve-changesets/` ignored and out of git.
The plan is authoritative only for changesets that have not been materialized;
live commit trailers, PR metadata, and mainline replace it in later phases.

## Minimal example

```json
{
  "feature_title": "Cloud host migration",
  "base_branch": "main",
  "source_branch": "feature/cloud-host-migration",
  "test_command": "just test",
  "changesets": [
    {
      "slug": "rename-config-types",
      "description": "Rename config types without behavior changes.",
      "mode": "paths",
      "include_paths": ["src/config/**", "src/types/**"],
      "exclude_paths": [],
      "allow_partial_files": false,
      "commit_message": "refactor: rename config types",
      "pr_notes": ["No behavior changes."]
    },
    {
      "slug": "add-dual-write-path",
      "description": "Add the flag-guarded dual-write path.",
      "mode": "hunks",
      "include_paths": ["src/migration/**"],
      "exclude_paths": [],
      "allow_partial_files": true,
      "hunk_selectors": [
        {
          "file": "src/migration/write.ts",
          "contains": ["enableDualWrite"],
          "occurrence": 1
        }
      ],
      "commit_message": "feat: add dual-write path behind flag",
      "pr_notes": [
        "Introduces temporary flag enableDualWrite.",
        "A later changeset removes the accommodation."
      ]
    }
  ]
}
```

## Top-level fields

- `feature_title` (required string): shared title stem for the changeset PRs.
- `base_branch` (required string): mainline branch that precedes changeset 1.
- `source_branch` (required string): immutable review-ready branch to recompose.
- `test_command` (optional string): separately approved validation command.
- `changesets` (required non-empty array): ordered proposed changesets.

## Changeset fields

- `slug` (required string): stable concise intent identifier carried into commit
  and PR metadata.
- `description` (required string): independently reviewable goal and scope.
- `mode` (optional string): `paths` by default, `patch`, or `hunks`.
- `include_paths` (string array): glob patterns included by `paths`, or a coarse
  filter for `hunks`; required and non-empty for `paths`.
- `exclude_paths` (optional string array): glob patterns removed from the
  selected paths.
- `allow_partial_files` (optional boolean): whether a changeset may select only
  some textual hunks from a file; defaults to true.
- `patch_file` (required string for `patch`): a non-empty patch path, normally
  under `.carve-changesets/patches/`.
- `hunk_selectors` (required non-empty object array for `hunks`): explicit
  textual hunk selectors described below.
- `commit_message` (optional string): changeset commit subject/body before the
  required metadata trailers are added.
- `pr_notes` (optional string array): scaffolding, flags, intentional
  incompleteness, and later changeset ownership shown in the PR body.

## Hunk selector fields

- `file` (required string): repository-relative old or new path; prefer the new
  path after a rename.
- `range` (optional string): exact unified-diff hunk header.
- `contains` (optional string array): every string must appear in the hunk body.
- `excludes` (optional string array): none of the strings may appear.
- `occurrence` (optional positive integer): select one match when the other
  filters match more than one hunk.
- `all` (optional boolean): select every textual hunk in the file.

Selectors must resolve unambiguously. Binary changes use `patch`, not `hunks`.
Pure renames should use `paths` or `patch` so rename intent is preserved.

## Authoring rules

- Keep one cohesive intent per changeset and prefer additive foundations before
  consumers, cutovers, or removals.
- Make changesets append-only once validated; do not reorder or renumber an
  existing materialized position.
- Document temporary flags and incomplete states in `pr_notes`, including the
  later changeset that removes them.
- Use `validate --strict` before materialization. Placeholder warnings, missing
  files, unmatched selectors, ambiguous hunks, or unappliable patches must be
  resolved rather than ignored.
- After materialization, do not use plan edits to change the meaning or identity
  of an existing changeset. Create a new candidate commit and renew evidence.
