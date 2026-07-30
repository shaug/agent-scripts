---
name: review-fix-loop
description: Validate the review-fix-loop invocation, checkpoint, and terminal-result contracts; run the complete-review orchestration that later children of epic #95 build a fix loop on top of; and provide the local execution substrate (common-directory locking, isolated attempt worktrees, durable checkpoint persistence, verified fast-forward-only canonical promotion, and interrupted-attempt recovery). Use when authoring, resuming, or terminating a review-fix-loop invocation to check its documents against the shared schemas, when running one complete review pass (fresh reviewer subagent by default, explicit in-agent override otherwise) and recording its result, or when acquiring a candidate lock, running an isolated remediation attempt, or recovering an interrupted one. This skill does not yet select or apply a fix's content or publish anything; see design/review-fix-loop.md, references/CONTRACT.md, and references/reviewer-orchestration.md for the full behavioral design and current implementation status.
allowed-tools: Read, Grep, Glob, Bash, Agent, Task, Skill
---

# Review Fix Loop

`review-fix-loop` will become a repository-owned skill that takes cooperative
ownership of an existing committed candidate, runs the complete repository
review suite, applies material ticket-scoped fixes, and repeats until review
converges or a bounded stop condition is reached. The full design is
[`design/review-fix-loop.md`](../../design/review-fix-loop.md).

Three of its children are implemented so far:

- [Issue #96](https://github.com/shaug/agent-scripts/issues/96) (the first of
  epic [#95](https://github.com/shaug/agent-scripts/issues/95)) defines and
  validates the contracts every later child builds on:
  - the **invocation** a caller or standalone operator supplies to start or
    resume a loop;
  - the **durable checkpoint** the loop would record between phases; and
  - the **terminal result** the loop returns.
- [Issue #98](https://github.com/shaug/agent-scripts/issues/98) implements
  **reviewer isolation and complete-review orchestration**: resolving the fixed
  lens set a complete review must cover, running that review in a fresh
  read-only subagent by default (or, only through an explicit invocation
  override, in-agent), detecting an attempted reviewer mutation and failing that
  cycle closed, and normalizing findings into one deterministic order. See
  [`references/reviewer-orchestration.md`](references/reviewer-orchestration.md)
  and [`scripts/reviewer_orchestration.py`](scripts/reviewer_orchestration.py).
- [Issue #97](https://github.com/shaug/agent-scripts/issues/97) adds the local
  execution substrate those contracts describe: common-Git-common-directory
  locking, isolated attempt worktrees, durable checkpoint persistence and resume
  reconciliation, verified fast-forward-only canonical promotion, and recovery of
  an interrupted attempt. See [Local execution](#local-execution) below.

This skill still does not select or apply a fix's content, or publish
anything — those behaviors belong to #99 (`local_commit`) and #100
(`update_pr`). Do not invoke it expecting a complete, end-to-end review-fix
loop yet; use it to validate a document you or a later child produced against
the shared schemas, to run and record one complete review pass, or to acquire
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

## Run a complete review

Read
[`references/reviewer-orchestration.md`](references/reviewer-orchestration.md)
in full before running a review pass; it implements design's "Review execution"
and "Reviewer write prevention" sections and workflow step 3 ("Review"). In
summary:

1. Confirm `review-code-change` and its three lens skills are available; fail
   closed (`blocked/missing_capability`) if not.
2. Resolve this invocation's review-execution mode with
   `resolve_review_execution_mode` — `fresh_subagent` by default, or the
   invocation's explicit `in_agent_override` when authorized. There is no
   automatic fallback between them.
3. Build the raw review-code-change packet bound to the exact current head and
   comparison base, prepend `build_reviewer_briefing`'s literal prohibitions,
   and invoke `review-code-change` in a fresh subagent (or, only under the
   explicit override, in-agent) restricted to
   `Read, Grep, Glob, Bash, Agent, Task, Skill` — never a file-editing or
   remote-write tool.
4. Capture worktree state immediately before and after the pass and run
   `detect_worktree_mutation` on the two snapshots.
5. Validate the raw result with `evaluate_review_result` and build one
   `review_records` entry with `build_review_record`, feeding in every detected
   mutation. A non-empty `mutation_attempts` always yields
   `write_isolation: "violated"` and fails that cycle closed, even when the
   aggregate verdict itself looked clean.
6. When the verdict is not `clean`, use `normalize_findings` and
   `select_next_finding` to identify the next finding in one deterministic order
   — selecting a finding is not disposing or fixing it; that remains a later
   child's "Decide"/"Fix" responsibility.

`scripts/reviewer_orchestration.py` is dependency-free, matching
`scripts/validate.py`'s convention, and bundles the same
`references/review-suite/` contract copy `review-code-change` itself ships (kept
in sync via the repository's `just sync-contracts`). See
`scripts/tests/test_reviewer_orchestration.py` for complete coverage of lens
resolution, rejection of an incomplete or stale-bound result, default
fresh-reviewer selection with no automatic fallback, the explicit in-agent
override, reviewer-identity freshness, mutation detection that fails a cycle
closed, and deterministic finding normalization/selection.

## Local execution

`scripts/local_execution.py` is dependency-free and loads `scripts/validate.py`
from this same directory via `importlib` rather than duplicating any schema or
cross-field check, so a caller always resumes and promotes against the exact
contract `references/CONTRACT.md` defines. It implements the parts of
`design/review-fix-loop.md`'s "Local ownership and checkpointing" section this
repository can exercise without a selected fix:

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
writing the fix's content, and publishing to a remote remain out of scope here;
a caller supplies the fix content and invokes these primitives around it.

## Non-goals

- Deciding which finding to accept, reject, or defer, and applying the resulting
  fix (a later child's "Decide"/"Fix" workflow steps).
- Publishing anything, including the `update_pr` expected-old fast-forward
  update (issue #100).
- Migrating `implement-ticket`, `babysit-pr`, `carve-changesets`, or any other
  existing caller.
- Owning acceptance criteria or a caller-specific acceptance ledger — the
  contract records `acceptance_reconciliation_required` but the caller always
  retains its own ledger.
