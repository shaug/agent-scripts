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

After implementation and required local validation, require one fresh, read-only
adversarial review using `code-review-pro` in a separate review-only subagent or
equivalent isolated context unless the user explicitly waives independent review
or independent review tooling is unavailable. Use a fresh or minimally inherited
context containing only raw task artifacts. Exclude the implementation
transcript, intended answer, prior conclusions, and suspected findings. Do not
silently treat unavailability as a passed independent-review gate.

Before review, require every intended ticket change to be committed and the
implementation worktree to be clean. If unrelated user artifacts prevent a clean
state, classify and preserve them and prove they are irrelevant to the
candidate.

Before delegation, capture HEAD, commit history, and tracked, untracked, and
ignored worktree state. After the reviewer returns, verify that all remain
unchanged. Treat any mutation as an integrity failure, inspect it, and preserve
user work rather than resetting or deleting it.

Give the reviewer:

- the live ticket and acceptance criteria;
- every named architecture, design, contract, migration, and rollout document;
- the exact captured head and base SHAs and their complete `base...HEAD` diff,
  not only the latest commit; and
- exact focused and full validation evidence, including unavailable checks.

Require the reviewer to inspect correctness, acceptance coverage, regressions,
failure paths, security, authorization boundaries, architecture, public surface
area, tests, documentation, and scope. Classify each finding as:

- must fix now: correctness, security, acceptance, architecture, or validation
  failure;
- obvious low-cost correctness or safety improvement: addresses demonstrated
  current risk without widening scope;
- already satisfied or incorrect;
- valid but outside the ticket;
- blocked by a missing product decision.

Apply only the first two categories. Reply with evidence for rejected findings.
When authorized, create a focused follow-up only for a real, evidenced gap.
Apply cognitive-load refactoring only when the user explicitly requests it or
when it is necessary to make the ticket's correctness evident. Do not use
reviewer convenience alone to expand the active PR.

Run a fresh pass after material fixes so the review covers the resulting diff.
Use at most three adversarial passes by default. A clean pass ends the loop. If
the third pass still reports a material finding, do not merge; report the
remaining issue and request direction. Do not spend passes on style, polish,
hypothetical hardening, or future compatibility.

When independent review tooling is unavailable, record why, perform a fresh
adversarial self-review using the same inputs and coverage, and proceed only if
repository policy does not require independence and the user has accepted or
already authorized this fallback.

## Revalidation

After every fix cycle:

- run affected focused tests;
- rerun the repository-required gate;
- commit every intended ticket change and confirm that no uncommitted ticket
  work is absent from `base...HEAD`;
- push the updated head;
- capture the current head and base SHAs;
- re-read current-candidate review and check state.

Do not carry an older clean review signal across any head change, including a
push, rebase, conflict resolution, or update-branch operation, or across a base
advance that changes the merge candidate.

## Base-drift gate

Bind validation, CI, adversarial review, required human approval, connector
review, and feedback disposition evidence to the captured head and base SHA
pair. Immediately before merge, re-read both SHAs.

When the base changed, build an up-to-date merge candidate and rerun applicable
local validation, CI, adversarial review, human review, connector review, and
feedback disposition. For required human approval, require proof that it was
submitted for the captured pair or request fresh approval after capturing the
new pair. When rebasing, merging, conflict resolution, or update-branch changes
the head, restart every current-head gate. When a review system cannot bind a
fresh verdict to an unchanged head plus a new base, update the branch so the
candidate receives a new reviewable head SHA.

## Merge gate

Require all applicable conditions:

- every intended ticket change is committed and represented by the candidate
  diff, with any unrelated artifacts classified, preserved, and proven
  irrelevant;
- local focused and full validation passed;
- required remote checks passed;
- no undispositioned actionable conversation comment, formal review, connector
  feedback, or review thread remains;
- every applicable required adversarial, human, and connector review has a clean
  or approving verdict explicitly tied to the exact current head and base SHA
  pair;
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
