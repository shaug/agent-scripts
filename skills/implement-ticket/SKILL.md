---
name: implement-ticket
description: Implement, build, or fix exactly one standalone GitHub or Linear ticket or issue, or one named child of a larger epic, through an isolated candidate and either one pull request or an explicitly authorized carved stack. Use when asked to implement a ticket end to end; resolves live ticket and dependency context, enforces readiness and authority boundaries, implements and validates one coherent change, runs an initial repository-owned review, chooses the publication path from the live cognitive-load guardrails, delegates the published lifecycle, and verifies tracker, mainline, and cleanup outcomes. Detects whole-epic requests before mutation and routes them toward implement-epic without creating a circular skill dependency.
---

# Implement Ticket

Implement one independently reviewable ticket without selecting sibling work or
claiming a parent epic is complete. Treat live tracker and repository evidence
as execution state; use old plans or summaries only for orientation.

Treat this skill as the canonical owner of generic single-ticket readiness,
implementation, initial review, publication-path selection, tracker transition,
mainline verification, cleanup, and terminal reporting. Delegate a normal PR's
post-publication lifecycle to repository-owned `babysit-pr`; delegate an
oversized candidate's decomposition and stacked lifecycle to repository-owned
`carve-changesets`. `implement-epic` consumes this contract for each selected
child. Do not copy any delegated skill's rules back into epic orchestration or
create a third shared workflow abstraction.

## Load the applicable references

- Read [the GitHub adapter](references/github.md) whenever GitHub owns issue
  state or hosts the repository and pull request.
- Read [the Linear adapter](references/linear.md) whenever Linear owns ticket,
  parent, dependency, or status state.
- Always read [review and merge gates](references/review-and-merge-gates.md)
  before publishing the candidate.
- Always read [the babysit-pr handoff](references/babysit-pr-handoff.md) before
  creating implementation state and again before transferring PR ownership.
- Read [the carve-changesets handoff](references/carve-changesets-handoff.md)
  after the initial review whenever the size gate classifies the candidate as
  oversized, and again before transferring candidate ownership.
- Always read [cleanup and result](references/cleanup-and-result.md) before a
  merge or terminal handoff.

For cross-system work, record which system owns issue status, dependency state,
source code, pull requests, checks, reviews, and merge. Never substitute a
same-numbered issue from the PR host for the real tracker ticket.

## Require compatible runtime capabilities

A compatible agentic runtime must be able to:

- load `implement-ticket`, repository-owned `review-code-change`, and
  repository-owned `babysit-pr` by stable skill name or an equivalent
  repository-owned dependency mechanism;
- load repository-owned `carve-changesets` by stable name at the publication
  size gate so its live guardrails and optional handoff are available;
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
particular agent product. Terms such as worker and subagent describe possible
isolated execution roles, not required product APIs.

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
  replies and resolution, decomposition of an oversized candidate into stacked
  changesets, merge, branch deletion, manual ticket transitions, deployment,
  production mutation, and destructive operations.

Use this default authority matrix unless the user or repository is stricter:

- `ready PR only` permits isolated implementation, validation, commit, feature
  branch push, PR creation or update, evidence-based review replies, and
  resolution of fully addressed threads;
- `merge after gates` additionally permits merging this ticket's ordinary PR or
  carved stack and safely deleting its verified merged feature branches;
- `merge plus manual transition` additionally permits the explicitly requested
  status or close transition for this ticket only;
- `decompose oversized candidates into stacked changesets` permits an oversized
  but coherent ticket candidate to be transferred to `carve-changesets`; it is
  off by default and is independent of every completion policy;
- ticket-body edits, dependency mutations, and follow-up creation require
  explicit ticket-management authority; and
- deployment, production mutation, destructive data operations, and parent
  closure always require separate explicit authority.

Do not infer decomposition, merge, issue-close, parent-close, deployment, or
production authority from words such as `implement`, `finish`, `complete`, or
`end to end`. When merge authority is unclear, stop at a ready PR or ready PR
stack. When decomposition authority is absent, never silently publish an
oversized monolith or silently carve it.

Treat an automatic ticket transition caused by the selected closing syntax as a
disclosed consequence of authorized merge, not as an independently requested
manual transition. State that consequence before publication or merge. Do not
use automatic closing syntax when its effect conflicts with the resolved
completion policy.

After applying the whole-epic scope guard, and before creating a branch,
worktree, or other implementation state for a ticket, verify that both
`review-code-change` and `babysit-pr` are available and readable by stable name
or an equivalent repository-owned dependency mechanism. Return `blocked` before
mutation when either is unavailable. Do not substitute a third-party reviewer,
generic self-review, private PR loop, runtime download, or stranded unmonitored
PR path. A whole-epic `requires_epic` result occurs before these ticket-only
dependencies are invoked.

The dependency graph is deliberately acyclic. The two publication paths are
mutually exclusive:

```text
implement-epic
└── implement-ticket
    ├── review-code-change          # initial candidate review
    ├── babysit-pr                  # ordinary single-PR lifecycle
    │   └── review-code-change      # after a head-changing fix
    └── carve-changesets            # authority-gated oversized path
        ├── review-code-change      # each exact changeset
        └── babysit-pr              # each changeset PR lifecycle
            └── review-code-change  # after a head-changing fix
```

`babysit-pr` and `carve-changesets` must never invoke `implement-ticket`.
`carve-changesets` must never invoke `implement-epic`. Do not re-enter this
skill while consuming either delegated result.

## Establish source-of-truth precedence

Use this order:

1. Current user instructions.
2. Live ticket, relationship, branch, PR, and review state.
3. Repository agent instructions (`AGENTS.md`, `CLAUDE.md`, or equivalent).
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
- represents one coherent candidate that is expected to fit one reviewable PR,
  with the publication size gate reserved for implementations that turn out
  materially larger than predicted; and
