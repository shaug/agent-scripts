# Review and merge gates

Use these gates for every implementation PR. Repository instructions may add
stricter requirements but must not silently weaken them.

## Contents

- [Bounded review loop](#bounded-review-loop)
- [Revalidation](#revalidation)
- [Base-drift gate](#base-drift-gate)
- [Merge gate](#merge-gate)
- [Feedback that should not expand the PR](#feedback-that-should-not-expand-the-pr)

## Bounded review loop

Before a merge-inclusive run, require the repository-owned `review-code-change`
skill. Fail closed with an explicit missing-dependency result when it is not
available or readable. Do not substitute another review skill, generic
self-review, or an unreviewed merge path.

After implementation and required local validation, invoke the suite in a fresh
or minimally inherited read-only context containing only raw task artifacts.
Exclude the implementation transcript, intended solution, prior conclusions, and
suspected findings.

Before review, require every intended ticket change to be committed and the
implementation worktree to be clean. If unrelated user artifacts prevent a clean
state, classify and preserve them and prove they are irrelevant to the
candidate.

Before delegation, capture HEAD, commit history, and tracked, untracked, and
ignored worktree state. After the reviewer returns, verify that all remain
unchanged. Treat any mutation as an integrity failure, inspect it, and preserve
user work rather than resetting or deleting it.

Give the suite:

- the live ticket and acceptance criteria;
- every named architecture, design, contract, migration, and rollout document;
- the exact captured head and comparison-base SHAs and their complete
  `base...HEAD` diff, not only the latest commit; and
- exact focused and full validation evidence, including unavailable checks.

Validate and consume the aggregate result according to the suite's shared
contract. Do not restate or override lens ordering, severity semantics,
deduplication, or correctness-versus-simplicity rules here. Apply only blocking
and strong-recommendation findings that are material, tractable, and
ticket-scoped. Preserve deferred findings without expanding the current PR.
Reply with evidence for findings that no longer apply. When authorized, create a
focused follow-up only for a real, evidenced gap outside active scope.

After a material fix, run affected and required validation, commit and push the
new head, rebuild the packet, and invoke the suite according to its returned
re-review instructions. Use at most three full fix/re-review cycles by default.
A clean aggregate ends the local loop. If the final cycle still reports a
material finding, keep the PR open and report the unresolved evidence. Do not
spend cycles on deferred findings.

## Revalidation

After every fix cycle:

- run affected focused tests;
- rerun the repository-required gate;
- commit every intended ticket change and confirm that no uncommitted ticket
  work is absent from `base...HEAD`;
- push the updated head;
- capture the current head and comparison-base SHAs;
- re-read current-candidate review and check state.

Do not carry older head-bound evidence across an edit, push, rebase, conflict
resolution, or update-branch operation that changes the head. A base advance
uses the separate drift gate below.

## Base-drift gate

Bind local review evidence to the captured head. Immediately before merge,
re-read the head and base and inspect the effective merge candidate when the
base advanced.

Retain head-bound evidence across base-only drift only when the effective diff
and resulting tree are unchanged, no conflict exists, no relevant base code
overlaps the candidate, repository policy permits retention, and the reason is
recorded. Otherwise invalidate and rerun each affected local-validation, CI,
local-review, human-review, connector-review, and feedback-disposition gate.
Repository policy may require a complete reset even for unrelated drift. Any
rebase, merge, conflict resolution, or update that changes the head restarts
every head-bound gate.

## Merge gate

Require all applicable conditions:

- every intended ticket change is committed and represented by the candidate
  diff, with any unrelated artifacts classified, preserved, and proven
  irrelevant;
- local focused and full validation passed;
- required remote checks passed;
- no undispositioned actionable conversation comment, formal review, connector
  feedback, or review thread remains;
- the repository-owned local review has a clean aggregate bound to the current
  head, with any later base drift explicitly retained or re-reviewed;
- every applicable required human and connector review is current under
  repository policy;
- no merge conflict or superseding PR exists;
- the diff still satisfies one ticket and its non-goals;
- rollout or migration prerequisites required before merge are complete.

CI success alone is not a clean review. A stale approval alone is not a clean
review. If the repository has no CI, record that fact and require its documented
local and review signals.

## Feedback that should not expand the PR

Keep these out unless the live ticket requires them:

- speculative pre-release backfills;
- support for nonexistent legacy data;
- broad refactors unrelated to correctness;
- defensive abstraction without demonstrated duplication;
- product polish or future-hardening suggestions;
- changes owned by another epic.
