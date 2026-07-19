# Linear execution adapter

Use live Linear issue relationships and current repository evidence to execute
epics whose planning source lives in Linear.

## Preflight

- Read the parent or epic and its current project context.
- List current children and inspect explicit blocking relationships.
- Read linked design documents, comments, and prior implementation PRs when they
  affect scope.
- Search for completed, canceled, duplicate, or superseding issues before
  selecting work.
- Resolve the code repository and its local instructions independently from
  Linear.

Do not use list order, priority labels, or an old prompt as dependency order
when explicit relations are available.

## Selecting work

Select an open child with no unresolved blocker and one PR-sized outcome. Verify
every required outcome from a completed, canceled, or superseded blocker in its
authoritative repository, artifact registry, tracker, or environment. For
same-repository code, verify the result on the base. For cross-repository or
operational prerequisites, also verify that the consumer uses the required
contract, version, configuration, approval, or environment state. Treat a
canceled or not-planned blocker with an unmet outcome as unresolved. Confirm
that the child is not already represented by a merged or open PR. Re-read the
parent after every merge or status transition because sibling readiness may have
changed.

If Linear's relationship model cannot express a required dependency, record the
limitation in the issue and execution report. Do not silently treat prose as
equivalent to a native blocker.

## Scope and PR linkage

- Treat the live Linear issue body as the child scope contract.
- Preserve exact product rules such as timing, timezone, idempotency, skip,
  unavailable, and migration behavior.
- Use the repository's required Linear reference in the branch, commit, and PR
  body.
- Keep one child per PR unless the user explicitly changes the decomposition.
- Update Linear status only when the corresponding workflow state has actually
  been reached.

## Closeout

After merge, verify the code is represented on the base branch and update the
child according to the team's Linear workflow. Close the parent only after all
required children, required closed-blocker outcomes, and parent-level acceptance
criteria are satisfied. Preserve explicitly deferred or canceled scope in the
final report; do not count an unmet canceled outcome as complete.
