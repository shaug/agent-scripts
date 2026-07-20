---
name: implement-ticket
description: Implement exactly one standalone GitHub or Linear ticket, or one named child of a larger epic, through an isolated branch and pull request. Use when an agent should resolve live ticket and dependency context, enforce readiness and authority boundaries, implement and validate one coherent change, invoke the repository-owned review-code-change skill in a fresh read-only context, handle current-head remote gates, and optionally merge and clean up when explicitly authorized. Detect whole-epic requests before mutation and route them toward implement-epic without creating a circular skill dependency.
---

# Implement Ticket

Implement one independently reviewable ticket without selecting sibling work or
claiming a parent epic is complete. Treat live tracker and repository evidence
as execution state; use old plans or summaries only for orientation.

Treat this skill as the canonical owner of generic single-ticket readiness,
implementation, review, PR, merge, base-drift, feedback, tracker-transition,
cleanup, and terminal-reporting rules. `implement-epic` consumes this contract
for each selected child. Do not copy these rules back into epic orchestration or
create a third shared workflow abstraction.

## Load the applicable references

- Read [the GitHub adapter](references/github.md) whenever GitHub owns issue
  state or hosts the repository and pull request.
- Read [the Linear adapter](references/linear.md) whenever Linear owns ticket,
  parent, dependency, or status state.
- Always read [review and merge gates](references/review-and-merge-gates.md)
  before publishing the pull request.
- Always read [cleanup and result](references/cleanup-and-result.md) before a
  merge or terminal handoff.

For cross-system work, record which system owns issue status, dependency state,
source code, pull requests, checks, reviews, and merge. Never substitute a
same-numbered issue from the PR host for the real tracker ticket.

## Require compatible runtime capabilities

A compatible agentic runtime must be able to:

- load this skill and repository-owned skill dependencies;
- read repository instructions, tracker state, and structured relationships;
- inspect and create isolated branch/worktree state;
- edit files, run commands, commit, push, and manage PRs when authorized;
- invoke a fresh read-only reviewer worker, subagent, or equivalent isolated
  context;
- poll or wait for asynchronous CI and review gates; and
- read thread-aware PR feedback.

Stop with an explicit missing-capability result when an applicable capability is
unavailable. Product-specific discovery metadata such as `agents/openai.yaml`
may exist, but it does not constrain the operating contract or require a
particular agent product.

## Resolve the operating contract

Before mutation, discover or receive and verify:

- live ticket identity, body, state, scope-affecting comments, owning tracker,
  and relevant native relationships;
- repository, PR host, current remote base, and repository instructions;
- parent outcome, closed-prerequisite evidence, and sibling-owned contracts
  needed to understand whether this ticket can ship independently;
- named architecture, design, contract, migration, and rollout documents;
- completion policy: ready PR only, merge after gates, or merge plus manual
  ticket transition;
- whether the owning tracker's PR reference will automatically close or
  transition the ticket when merged, with that consequence stated explicitly in
  the completion policy;
- required local, CI, human, connector, thread, build, integration, and manual
  validation gates; and
- authority for ticket edits, dependency changes, follow-up creation, review
  replies and resolution, merge, branch deletion, manual ticket transitions,
  deployment, production mutation, and destructive operations.

Use this default authority matrix unless the user or repository is stricter:

- `ready PR only` permits isolated implementation, validation, commit, feature
  branch push, PR creation or update, evidence-based review replies, and
  resolution of fully addressed threads;
- `merge after gates` additionally permits merging this ticket's PR and safely
  deleting its verified merged feature branch;
- `merge plus manual transition` additionally permits the explicitly requested
  status or close transition for this ticket only;
- ticket-body edits, dependency mutations, and follow-up creation require
  explicit ticket-management authority; and
- deployment, production mutation, destructive data operations, and parent
  closure always require separate explicit authority.

Do not infer merge, issue-close, parent-close, deployment, or production
authority from words such as `implement`, `finish`, `complete`, or `end to end`.
When merge authority is unclear, stop at a ready PR.

