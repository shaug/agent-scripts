# Review and merge gates

Apply these gates to the single ticket candidate. Repository instructions may
add stricter requirements but must not silently weaken them.

## Contents

- [Bounded review loop](#bounded-review-loop)
- [Revalidation](#revalidation)
- [Base-drift gate](#base-drift-gate)
- [Merge gate](#merge-gate)
- [Feedback that must not expand the PR](#feedback-that-must-not-expand-the-pr)

## Bounded review loop

Require the repository-owned `review-code-change` skill before a merge-inclusive
run. Fail closed when it is missing or unreadable. Do not substitute another
skill, a generic self-review, or an unreviewed merge path.

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

After a material fix, run affected and required validation, commit and push the
new head, rebuild the evidence packet, and follow the returned re-review
instruction. Use at most three full fix/re-review cycles by default. A clean
aggregate ends the local loop. If material findings remain after the final
cycle, keep the PR open and return `blocked` with the unresolved evidence.

## Revalidation

After every accepted fix:

- run affected focused tests;
- rerun the repository-required gate;
- commit every intended ticket change;
- confirm `base...HEAD` contains the complete ticket implementation and no
  unexplained artifact;
- push the new head;
- capture the new head and comparison-base identities; and
- reread current-candidate check and review state.

Never carry head-bound evidence across an edit, push, rebase, conflict
resolution, or update operation that changes the head.

## Base-drift gate

Bind local review to the captured head and comparison base. Immediately before
merge, reread both identities and inspect the effective merge candidate when the
base advanced.

Retain head-bound evidence across base-only drift only when all are true:

- the effective diff and resulting tree are unchanged;
- no conflict or relevant overlap exists;
- repository policy permits retaining the evidence; and
- the reason is recorded.

Otherwise invalidate and rerun every affected local-validation, CI,
repository-owned-review, human-review, connector-review, and
feedback-disposition gate. Any rebase, merge, conflict resolution, or update
that changes the head restarts all head-bound gates.

## Merge gate

Require every applicable condition:

- every intended ticket change is committed and represented by the candidate
  diff, with unrelated artifacts classified, preserved, and proven irrelevant;
- focused and full local validation passed;
- required remote checks passed;
- the repository-owned review is clean for the current head, with later base
  drift explicitly retained or re-reviewed;
- every required human and connector review is current under repository policy;
- no undispositioned actionable conversation comment, formal review, connector
  finding, or inline thread remains;
- no conflict or superseding implementation exists;
- the candidate still satisfies one ticket and its non-goals; and
- required rollout or migration prerequisites are complete.

If the repository has no CI or a category of remote review, record that fact and
use the remaining documented gates. Do not infer absence merely from an empty
first read.

## Feedback that must not expand the PR

Keep these out unless the live ticket requires them:

- speculative pre-release backfills;
- support for nonexistent legacy data;
- broad refactors unrelated to correctness;
- defensive abstraction without demonstrated duplication;
- product polish or future hardening; and
- changes owned by a sibling or parent epic.