- can merge without exposing incomplete, misleading, or unusable behavior.

Treat a closed, canceled, or not-planned prerequisite as unresolved when its
required outcome is absent. Read parent and sibling context as evidence, not as
permission to widen scope. Return `blocked` with the missing outcome when an
unimplemented sibling is required; never absorb that sibling into this PR.

When an open canonical PR or branch already owns the ticket, return `blocked`
with its identity and require explicit ownership transfer before modifying it;
do not report another worker's candidate as this run's `ready_pr` or
`ready_prs`. When a merged PR or stack is verified on the base and the ticket is
already complete, return `merged` with that evidence without creating new
implementation state.

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
- Use one ticket per candidate branch and worktree. Publication is either one PR
  or one carved stack; never combine another ticket into either form.
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

### 4. Run bounded repository-owned review

Follow [review and merge gates](references/review-and-merge-gates.md). Keep
every mutation in the implementation context. Give `review-code-change` only raw
live ticket, repository, full diff, candidate identity, validation, and worktree
evidence in a fresh read-only context. Exclude the implementation transcript,
intended solution, prior conclusions, and suspected findings.

Apply only material ticket-scoped blocking and strong-recommendation findings.
Preserve deferred findings without expanding scope. After a fix, rerun affected
and required validation, commit a new head, rebuild the evidence, and follow the
suite's re-review instruction. Use at most three full fix/re-review cycles by
default.

Treat a missing dependency, malformed result, `blocked` verdict, reviewer
mutation, or unavailable required evidence as a failed local gate. The review
suite stays read-only. This skill owns accepted fixes and commits during the
initial review loop, but withholds the first remote push until the publication
path is selected. Finish with every intended change committed, a clean worktree,
and a clean review bound to the exact candidate and base.

### 5. Choose exactly one publication path

After the candidate is complete, validated, committed, clean, and review-clean,
load `carve-changesets` by stable repository-owned name and read its live
normative cognitive-load guardrails. Do not copy their thresholds or substitute
local heuristics. Record the candidate-bound guardrail evidence and classify the
candidate before any remote publication.

- When the candidate fits the guardrails, use the ordinary single-PR path.
- When it is oversized, decide whether the ticket should be split or the branch
  should be carved. Prefer tracker-level ticket decomposition when the parts are
  independently valuable and trackable. Prefer `carve-changesets` only when the
  ticket remains one coherent deliverable whose implementation diff is simply
  too large for one reviewable PR.
- The operator decides between those outcomes from the recorded evidence. When
  the ticket should be split, or the decision is unresolved, stop before remote
  publication with `blocked`; tracker-splitting mechanics are out of scope.
- An oversized coherent candidate may use the carved path only with the explicit
  `decompose oversized candidates into stacked changesets` authority grant.
  Without it, stop and ask or return `blocked` with the guardrail evidence.

Recheck that no canonical PR, stack, or branch already owns the ticket. Never
publish both paths for one candidate.

### 6. Publish and delegate the selected path

For the ordinary path, push the candidate branch, open one focused PR, and
follow [the babysit-pr handoff](references/babysit-pr-handoff.md). Map
`ready PR only` to `ready_to_merge`; map both merge policies to
`merge_when_ready`.

For the carved path, follow
[the carve-changesets handoff](references/carve-changesets-handoff.md) and
transfer the immutable source candidate to `carve-changesets`. Map
`ready PR only` to its publish boundary and `prs_open`; map both merge policies
to its merge-and-propagate boundary and `all_merged`. `implement-ticket`
performs no direct `babysit-pr` handoff, watcher, retry, feedback, fix, or merge
loop for any stack PR. Exactly one watcher owner exists per PR.

In either path, describe the ticket-wide outcome, important non-goals, and
actual validation. Use the owning tracker's correct closing syntax on the one
ordinary PR or only on the final changeset PR. Intermediate stack PRs use a
non-closing reference and must remain behaviorally safe under the
`carve-changesets` equivalence contract. Verify the ticket transition only after
the ordinary PR merges or `carve-changesets` returns `all_merged`.

Normal ticket execution never uses `watch_until_closed`. Ordinary pending CI or
review time is not a blocker; retain task ownership through the selected
delegate until its mapped policy reaches a terminal result or a genuine
user-help-required condition occurs.

Validate the returned identity and evidence against live GitHub state. After an
authorized ordinary merge or `all_merged`, independently verify remote merge
state, complete mainline representation, and the owning tracker's ticket
transition before cleanup. A mid-stack material redesign that invalidates an
earlier merged changeset returns `blocked`; never paper it over by mutating
merged history. For an epic child, reread affected native dependency
relationships and report newly unblocked work without selecting or mutating it.
Never close or verify a parent epic from this skill.

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

- `ready_pr`: the ticket's one ordinary PR is open and mergeable at the reported
  candidate, every applicable current-candidate non-merge gate has passed, merge
  was withheld, and this run owns or was explicitly handed ownership of the
  candidate;
- `ready_prs`: the ticket's carved stack is open with verified topology and
  every PR at its applicable non-merge gate, merge was withheld, and
  `carve-changesets` returned current-candidate `prs_open` evidence;
- `merged`: either the ordinary PR is verified on the base or the full carved
  stack is verified there after `all_merged`; in both cases the ticket
  transition and authorized cleanup are verified;
- `blocked`: give one concrete blocking reason and next action, preserving any
  partial artifacts; or
- `requires_epic`: no mutation occurred and the handoff names `implement-epic`
  with its stable routing marker.

When this ticket is an epic child, report newly unblocked downstream work after
merge but do not select or implement it. Never claim whole-epic acceptance or
close a parent.