Treat an automatic ticket transition caused by the selected closing syntax as a
disclosed consequence of authorized merge, not as an independently requested
manual transition. State that consequence before publication or merge. Do not
use automatic closing syntax when its effect conflicts with the resolved
completion policy.

For a merge-inclusive run, verify before implementation that
`review-code-change` is available and readable. It is the only local
adversarial-review dependency. Return `blocked` when it is unavailable; do not
substitute a third-party skill, generic self-review, or unreviewed merge path.

## Establish source-of-truth precedence

Use this order:

1. Current user instructions.
2. Live ticket, relationship, branch, PR, and review state.
3. Repository `AGENTS.md` and equivalent local instructions.
4. Named architecture, design, contract, migration, and rollout documents.
5. Current code and tests.
6. Prior summaries or memory.

Stop on a material conflict. Do not choose the most convenient interpretation.

## Guard whole-epic scope before mutation

Determine whether the requested item is itself an epic whose requested outcome
requires implementing a child graph. Prefer authoritative structured evidence:
native issue type, native parent/sub-issue relationships, and explicit user
scope. Labels and prose may support the decision but must not silently override
contradictory native state.

- Treat a named child of an epic as ordinary `implement-ticket` scope.
- Treat an epic with children, or an explicitly identified undecomposed epic
  requested as a whole, as `implement-epic` scope.
- Permit work directly on a parent only when the user explicitly requests a
  genuinely independent one-PR deliverable owned by that parent and the normal
  readiness gate proves it can ship without implementing children.

For whole-epic scope, stop before branch creation or any other mutation and
return `requires_epic`. Name `implement-epic`, preserve the resolved
tracker/repository context, and include the stable marker
`implement-ticket:requires-epic:<tracker>:<ticket-id>`. If the same marker is
already present in the incoming handoff, return `blocked` with a routing-cycle
reason instead of redirecting again.

Do not invoke or require `implement-epic` from this skill. The executing host or
caller may route the handoff when that skill is available. If it is unavailable,
report the missing capability explicitly without flattening the epic into one PR
or implementing children.

## Apply the ticket readiness gate

Proceed only when the selected ticket:

- is open and is not already implemented, superseded, or represented by a
  canonical open or merged PR or branch;
- has no unresolved native blocker;
- has every required closed-blocker outcome verified in its authoritative
  repository, artifact registry, tracker, or environment;
- has a clear observable goal, acceptance criteria, non-goals, preserved
  behavior, and required verification;
- contains no unresolved product, data, authorization, migration, destructive,
  or architecture decision;
- represents one coherent, independently reviewable PR; and
- can merge without exposing incomplete, misleading, or unusable behavior.

Treat a closed, canceled, or not-planned prerequisite as unresolved when its
required outcome is absent. Read parent and sibling context as evidence, not as
permission to widen scope. Return `blocked` with the missing outcome when an
unimplemented sibling is required; never absorb that sibling into this PR.

When an open canonical PR or branch already owns the ticket, return `blocked`
with its identity and require explicit ownership transfer before modifying it;
do not report another worker's candidate as this run's `ready_pr`. When a merged
PR is verified on the base and the ticket is already complete, return `merged`
with that evidence without creating new implementation state.

When ticket editing is authorized, make an unclear ticket implementation-ready
and re-read it. Otherwise stop with the missing decision rather than
improvising.

## Execute one ticket

### 1. Create exclusive implementation state

- Confirm the primary checkout and registered worktrees.
- Fetch current remote state.
- Create one feature branch and clean isolated worktree from the verified base,
  unless the current clean worktree is already the user's explicit ticket
  workspace.
- Use one ticket per branch, worktree, and PR.
- Install documented dependencies and start required local services before
  classifying missing-tool failures as feature failures.

Standalone execution may mutate the primary context. A delegated worker,
subagent, or equivalent context must own exactly one verified worktree and
feature branch exclusively. Never allow two implementation contexts to mutate
the same candidate. Preserve unrelated branches, worktrees, and user changes.

### 2. Implement only the live contract

