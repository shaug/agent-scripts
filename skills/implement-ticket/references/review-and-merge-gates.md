# Initial review and delegation gates

Apply these gates to the complete initial ticket candidate. Repository
instructions may add stricter requirements but must not silently weaken them.
After review, select exactly one publication path. Delegate an ordinary PR's
continuing lifecycle to repository-owned `babysit-pr`, or delegate an oversized
candidate's entire stacked lifecycle to repository-owned `carve-changesets`. Do
not duplicate either delegate's mechanics here.

## Initial bounded review loop

Require repository-owned `review-code-change` before the publication size gate.
Fail closed when it is missing or unreadable. Do not substitute another skill, a
generic self-review, or an unreviewed path.

Read the bundled review-result contract at
[references/review-suite/CONTRACT.md](review-suite/CONTRACT.md) and the schema
beside it. Before consuming any returned result, validate it with
`references/review-suite/validate.py` or the stricter bundled
`scripts/review_gate.py`, which also binds the result to this run's exact
current head and comparison-base SHA. Reject a result that fails schema
validation, carries a `schema_version` other than the bundled contract's current
version (`1.4`; a stale version such as `1.0`, `1.1`, `1.2`, or `1.3` fails with
its own migration message and is never accepted as current evidence), is not an
`aggregate` result, has a `verdict` other than `clean`, or is missing a
complete, current, freshly executed `lens_executions` entry for every required
lens. Treat any such rejection, exactly like a missing dependency or a `blocked`
verdict, as a failed initial review; never publish or advance the publication
gate on that evidence. A schema-valid `clean` aggregate already bound to the
current head and base with complete fresh lens executions needs no additional
invented review cycle.

Require every intended ticket change to be committed and the implementation
worktree to be clean before review. If unrelated user artifacts prevent a clean
state, classify and preserve them and prove they are irrelevant to the
candidate.

Before delegation, capture HEAD, comparison base, commit history, and tracked,
staged, unstaged, untracked, and ignored state. Invoke `review-code-change` in a
fresh or minimally inherited read-only context with:

- the live ticket, every acceptance criterion, and every required verification
  item classified as pre-merge or post-merge;
- the criterion-specific acceptance ledger with required evidence category,
  current SHA/environment, source, and status;
- every named architecture, design, contract, migration, and rollout document;
- repository instructions and representative nearby code and tests;
- the exact captured head and comparison-base SHAs plus the location of a file
  holding the complete `base...HEAD` diff; and
- exact focused and full validation evidence, including unavailable checks.

Write that diff file to a temporary directory outside the ticket worktree and
hand over its path, not the diff text. Writing it inside the worktree would show
up as a candidate mutation in the integrity check below, and inlining it spends
the reviewer's context on an artifact it can read for itself.

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
commit the new head, rebuild the raw evidence packet, and follow the returned
re-review instruction. Push only after the publication path is selected. Use at
most three full fix/re-review cycles by default. A clean aggregate ends the
initial loop. If material findings remain after the final cycle, preserve the
candidate and return `blocked` with unresolved evidence.

## Publication and delegation gate

Before invoking either delegate:

- verify the initial review is clean for the exact live head and applicable
  base;
- verify every required pre-merge acceptance entry passes and choose closing or
  non-closing tracker syntax from whether post-merge entries exist;
- evaluate the exact candidate against the live `carve-changesets` guardrails
  without duplicating their thresholds;
- verify the selected single-PR or stack identity, effective diff, resulting
  tree, validation, worktree, ticket reference, and authority are internally
  consistent;
- assemble every field required by the applicable
  [babysit-pr](babysit-pr-handoff.md) or
  [carve-changesets](carve-changesets-handoff.md) handoff contract;
- map the completion policy without broadening merge, deployment, verification,
  or tracker-transition authority; and
- establish one exclusive mutating owner.

Treat a missing dependency, malformed result, `blocked` verdict, reviewer
mutation, stale identity, or unavailable required evidence as a failed gate. Do
not claim `ready_pr` or `ready_prs` merely because a PR or stack exists or an
initial review is clean.

## Caller-side completion verification

After the selected delegate returns, reread live GitHub state and apply the
applicable [babysit-pr](babysit-pr-handoff.md) or
[carve-changesets](carve-changesets-handoff.md) result mapping. A `ready_pr`
requires a validated current `ready_to_merge` result plus passing required
pre-merge acceptance evidence. A `ready_prs` requires a validated current
`prs_open` result plus the same evidence. A `merged` result requires independent
remote merge or `all_merged`, mainline, complete current acceptance evidence,
tracker transition, dependency refresh, and cleanup verification by
`implement-ticket`.

If the live head, base, PR state, ownership, acceptance ledger, or gate evidence
differs from the result, reconcile the live candidate or fail closed. Never
carry stale evidence through a head/deployment change or accept a closed issue,
merged PR, or closed-unmerged PR as acceptance proof.

## Findings that must not expand the ticket

Keep these out unless the live ticket requires them:

- speculative pre-release backfills;
- support for nonexistent legacy data;
- broad refactors unrelated to correctness;
- defensive abstraction without demonstrated duplication;
- product polish or future hardening; and
- changes owned by a sibling or parent epic.
