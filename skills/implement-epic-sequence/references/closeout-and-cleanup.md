# Closeout and cleanup

Verify remote and mainline state before deleting anything or closing a parent.

## Per-PR cleanup

01. Confirm the PR is merged remotely.
02. Fetch and prune the remote.
03. Confirm the branch's result is represented on the base branch.
04. Use ancestry first; use patch equivalence after squash or rebase when
    ancestry is unavailable.
05. Map the exact disposable worktree, local branch, upstream branch, PR branch,
    and base branch. Do not rely on the current directory or a branch-name
    guess.
06. Inspect tracked, staged, unstaged, untracked, and ignored state in that
    exact worktree. Always inventory ignored files, even when ordinary status is
    clean. Classify ignored and untracked paths as reproducible generated output
    or non-reproducible/user-created data. Stop or preserve `.env` files,
    credentials, local databases, and every other non-reproducible artifact.
07. Confirm the local branch has no commits absent from its pushed PR branch.
    When the remote branch no longer exists, compare the local tip with the PR's
    recorded merged head.
08. When the pushed PR branch still exists, confirm it did not advance beyond
    the recorded merged head. Confirm the merged-head result is fully
    represented on the verified base by ancestry or patch equivalence. Stop if
    either branch check fails.
09. If the local branch is checked out, remove the clean disposable worktree or
    detach it before deleting the branch. Never force worktree removal.
10. Delete only the verified local feature branch, then its remote feature
    branch when it still exists and repository policy permits deletion.
11. Prune worktree metadata and verify that the old path, local branch, and
    remote branch are gone.
12. Preserve unrelated worktrees, branches, ignored and untracked files, and
    user edits.

If another worktree owns the base branch, update or merge from that checkout or
use the remote API. Do not force branch ownership changes. If cleanup
preconditions fail, report the exact dirty, ignored, or untracked paths or
unique commits and leave the worktree and branches intact.

## Mainline verification

After every merge, verify:

- the remote base advanced as expected;
- the merged behavior and tests exist on the base;
- the child ticket closed or transitioned correctly;
- no required check or review state changed after merge;
- the next dependency graph read uses current remote state.

Separate environment failures from regressions when validating a clean mainline.
Bootstrap documented dependencies and services before modifying code.

## Late-feedback sweep

Before closing an epic, inspect every merged PR in scope again. Read ordinary
conversation comments and thread-aware review state, including connector
comments or threads posted after merge.

Classify late findings with the same rules used during active review and record
the disposition of each one. When a late finding exposes a required correctness,
security, acceptance, architecture, or validation gap:

- keep the epic open;
- create or use an in-scope follow-up ticket when ticket mutation is authorized;
- implement the fix from a fresh branch based on the current remote base;
- never reopen, reuse, or edit the merged feature branch as the implementation
  path; and
- pass the normal validation, review, merge, and cleanup gates.

Do not close the epic until every late comment and review thread has a recorded
disposition and every blocking finding is resolved on the base branch.

## Epic closeout

Before closing an epic:

- read the live child and blocker graph;
- confirm every required child disposition;
- confirm every required PR is merged and represented on the base;
- verify epic acceptance criteria against resulting behavior;
- run required clean-main validation;
- complete the mandatory late-feedback sweep for every merged PR;
- perform any required candidate smoke check, migration, documentation,
  compatibility, or cleanup work;
- confirm no not-planned child leaves an unsatisfied outcome.

Close each epic separately. For a series, close the umbrella only after every
required epic passes the same check. A nearly complete graph is not complete.

## Final report

Record:

- merged PRs and their tickets;
- validation and current-head review evidence;
- branch and worktree cleanup results;
- closed, deferred, canceled, or blocked children;
- remaining critical-path and parallel-ready work;
- the exact reason any epic remains open.