- Read nearby code and tests before editing.
- Preserve explicit non-goals and named existing behavior.
- Follow established architecture, idioms, shared modules, and extension points.
- Add focused behavior tests with the implementation.
- Update executable contract or contributor documentation when behavior changes.
- Avoid speculative backfills, compatibility layers, abstractions, or adjacent
  ticket work for conditions not evidenced by the ticket or repository.

Apply incidental changes only for a demonstrated ticket-scoped correctness,
security, acceptance, architecture, or validation need. Defer polish, broad
refactors, hypothetical hardening, and sibling work.

### 3. Validate in layers

Discover commands from repository instructions and tooling. Run:

1. focused tests for changed behavior;
2. relevant static checks;
3. the complete required repository gate;
4. integration tests with documented real dependencies; and
5. required build, packaging, or manual checks.

Report commands and exact outcomes. Distinguish bootstrap or environment
failures from feature failures. Do not claim completion while required
validation is failing or unavailable.

### 4. Publish one focused PR

- Recheck that no PR or branch already owns the ticket.
- Commit with repository conventions and push only the feature branch.
- Describe the branch-wide outcome, important non-goals, and actual validation.
- Use the owning tracker's correct closing or reference syntax.
- Confirm the PR base and head match the ticket worktree.

Do not combine independently useful tickets in one PR.

### 5. Run bounded repository-owned review

Follow [review and merge gates](references/review-and-merge-gates.md). Keep
every mutation in the implementation context. Give `review-code-change` only raw
live ticket, repository, full diff, candidate identity, validation, and worktree
evidence in a fresh read-only context. Exclude the implementation transcript,
intended solution, prior conclusions, and suspected findings.

Apply only material ticket-scoped blocking and strong-recommendation findings.
Preserve deferred findings without expanding scope. After a fix, rerun affected
and required validation, commit and push a new head, rebuild the evidence, and
follow the suite's re-review instruction. Use at most three full fix/re-review
cycles by default.

Treat a missing dependency, malformed result, `blocked` verdict, reviewer
mutation, or unavailable required evidence as a failed local gate. The review
suite stays read-only; this skill owns accepted fixes, GitHub replies, thread
resolution, commits, pushes, merge, and cleanup within granted authority.

### 6. Apply current-candidate remote and merge gates

Do not equate CI success, stale approval, or zero threads with a clean review.
Require every applicable local, CI, human, connector, comment, formal-review,
and thread gate for the current candidate. Follow the risk-based base-drift
rules in the gate reference.

When merge is authorized and every gate passes, merge using the repository's
approved method. Verify remote merge state, mainline representation, and the
owning tracker's ticket transition before cleanup. For an epic child, reread the
affected native dependency relationships after that transition and report newly
unblocked work without selecting or mutating it. Never close or verify a parent
epic from this skill.

## Stop conditions

Stop and return `blocked` when:

- ticket scope and native relationships conflict materially;
- implementation requires an unresolved product or architecture choice;
- a prerequisite outcome, authority, credential, approval, or required
  infrastructure is missing;
- correctness would materially exceed one-ticket scope;
- review feedback requires redesigning the ticket; or
- required validation remains unavailable after documented bootstrap attempts.

Difficulty, a long test suite, ordinary CI wait time, or independently ready
sibling work is not a blocker.

## Return one terminal handoff

Follow [cleanup and result](references/cleanup-and-result.md). Return exactly
one terminal state:

- `ready_pr`: the one-ticket PR exists at the reported candidate; state every
  remaining remote or authority gate, and confirm this run owns or was
  explicitly handed ownership of the candidate;
- `merged`: the PR is verified on the base, the ticket transition is verified,
  and authorized cleanup is complete or precisely limited;
- `blocked`: give one concrete blocking reason and next action, preserving any
  partial artifacts; or
- `requires_epic`: no mutation occurred and the handoff names `implement-epic`
  with its stable routing marker.

When this ticket is an epic child, report newly unblocked downstream work after
merge but do not select or implement it. Never claim whole-epic acceptance or
close a parent.
