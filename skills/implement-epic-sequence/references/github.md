# GitHub execution adapter

Use GitHub independently as an issue tracker, a PR host, or both. Apply only the
sections owned by its role in the current run.

## Contents

- [Ownership boundary](#ownership-boundary)
- [PR-host preflight](#pr-host-preflight)
- [GitHub-tracker preflight](#github-tracker-preflight)
- [Selecting work when GitHub owns issue state](#selecting-work-when-github-owns-issue-state)
- [PR contract](#pr-contract)
- [Review state](#review-state)
- [Checks and merge](#checks-and-merge)
- [Epic closeout when GitHub owns issue state](#epic-closeout-when-github-owns-issue-state)

## Ownership boundary

- When GitHub owns issue state, use the GitHub-tracker preflight, selection,
  issue-closing syntax, dependency refresh, and epic closeout sections.
- Whenever GitHub hosts PRs, use the PR-host preflight, PR contract, review,
  checks, merge, and branch-handling sections.
- When Linear owns issue state and GitHub hosts PRs, route all parent, child,
  blocker, status, and closeout decisions through `linear.md`. Do not inspect or
  mutate same-numbered GitHub issues as substitutes.

## PR-host preflight

- Resolve the repository from the request or current checkout.
- Confirm GitHub authentication.
- Inspect open and merged PRs that reference the candidate tracker ticket.
- Confirm local branch and worktree topology before creating implementation
  state.
- When connector review is required, record the connector identity, automatic or
  request-driven mode, exact initiation action, per-push policy, expected
  run-start evidence, and accepted clean signal. Derive this contract from
  repository instructions, configuration, or verified recent PR behavior.

Fail closed before connector polling when its identity, initiation contract, or
required current-candidate signal cannot be discovered.

## GitHub-tracker preflight

Run this section only when GitHub owns issue state.

- Read the epic body, labels, state, and comments when they affect scope.
- Read native `parent`, `subIssues`, `blockedBy`, and `blocking` relationships
  through GraphQL or an equivalent structured GitHub tool.

Do not derive ownership or ordering from issue title, issue number, Markdown
task lists, or prose dependency notes when native relationships exist.

## Selecting work when GitHub owns issue state

Choose an open child whose native `blockedBy` set contains no open issue. Verify
every required closed-blocker outcome in its authoritative repository, artifact
registry, tracker, or environment. For same-repository code, verify the result
on the base. For cross-repository or operational prerequisites, also verify that
the consumer uses the required contract, version, configuration, approval, or
environment state. Treat a canceled or not-planned blocker with an unmet outcome
as unresolved.

Check that no open or merged PR already represents the child. When duplicate
branches or PRs exist, compare their actual patches or resulting trees and
retain one canonical path.

Read the graph again after every merge because closing one child can unblock
work in another epic.

## PR contract

- Use one tracker child per branch and PR.
- When GitHub owns issue state, use the repository's closing syntax, normally
  `Fixes #<issue>`.
- When another tracker owns issue state, use its required reference and avoid
  GitHub issue-closing syntax unless a real GitHub issue is intentionally in
  scope.
- Describe the branch as a whole rather than the latest commit.
- Preserve explicit ticket non-goals in the PR when scope pressure is likely.
- Confirm the PR base and head match the intended worktree.

Use file-based PR bodies when shell interpolation could alter Markdown.

## Review state

Capture the exact PR head and base SHAs before evaluating review state. Read
ordinary PR conversation, formal reviews, and inline review threads; use GraphQL
or an equivalent thread-aware API when flat PR output does not expose thread
resolution.

For required human review, record the reviewer, review state, reviewed commit
OID, submission time, and base SHA observed when the review arrives. Require its
reviewed commit to equal the current head. After a base advance, apply the
generic base-drift gate: retain approval only when the effective candidate is
unchanged and repository policy permits it; otherwise request fresh approval.
When the host cannot bind a required fresh approval to an unchanged head plus a
new base, update the branch so the candidate has a new reviewable head.

When the repository uses a connector bot, use the identity, initiation mode, and
clean signal recorded during PR-host preflight. Accept a clean result only when
all of these conditions hold:

- the evidence comes from that configured connector identity;
- it is an explicit clean verdict represented by one of these forms:
  - a formal review whose commit OID equals the captured SHA;
  - a conversation comment that names the captured SHA;
  - the configured clean reaction on a request or result that names the captured
    SHA; or
  - a configured PR-object thumbs-up from the connector bot that appeared as the
    completion signal for the connector run on the captured SHA;
- the PR head still equals the captured SHA; and
- any base advance has passed the generic base-drift gate and the connector
  policy permits retaining its current-head signal; and
- there are zero unresolved connector-authored review threads.

For a PR-object thumbs-up, require repository evidence that this is the
configured completion signal, capture the reaction identity and timestamp or
equivalent run evidence, and prove it appeared after the connector request or
run began for the captured SHA. Never reuse a PR-object reaction that predates
the captured head or cannot be tied to its connector run.

Do not infer current-head approval from timing, comment order, a generic bot
message, CI success, or a verdict on an earlier commit. A push, rebase, conflict
resolution, or update-branch operation changes the head and invalidates all
older current-head evidence.

For every actionable conversation comment, formal review, and inline thread:

1. Verify the claim against the current code and ticket.
2. Fix it or reject it with concrete evidence.
3. Run affected and required validation.
4. Push when the code changed.
5. Reply publicly on the originating surface when possible and record the item
   identifier, disposition, and evidence.
6. Resolve an inline thread only after its disposition is complete.

Require zero undispositioned actionable items across conversation comments,
formal reviews, connector feedback, and inline threads before merge.

After a head change, capture the new head/base pair and wait for a fresh
connector verdict tied to that candidate. After base-only drift, apply the
generic drift gate and request a fresh connector verdict only when the effective
candidate changed, relevant overlap exists, or connector/repository policy
requires it. Trigger the configured connector when review is request-driven.
When review is automatic, record evidence that a run began for the captured
candidate after it was pushed or rebuilt. Do not accept a required fresh verdict
until its review request or automatic run is tied to that candidate.

Resolve the connector polling window and interval from repository instructions.
When none is configured, state and use a 30-minute window with a 30-to-60-second
polling interval. Start the window when the review request is sent or, for an
automatic connector, when the head is pushed. During every poll, re-read the
head and base SHAs, run-start evidence, required checks, conversation comments,
formal reviews, reactions, and review threads.

If no automatic run begins or no valid current-head signal arrives within the
window, stop and report the missing gate. Keep the PR and epic open; never infer
approval from green CI or zero unresolved threads. Re-read the conversation,
formal reviews, review threads, reactions, head and base SHAs, and checks
immediately before merge.

Use at most three connector feedback passes per PR by default, including the
initial review and re-reviews after fixes. A review repeated only because the
candidate identity changed without producing feedback does not consume this
feedback budget. If the final allowed pass still reports a material in-scope
finding, keep the PR and epic open, report the remaining finding, and request
direction. Do not spend connector passes on feedback already classified as
incorrect, outside scope, polish, or hypothetical hardening.

## Checks and merge

- Read required GitHub Actions checks directly.
- Continue monitoring pending required checks; ordinary check execution is not a
  blocker requiring user input.
- Inspect failed required checks and their logs. Distinguish an in-scope
  regression from an infrastructure, dependency, or external-service failure.
- Fix only demonstrated in-scope failures, rerun affected and required local
  validation, push the fix, and restart every current-head connector and check
  gate.
- Report unavailable external checks without weakening or bypassing the gate.
- If the repository has no branch checks, state that explicitly and use the
  documented local and review gates.
- Immediately before merge, re-read the base SHA. If it differs from the
  comparison base, build or inspect an up-to-date merge candidate and apply the
  generic base-drift gate. Record why each signal is retained or rerun every
  affected local validation, CI, local review, human review, connector review,
  and feedback disposition. When a review system cannot bind required fresh
  evidence to an unchanged head plus a new base, update the branch so the new
  candidate has a reviewable head SHA.
- Use the repository's approved merge method.
- If local worktree ownership prevents the CLI from switching to the base
  branch, merge through GitHub's API and perform local cleanup separately.

After merge, verify PR state, merge commit or squash result, and base-branch
content before deleting the branch. Verify issue transition or closure through
the adapter for the owning tracker; do not assume GitHub owns it.

## Epic closeout when GitHub owns issue state

Read back native relationships. Close the epic only when required sub-issues are
closed, no blocker remains, every required closed-blocker outcome is satisfied,
and epic-level behavior is verified. Do not infer completion solely from merged
PR count or a canceled/not-planned issue state.
