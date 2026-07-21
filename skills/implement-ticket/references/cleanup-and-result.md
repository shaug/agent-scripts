# Cleanup and terminal result

Verify remote, mainline, tracker, and local state before deleting anything or
returning a terminal handoff.

## Safe per-PR cleanup

01. Confirm the PR is merged remotely.
02. Fetch and prune the remote.
03. Confirm the branch result is represented on the verified base. Use ancestry
    first and patch equivalence after squash or rebase when needed.
04. Map the exact ticket worktree, local branch, upstream, PR branch, recorded
    PR head, and base branch. Never rely on the current directory or a
    branch-name guess.
05. Inspect tracked, staged, unstaged, untracked, and ignored state in that
    exact worktree. Classify ignored and untracked paths as reproducible output
    or non-reproducible/user-created data. Preserve credentials, `.env` files,
    local databases, and all non-reproducible artifacts.
06. Confirm the local branch has no commits absent from its pushed PR branch.
    When the remote branch is gone, compare it with the recorded PR head.
07. If the pushed branch exists, confirm it did not advance beyond the recorded
    PR head and that the recorded result is represented on the base.
08. Remove only a clean disposable worktree. Never force removal.
09. Delete only the verified merged local feature branch, then its remote
    feature branch when policy and authority permit.
10. Prune worktree metadata and verify the intended path and branches are gone.

Stop cleanup and report exact dirty paths, ignored paths, unique commits, or
branch drift when any precondition fails. Preserve unrelated worktrees,
branches, ignored files, untracked files, and user edits.

## Mainline and ticket verification

After merge, verify:

- the remote base advanced or otherwise contains the merged result;
- the implemented behavior and tests exist on the base;
- the owning tracker transitioned the ticket as expected;
- for an epic child, affected native dependency relationships were reread after
  the transition and newly unblocked work was reported without selection or
  mutation;
- no required check or review state invalidated the claimed result; and
- every performed cleanup action passed its preconditions.

Do not close a parent epic, verify whole-epic acceptance, or implement newly
unblocked work. Report newly ready work only as context.

## Result fields

Return a concise documented handoff. Do not require a machine-readable schema
unless the caller has one. Include every applicable field:

- `terminal_state`: `ready_pr`, `merged`, `blocked`, or `requires_epic`;
- ticket identity, tracker, repository, PR host, and base identity;
- branch, worktree, candidate head, and PR identity when created;
- completion policy and the authority actually used;
- focused and full validation commands, outcomes, and limitations;
- initial `review-code-change` verdict and reviewed candidate identity;
- `babysit-pr` policy, terminal state, returned candidate identity, authority
  used, mutation ownership, and independently verified live-state match;
- applicable CI, human, connector, comment, formal-review, and thread state;
- merge, mainline, ticket transition, and cleanup state;
- deferred findings and intentionally unperformed work; and
- one concrete next action or blocking reason.

For `ready_pr`, require a verified `babysit-pr: ready_to_merge` result for the
still-current open and mergeable PR. Every applicable non-merge gate must pass;
the only withheld action is merge. Do not list ordinary pending CI or review as
a remaining gate on a terminal `ready_pr`.

For `merged`, require a verified `babysit-pr: merged` result plus the
independent mainline, tracker-transition, dependency-refresh, and cleanup checks
above. A `closed` babysitter result becomes `blocked` with
`PR closed without merge` and preserves local artifacts unless another canonical
completion is proven.

For `requires_epic`, require all of:

- no branch, worktree, ticket, or PR mutation occurred;
- `target_skill` is `implement-epic`;
- the resolved tracker, repository, ticket, native type, and sub-issue evidence;
- stable marker `implement-ticket:requires-epic:<tracker>:<ticket-id>`; and
- an explicit missing-skill limitation when `implement-epic` is unavailable.

If the incoming handoff already contains the same marker, return `blocked` with
`routing cycle detected` rather than another `requires_epic` result.
