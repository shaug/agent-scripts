# GitHub watcher contract

Use GitHub as the PR host. Resolve tracker state separately when another system
owns the ticket.

## Contents

- [Preflight](#preflight)
- [Watcher commands](#watcher-commands)
- [State and candidate changes](#state-and-candidate-changes)
- [Feedback surfaces](#feedback-surfaces)
- [Repository-specific connectors](#repository-specific-connectors)
- [Terminal verification](#terminal-verification)

## Preflight

- Confirm `gh` authentication and repository access.
- Resolve the PR from an explicit number/URL or an unambiguous current branch.
  Prefer passing the explicit number or URL to every watcher invocation; `auto`
  resolution is a convenience for single-PR checkouts only.
- Capture repository, number, URL, state, head repository/branch/SHA, base
  branch/SHA, mergeability, merge-state status, and review decision.
- Inspect open/merged PRs and plausible branches for a superseding candidate.
- Map the exact local branch/worktree before any mutation.
- Read repository policy for required checks, human review, connector review,
  thread handling, merge method, and communication authority.
- Record documented absence of a category; do not infer it from empty output.

When a tracker ticket is supplied, use its goal and scope but leave status,
dependency, and close mutations to the caller.

## Watcher commands

Paths are relative to this skill's root directory. Use a one-shot snapshot for
diagnosis:

```bash
python3 scripts/gh_pr_watch.py \
  --repo OWNER/REPO --pr NUMBER --once
```

Use JSONL monitoring for a persistent task:

```bash
python3 scripts/gh_pr_watch.py \
  --repo OWNER/REPO --pr NUMBER \
  --completion-policy ready_to_merge --watch
```

For runtimes with bounded foreground command windows, either run `--watch` as a
managed background task and read its incremental JSONL output, or bound each
foreground window with `--watch --max-polls <n>` or `--watch --stop-when-clear`
and re-invoke until a terminal condition is reached. `--stop-when-clear` exits
when GitHub-native gates are clear; it never asserts repository-specific gates
or feedback disposition. When no completion policy is passed it implies
`ready_to_merge`; combining it with an explicit `watch_until_closed` is
rejected. On a repository with zero configured checks the candidate is never
GitHub-clear (the watcher emits `verify_required_check_policy` instead), so pair
`--stop-when-clear` with `--max-polls` to keep the window bounded.

Watch mode tolerates a bounded number of consecutive transient GitHub CLI
failures (`--max-transient-failures`, default 5), emitting a `transient_error`
event with backoff before retrying; it still exits nonzero when the budget is
exhausted and immediately on identity failures.

Use `--state-file` when the caller needs a controlled durable location. The
default state is isolated by repository and PR in a per-user mode-0700 directory
under the operating system's temporary directory; a reboot or temp-file cleaner
may reset it, which re-surfaces already-seen feedback (safe) and resets retry
budgets (permits extra reruns). Pass `--state-file` on a durable path when retry
budgets must survive reboots. A state file whose stored repository/PR differs
from the live target fails closed.

All modes share a nonblocking lock on their repository/PR state file, including
one-shot snapshots, continuous watch, and retry mutation. Do not run a second
controller for the same state; stop the continuous watcher before running
`--once` or `--retry-failed-now`, then restart it. The controlling task must
consume watch output and terminate the process when interrupted; never leave a
detached watcher.

The watcher emits:

- exact PR/head/base identity and candidate-change flags;
- check counts (including cancelled checks) and per-check metadata;
- failed workflow runs and direct failed-job log endpoints, scoped to the runs
  backing the PR's own checks; failed head-SHA workflows that are not PR checks
  (push- or schedule-triggered) appear separately under
  `non_pr_check_failed_runs` and never gate readiness or retries;
- explicit `resolve_draft_state` and `resolve_merge_conflict` actions for draft
  and conflicting PRs;
- all published feedback, new feedback, and unresolved threads;
- retry count and remaining budget;
- mergeability/review state; and
- ordered recommended actions.

Recommendations never establish repository-specific review, connector, or
local-validation success. In particular, `verify_external_gates` asserts only
GitHub-native gates; when any published feedback exists the watcher also emits
`confirm_feedback_disposition` because it can deduplicate conversation comments
but cannot verify that the controller dispositioned them.

## State and candidate changes

Persist only operational deduplication and retry state. Write state atomically.
Never store credentials or raw job logs.

On every snapshot:

- compare live head and base with the last observed identities;
- emit head/base change flags;
- preserve retry budgets per head SHA;
- preserve seen feedback IDs while continuing to emit the complete published
  feedback and every unresolved thread; and
- remove pending review IDs from seen state so feedback surfaces after
  publication.

A head change invalidates head-bound evidence even when GitHub reports green
checks. A base-only change requires the risk-based proof in the main skill.

Use REST pagination for comments, reviews, workflow runs, and jobs. Use GraphQL
pagination for review threads because flat PR output does not reliably provide
resolution state. Treat API errors, partial data, and unknown mergeability as
unknown rather than clean.

## Feedback surfaces

Read all of:

- PR conversation comments;
- formal reviews, including their reviewed commit IDs;
- inline review comments and parent review state;
- resolved/unresolved review threads; and
- repository-documented reactions or connector signals when applicable.

Ignore reviews in `PENDING` state and inline comments belonging to them. Do not
add pending IDs to seen state. Emit all published authors rather than silently
filtering outsiders or unfamiliar bots; the controller verifies relevance and
repository trust policy.

Do not accept review cleanliness merely because no new items appeared. Use the
complete feedback and thread collections, and require zero undispositioned
actionable items.

## Repository-specific connectors

Before polling a required connector, discover and record:

- connector identity;
- automatic or request-driven initiation;
- exact initiation action and per-push policy;
- run-start evidence;
- accepted clean signal;
- candidate binding;
- polling window/interval; and
- base-drift retention policy.

Fail closed when a required contract cannot be discovered. Accept cleanliness
only from a current-head formal review, a result naming the head, a configured
reaction on a request/result naming the head, or an equivalent documented
signal. Require zero unresolved connector-authored threads.

After a head change, reinitiate or await a new signal according to repository
policy. Do not infer current approval from timing, comment order, CI success, or
a generic bot message.

## Terminal verification

For `ready_to_merge`, reread head/base, checks, reviews, comments, reactions,
threads, connector state, and mergeability immediately before returning.

For `merge_when_ready`, repeat that read immediately before merge, use the
repository-approved method, and then verify:

- PR state is merged;
- merged head/commit identity is recorded; and
- the expected candidate is represented by the remote merge.

Do not transition a tracker ticket, verify application behavior on mainline, or
delete branches/worktrees. Return those caller-owned actions explicitly.
