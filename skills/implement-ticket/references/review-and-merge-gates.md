# Initial review and delegation gates

Apply these gates to the complete initial ticket candidate. Repository
instructions may add stricter requirements but must not silently weaken them.
Delegate the published PR's continuing lifecycle to repository-owned
`babysit-pr`; do not duplicate its CI, feedback, drift, post-fix review, or
merge mechanics here.

## Initial bounded review loop

Require repository-owned `review-code-change` before a PR can be handed to
`babysit-pr`. Fail closed when it is missing or unreadable. Do not substitute
another skill, a generic self-review, or an unreviewed path.

Require every intended ticket change to be committed and the implementation
worktree to be clean before review. If unrelated user artifacts prevent a clean
state, classify and preserve them and prove they are irrelevant to the
candidate.

Before delegation, capture HEAD, comparison base, commit history, and tracked,
staged, unstaged, untracked, and ignored state. Invoke `review-code-change` in a
fresh or minimally inherited read-only context with:

- the live ticket and acceptance criteria;
- every named architecture, design, contract, migration, and rollout document;
- repository instructions and representative nearby code and tests;
- the exact captured head and comparison-base SHAs plus the complete
  `base...HEAD` diff; and
- exact focused and full validation evidence, including unavailable checks.

Exclude the implementation transcript, intended solution, prior conclusions,
suspected findings, and fixture expected outputs. After review, verify that
HEAD, history, and every captured worktree-state category remain unchanged.
Treat any mutation as an integrity failure; inspect and preserve it rather than
resetting or deleting user work.

Consume the suite's validated aggregate result without restating or overriding
lens order, severity, deduplication, or correctness-versus-simplicity rules.
Apply only blocking and strong-recommendation findings that are material,
tractable, and ticket-scoped. Preserve deferred findings without expanding the
PR. Reply with evidence when a finding no longer applies.

After a material initial-review fix, run affected and required validation,
commit and push the new head, rebuild the raw evidence packet, and follow the
returned re-review instruction. Use at most three full fix/re-review cycles by
default. A clean aggregate ends the initial loop. If material findings remain
after the final cycle, keep the PR open and return `blocked` with unresolved
evidence.

## Delegation gate

Before invoking `babysit-pr`:

- verify the initial review is clean for the exact live head and applicable
  base;
- verify the PR identity, effective diff, resulting tree, validation, worktree,
  ticket reference, and authority are internally consistent;
- assemble every field required by
  [the handoff contract](babysit-pr-handoff.md);
- map the completion policy without broadening authority; and
- establish one exclusive mutating owner.

Treat a missing dependency, malformed result, `blocked` verdict, reviewer
mutation, stale identity, or unavailable required evidence as a failed gate. Do
not claim `ready_pr` merely because a PR exists or an initial review is clean.

## Caller-side completion verification

After `babysit-pr` returns, reread live GitHub state and apply the result
mapping in [the handoff contract](babysit-pr-handoff.md). A `ready_pr` requires
a validated current `ready_to_merge` result. A `merged` result requires
independent remote merge, mainline, tracker-transition, dependency-refresh, and
cleanup verification by `implement-ticket`.

If the live head, base, PR state, ownership, or gate evidence differs from the
result, reconcile the live candidate or fail closed. Never carry stale evidence
through a head change or accept a closed-unmerged PR as complete.

## Findings that must not expand the ticket

Keep these out unless the live ticket requires them:

- speculative pre-release backfills;
- support for nonexistent legacy data;
- broad refactors unrelated to correctness;
- defensive abstraction without demonstrated duplication;
- product polish or future hardening; and
- changes owned by a sibling or parent epic.
