---
name: review-fix-loop
description: Validate the review-fix-loop invocation, checkpoint, and terminal-result contracts, and provide the local execution substrate (common-directory locking, isolated attempt worktrees, durable checkpoint persistence, verified fast-forward-only canonical promotion, and interrupted-attempt recovery) that later children of epic #95 use to run the standalone review-remediation workflow. Use when authoring, resuming, or terminating a review-fix-loop invocation to check its documents against the shared schemas, or when acquiring a candidate lock, running an isolated remediation attempt, or recovering an interrupted one. This skill does not yet run reviewers, select or apply a fix's content, or publish anything; see design/review-fix-loop.md and references/CONTRACT.md for the full behavioral design and current implementation status.
allowed-tools: Read, Bash
---

# Review Fix Loop

`review-fix-loop` will become a repository-owned skill that takes cooperative
ownership of an existing committed candidate, runs the complete repository
review suite, applies material ticket-scoped fixes, and repeats until review
converges or a bounded stop condition is reached. The full design is
[`design/review-fix-loop.md`](../../design/review-fix-loop.md).

Issue [#96](https://github.com/shaug/agent-scripts/issues/96) (the first child
of epic [#95](https://github.com/shaug/agent-scripts/issues/95)) defined and
validates the contracts every other child builds on:

- the **invocation** a caller or standalone operator supplies to start or resume
  a loop;
- the **durable checkpoint** the loop would record between phases; and
- the **terminal result** the loop returns.

Issue [#97](https://github.com/shaug/agent-scripts/issues/97) adds the local
execution substrate those contracts describe: common-Git-common-directory
locking, isolated attempt worktrees, durable checkpoint persistence and resume
reconciliation, verified fast-forward-only canonical promotion, and recovery of
an interrupted attempt. See [Local execution](#local-execution) below.

This skill still does not run a reviewer, select or apply a fix's content, or
publish anything — those behaviors belong to issue #98 (reviewer isolation and
orchestration), #99 (`local_commit`), and #100 (`update_pr`). Do not invoke it
expecting a complete, end-to-end review-fix loop yet; use it to validate a
document you or a later child produced against the shared schemas, or to acquire
a lock, run an isolated attempt, and recover an interrupted one.

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
remaining fix cycles from a checkpoint's recorded attempts),
`validate_checkpoint_against_invocation` (confirm a checkpoint's initial head,
original base, cycle budget, invocation ID, repository, and publication policy
match the invocation it derives from), and
`validate_terminal_against_checkpoint` (confirm a terminal result's budget and
head/base identities match the checkpoint it derives from). See
[`references/CONTRACT.md`](references/CONTRACT.md) for the cross-field semantics
these functions enforce beyond plain JSON Schema, and
`scripts/tests/test_validate.py` for the complete valid, invalid, boundary, and
round-trip case coverage.

## Local execution

`scripts/local_execution.py` is dependency-free and loads `scripts/validate.py`
from this same directory via `importlib` rather than duplicating any schema or
cross-field check, so a caller always resumes and promotes against the exact
contract `references/CONTRACT.md` defines. It implements the parts of
`design/review-fix-loop.md`'s "Local ownership and checkpointing" section this
repository can exercise without a reviewer or a selected fix:

- `acquire_candidate_locks` — the non-blocking, common-Git-common-directory
  local-ref lock plus the optional `update_pr` remote-target lock, acquired in
  that fixed order and released in reverse, so conflicting local invocations can
  never both own the same target and lock ordering cannot self-deadlock.
- `write_checkpoint_atomic`, `read_checkpoint`, and
  `reconcile_checkpoint_for_resume` — durable, schema-validated checkpoint
  persistence and the complete design-required resume precondition set (no
  active lock holder, matching cross-document identity, a clean candidate, and
  live head/base agreement).
- `create_attempt`, `commit_attempt`, `promote_attempt`, `discard_attempt`, and
  `cleanup_attempt` — an isolated attempt worktree and branch created from the
  exact canonical head, a verified fast-forward-only promotion that leaves the
  canonical candidate untouched on any failure, and cleanup that only ever acts
  on the `review-fix-loop/attempt/` namespace it created.
- `recover_interrupted_attempts` — reconciles attempt branches an interrupted
  invocation left behind against a checkpoint's own history, returning each
  uniquely identifiable leftover for the caller to retry or discard, and raising
  rather than guessing when reconciliation is ambiguous.

See the module's own docstrings and
[`scripts/tests/test_local_execution.py`](scripts/tests/test_local_execution.py)
for the complete contention, interruption, stale-state, dirty-worktree,
promotion-race, and cleanup-safety coverage. Selecting which finding to fix,
writing the fix's content, running a reviewer, and publishing to a remote remain
out of scope here; a caller supplies the fix content and invokes these
primitives around it.

## Non-goals

- Running a reviewer, or selecting or writing a fix's content.
- Publishing anything, including the `update_pr` expected-old fast-forward
  update.
- Migrating `implement-ticket`, `babysit-pr`, `carve-changesets`, or any other
  existing caller.
- Owning acceptance criteria or a caller-specific acceptance ledger — the
  contract records `acceptance_reconciliation_required` but the caller always
  retains its own ledger.
