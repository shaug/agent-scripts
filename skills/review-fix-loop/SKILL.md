---
name: review-fix-loop
description: Validate the review-fix-loop invocation, checkpoint, and terminal-result contracts that later children of epic #95 use to run the standalone review-remediation workflow. Use when authoring, resuming, or terminating a review-fix-loop invocation to check its documents against the shared schemas before trusting or acting on them. This child does not yet run reviewers, apply fixes, acquire locks, manage worktrees, or publish anything; see design/review-fix-loop.md and references/CONTRACT.md for the full behavioral design and current implementation status.
allowed-tools: Read, Bash
---

# Review Fix Loop

`review-fix-loop` will become a repository-owned skill that takes cooperative
ownership of an existing committed candidate, runs the complete repository
review suite, applies material ticket-scoped fixes, and repeats until review
converges or a bounded stop condition is reached. The full design is
[`design/review-fix-loop.md`](../../design/review-fix-loop.md).

This child ([issue #96](https://github.com/shaug/agent-scripts/issues/96), the
first of epic [#95](https://github.com/shaug/agent-scripts/issues/95)) defines
and validates only the contracts later children build on:

- the **invocation** a caller or standalone operator supplies to start or resume
  a loop;
- the **durable checkpoint** the loop would record between phases; and
- the **terminal result** the loop returns.

It does not run a reviewer, apply a fix, acquire a lock, manage a worktree,
recover from interruption, or publish anything — those behaviors belong to
issues #97 (local locking, isolated attempts, and recovery), #98 (reviewer
isolation and orchestration), #99 (`local_commit`), and #100 (`update_pr`). Do
not invoke this skill expecting an executable review-fix loop yet; use it to
validate a document you or a later child produced against the shared schemas.

## Load the contracts

Read [`references/CONTRACT.md`](references/CONTRACT.md) and the three schemas
beside it before authoring or trusting any invocation, checkpoint, or
terminal-result document:

- [`references/invocation.schema.json`](references/invocation.schema.json)
- [`references/checkpoint.schema.json`](references/checkpoint.schema.json)
- [`references/terminal-result.schema.json`](references/terminal-result.schema.json)

[`references/examples/`](references/examples) contains complete, valid documents
for both the `local_commit` and `update_pr` publication policies, including a
`changes_remaining` and a `blocked` terminal result, each already in the
canonical serialized form `scripts/validate.py` produces.

## Validate a document

`scripts/validate.py` is dependency-free, matching the convention used by the
bundled `review-code-change` review-suite contract, so it works wherever this
skill is installed:

```bash
python3 skills/review-fix-loop/scripts/validate.py invocation path/to/invocation.json
python3 skills/review-fix-loop/scripts/validate.py checkpoint path/to/checkpoint.json
python3 skills/review-fix-loop/scripts/validate.py terminal-result path/to/result.json
```

Each prints `valid <kind>: <path>` and exits `0` on success, or prints one
diagnostic per violation to stderr and exits `1`. A malformed document exits
`2`.

The module also exposes importable functions for a caller that already holds
parsed documents in memory: `validate_invocation`, `validate_checkpoint`,
`validate_terminal_result`, `reconstruct_cycle_accounting` (derive consumed and
remaining fix cycles from a checkpoint's recorded attempts), and
`validate_terminal_against_checkpoint` (confirm a terminal result's budget and
head/base identities match the checkpoint it derives from). See
[`references/CONTRACT.md`](references/CONTRACT.md) for the cross-field semantics
these functions enforce beyond plain JSON Schema, and
`scripts/tests/test_validate.py` for the complete valid, invalid, boundary, and
round-trip case coverage.

## Non-goals of this child

- Running a reviewer or applying a fix.
- Acquiring a local or remote-target lock, managing a worktree, or recovering an
  interrupted attempt.
- Publishing anything, including the `update_pr` expected-old fast-forward
  update.
- Migrating `implement-ticket`, `babysit-pr`, `carve-changesets`, or any other
  existing caller.
- Owning acceptance criteria or a caller-specific acceptance ledger — the
  contract records `acceptance_reconciliation_required` but the caller always
  retains its own ledger.
