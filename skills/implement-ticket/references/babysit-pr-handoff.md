# Babysit PR handoff and result mapping

Use repository-owned `babysit-pr` as the sole canonical owner of an existing
GitHub PR's post-publication lifecycle. Read its live skill, references, tests,
evaluations, and result contract before delegation. If its delivered contract
differs materially from this boundary, stop and reconcile ownership rather than
copying lifecycle mechanics into `implement-ticket`.

This reference applies only to the ordinary single-PR publication path. When the
size gate selects a carved stack, use
[the carve-changesets handoff](carve-changesets-handoff.md) and perform no
direct `babysit-pr` handoff from `implement-ticket`.

## Responsibility boundary

`implement-ticket` retains ticket resolution and readiness, epic routing,
exclusive implementation state, the initial implementation and validation, PR
publication, the initial `review-code-change` loop, handoff verification,
terminal-result validation, post-merge mainline and tracker verification,
dependency refresh, cleanup, and final reporting.

After handoff, `babysit-pr` owns current PR head/base resolution, CI and failed
job diagnosis, bounded eligible retries, all published feedback surfaces,
ticket-scoped PR fixes, post-fix validation and fresh `review-code-change`,
external head changes, base drift, current-candidate human and connector gates,
mergeability, and optional merge. It returns responsibility before tracker
transition, mainline behavior verification, dependency refresh, or cleanup.

Do not reproduce those mechanics in this skill. Retain only caller-side policy,
handoff construction, result validation, and post-merge work.

## Pre-mutation dependency gate

Every successful ticket run publishes at least one PR that must be reconciled.
Verify `babysit-pr` and `review-code-change` by stable repository-owned name
before creating a branch or worktree. Missing `babysit-pr` returns `blocked`
before mutation; never download an external implementation at runtime, restore a
private copy of the old PR loop, or publish a PR that no owner will monitor.

Whole-epic routing still happens before dependency invocation and returns
`requires_epic` without creating implementation state.

## Exclusive mutation ownership

Skill composition does not imply concurrent mutation. The same exclusive
implementation context may follow `babysit-pr` directly. If another worker or
equivalent context runs it, transfer ownership explicitly and prove the caller
has stopped mutating. Provide the exact repository, PR, branch, worktree, head,
base, scope, and authority. Do not resume mutation until that worker returns or
ownership is explicitly reclaimed and live state is reverified.

Read-only monitoring may coexist, but it cannot claim the candidate as this
run's `ready_pr`. `review-code-change` always runs in a separate fresh read-only
context and receives raw evidence rather than implementation or babysitting
conclusions.

## Verified handoff

Immediately before delegation, reread the live PR and verify all of:

- ticket identity, owning tracker, observable goal, acceptance criteria,
  non-goals, and allowed fix scope;
- repository instructions and named architecture, design, contract, migration,
  and rollout documents;
- GitHub repository and PR identity;
- feature branch, worktree, exact head SHA, base branch, exact base SHA,
  effective diff, resulting tree, and commit history;
- tracked, staged, unstaged, untracked, and ignored worktree state;
- focused and full validation commands, outcomes, and limitations;
- initial `review-code-change` verdict, reviewed head/base, and integrity
  evidence;
- required CI, human, connector, comment, formal-review, reaction, and thread
  gates, including documented absence;
- connector identity, initiation procedure, accepted clean signal, candidate
  binding, polling policy, and retention rules when applicable;
- mapped completion policy, retry budget, and review-cycle budget;
- mutation, push, retry, reply, resolution, draft/ready transition, merge, and
  branch-deletion authorities;
- exclusive mutation ownership or read-only status; and
- correct tracker reference or closing behavior and the transition expected on
  merge.

The babysitter must reject stale or conflicting repository, PR, head, base,
branch, worktree, scope, or ownership identity. Use this documented shape
without adding a larger mandatory schema unless tests demonstrate a need.

## Policy and authority mapping

- `ready PR only` invokes `babysit-pr` with `ready_to_merge`; merge authority is
  withheld.
- `merge after gates` invokes it with `merge_when_ready` and passes merge
  authority.
- `merge plus manual transition` also uses `merge_when_ready`; the separately
  authorized manual transition stays with `implement-ticket` after merge
  verification.
- Normal ticket execution never uses `watch_until_closed`.

Pass authority through without expansion. Ready-PR authority permits babysitting
to readiness and evidence-based ticket-scoped repair, but not merge. Merge
authority does not imply human-authored communication, tracker mutation, branch
deletion, deployment, production mutation, or parent closure. Preserve stricter
repository communication and thread-resolution rules.

## Candidate and review integrity

The supplied initial review is reusable only for its exact head and applicable
base. A babysitter-authored or external head change invalidates head-bound
evidence. `babysit-pr` must then run affected and required validation, commit
and push any authorized fix, invoke fresh repository-owned `review-code-change`
with raw current evidence, and rebuild every invalidated remote gate.

Never pass expected findings, implementation transcripts, or prior reviewer
conclusions into a fresh review. A missing, malformed, stale, blocked, or
materially unresolved review cannot satisfy readiness.

## Terminal result mapping

Reread live GitHub state and validate the returned repository, PR, head, base,
branch/worktree, policy, ownership, validation, review, CI, feedback, gate, and
merge evidence before mapping:

- `ready_to_merge` maps to `ready_pr` only when the exact PR remains open and
  mergeable, every applicable current-candidate non-merge gate passes, merge was
  withheld, and ownership is consistent.
- `merged` maps to `merged` only after independent remote merge, mainline
  representation, tracker transition, dependency refresh, and cleanup checks.
- `closed` maps to `blocked` with `PR closed without merge`; preserve local
  artifacts unless another canonical merged implementation is independently
  proven complete.
- `blocked` maps to `blocked` with the concrete blocker, current candidate,
  partial evidence, and next action.

If any identity or evidence is stale, malformed, or conflicts with live state,
fail closed and reconcile it. Never translate a stale green snapshot into
`ready_pr` or `merged`. Resume by rereading the existing PR and durable watcher
state so feedback, retries, commits, replies, and merge attempts are not
duplicated.

## Forward evaluation integrity

Exercise this composition with raw live-shaped ticket, repository-instruction,
PR, diff, resulting-tree, check, review, comment, thread, and worktree
artifacts. Exclude implementation transcripts, intended fixes, expected outputs,
suspected findings, and prior conclusions. Treat contaminated evidence as
invalid and rerun the evaluation with a fresh isolated reviewer or worker
context.
