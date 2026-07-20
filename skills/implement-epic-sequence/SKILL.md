---
name: implement-epic-sequence
description: Execute one or more GitHub or Linear epics end to end through their live dependency graphs. Use when Codex should select unblocked PR-sized children, implement each in an isolated branch or worktree, run repository validation and bounded review loops, wait for current-head review and CI gates, merge and clean up safely, refresh the graph after every merge, and close epics only after resulting behavior and acceptance criteria are verified.
---

# Implement Epic Sequence

Execute the live work graph, one independently mergeable child at a time. Treat
tracker state and repository evidence as the source of truth; do not turn an old
plan or conversation summary into execution state.

## Load the relevant references

- Resolve the issue tracker and the code/PR host independently.
- Read `references/github.md` whenever GitHub owns issue state or hosts the
  repository and PRs. This includes Linear-owned epics implemented through
  GitHub PRs.
- Read `references/linear.md` whenever Linear owns parent, child, dependency, or
  status state.
- Always read `references/review-and-merge-gates.md` before publishing the first
  PR in a run.
- Always read `references/closeout-and-cleanup.md` before merging the first PR
  or closing an epic.

For cross-system work, load every applicable adapter and record which system
owns issue status, dependency state, source code, PR state, checks, review, and
merge. Do not assume the issue tracker also hosts the PR.

## Resolve the operating contract

Before changing code, resolve:

- repository and tracker;
- epic identifiers and any named child subset;
- base branch;
- completion policy: ready PRs only, merge after gates, or merge plus epic
  closeout;
- execution mode: serial by default, parallel only when explicitly requested;
- required review mechanism;
- mutation authority for tracker edits, status or dependency changes, follow-up
  creation, review replies and resolution, merge, parent closeout, remote-branch
  deletion, and deployment;
- named architecture, design, contract, or rollout documents.

Unless the user or repository contract states otherwise, apply this authority
matrix:

- `ready PRs only` authorizes isolated implementation, commits, feature-branch
  pushes, PR creation or updates, evidence-based review replies, and resolution
  of fully addressed review threads;
- `merge after gates` additionally authorizes merging the in-scope PR and safely
  deleting its verified merged feature branch;
- `merge plus epic closeout` additionally authorizes evidence comments and
  manual status or close transitions for the in-scope children and parents;
- issue-body edits, dependency-graph mutations, and follow-up-ticket creation
  require explicit ticket-management authority; and
- deployment, production mutation, and destructive data operations always
  require explicit authority.

Do not infer merge or issue-close authority from words such as `finish`,
`complete`, or `execute end to end`; treat them as persistence within the
selected completion policy. Merge PRs or close issues only when the user
explicitly selects a merge-inclusive policy or unambiguously asks for those
actions. When merge authority is unclear, stop at a ready PR and request it.
Never infer deployment or production mutation from merge authorization.

If a required input cannot be discovered safely and materially changes the
outcome, stop and ask. Otherwise use repository conventions.

## Establish source-of-truth precedence

Use this order within the task:

1. Current user instructions.
2. Live parent, child, dependency, and PR state.
3. Repository `AGENTS.md` and equivalent local instructions.
4. Named architecture, design, contract, and rollout documents.
5. Current code and tests.
6. Prior summaries or memory as orientation only.

Stop on material conflicts between the live dependency graph, ticket body, and
repository contract. Do not choose the most convenient interpretation.

## Run the epic loop

Repeat the following procedure until the requested scope reaches its completion
policy or a genuine blocker requires user input.

### 1. Refresh live state

- Read every in-scope epic and its open children.
- Read native parent, blocking, and blocked-by relationships.
- Read the dispositions and delivered outcomes of closed blockers for candidate
  children.
- Inspect existing branches and open or merged PRs for candidate children.
- Recompute ready work after every merge; never reuse yesterday's order.
- Separate the serial critical-path recommendation from parallel-ready work.

When multiple children are ready, prefer the child that unlocks the most
downstream work without widening scope. Prefer contracts and additive
foundations before consumers and cutovers.

### 2. Apply the readiness gate

Select a child only when it:

- is open and belongs to an in-scope epic;
- has no unresolved native blocker;
- has every required closed-blocker outcome verified in its authoritative
  repository, artifact registry, tracker, or environment; for a cross-repository
  or operational prerequisite, also verifies that the consumer uses the required
  contract, version, configuration, approval, or environment state;
- is not already implemented, superseded, or represented by another PR;
- delivers one coherent outcome through one PR;
- states goals, non-goals, acceptance criteria, and verification;
- contains no unresolved product, data, authorization, migration, destructive,
  or architecture decision;
- identifies existing behavior that must be preserved;
- can merge without exposing misleading or incomplete behavior.

Treat a canceled or not-planned blocker with an unmet required outcome as
unresolved even when the tracker marks it closed. Do not absorb that missing
prerequisite into the selected child. Do not improvise missing requirements.
When ticket editing is authorized, make the ticket implementation-ready and
re-read it. Otherwise select another ready child or report the missing decision.

### 3. Create isolated implementation state

- Confirm the primary checkout, current worktree, and all registered worktrees.
- Fetch and prune the remote.
- Start a fresh feature branch and disposable worktree from the current remote
  base unless the repository directs otherwise.
- Use one ticket per branch and one ticket-closing PR.
- Verify the new worktree is clean before editing.
- Install dependencies and start documented local services before diagnosing
  missing-tool or missing-service failures as feature failures.

Preserve unrelated worktrees, branches, and local changes. Never reuse a dirty
or ambiguous checkout merely to save setup time.

### 4. Implement the ticket contract

- Read nearby implementation and tests before editing.
- Keep the live child and named source documents as the scope boundary.
- Preserve explicit non-goals and existing behavior named by the ticket.
- Follow existing architecture and extension points.
- Add focused behavior tests with the implementation.
- Update contract or contributor documentation when executable behavior changes.
- Keep exported-symbol documentation aligned with repository rules.
- Avoid speculative backfills, compatibility layers, or abstractions for
  nonexistent conditions.

Apply incidental changes only for a demonstrated correctness, security,
acceptance, architecture, or validation need, or for an obvious low-cost
correctness or safety improvement with demonstrated current risk. Refactor to
reduce cognitive load only when the user explicitly requests it or when the
ticket's correctness cannot otherwise be made evident. Defer polish, broad
refactors, hypothetical hardening, and adjacent epic work.

### 5. Validate in layers

Discover validation from repository instructions and tooling. Run:

1. focused tests for changed behavior;
2. relevant static checks;
3. the complete required repository gate;
4. integration tests with documented real dependencies;
5. build, packaging, or manual checks required by the ticket.

Report exact outcomes. Distinguish bootstrap/environment failures from feature
failures. Do not claim completion when required validation is unavailable or
failing.

### 6. Publish one focused PR

- Confirm no existing PR already owns the ticket.
- Commit using repository conventions.
- Push only the feature branch.
- Summarize the whole branch, observable outcome, important non-goals, and
  actual validation.
- Include the tracker-closing reference required by the repository.
- Open the PR as draft or ready according to the operating contract.

Do not combine independently useful tickets in one PR, even when they touch the
same files.

### 7. Run bounded review

Follow `references/review-and-merge-gates.md`.

- Implement directly in the primary execution context.
- After local validation, require one fresh, read-only adversarial
  `code-review-pro` pass in a separate review-only subagent or equivalent
  isolated context unless the user explicitly waives it or independent review
  tooling is unavailable.
- Use a fresh or minimally inherited context. Give the reviewer only raw task
  artifacts: repository instructions, the live ticket, named specifications, the
  complete `base...HEAD` diff for the captured head/base SHA pair, and
  validation evidence. Do not provide the implementation transcript, intended
  answer, prior conclusions, or suspected findings.
- Before review, require every intended ticket change to be committed and the
  implementation worktree to be clean. If unrelated user artifacts prevent a
  clean state, classify and preserve them and prove they are irrelevant to the
  candidate.
- Before delegation, capture HEAD, commit history, and tracked, untracked, and
  ignored worktree state. After review, verify that all remain unchanged. Treat
  any reviewer mutation as an integrity failure and inspect it without
  discarding user work.
- Review correctness, acceptance criteria, regressions, failure paths, security,
  authorization, architecture, public surface area, tests, documentation, and
  scope.
- Apply only material, tractable, in-scope findings.
- Re-run affected and required validation after fixes.
- Run a fresh pass after material fixes and invalidate prior remote review
  signals after every head or base change.
- Use at most three adversarial passes by default. If the final pass still has a
  material finding, do not merge; report the unresolved finding and request
  direction.

Do not silently count an unavailable independent reviewer as a passed gate.
Record the limitation, perform a fresh adversarial self-review, and proceed only
when repository policy does not require independence and the user has accepted
or already authorized the unavailable-tool fallback.

Create a follow-up ticket only when ticket management is authorized and the gap
is real, evidenced, and intentionally outside the current PR. Otherwise report a
pasteable follow-up proposal.

### 8. Merge only through current-candidate gates

Follow both bundled gate references. Merge only when:

- every intended ticket change is committed and represented by the candidate
  diff, with any unrelated artifacts classified, preserved, and proven
  irrelevant;
- required local validation passed;
- required CI passed or the repository explicitly has no such checks;
- every applicable required adversarial, human, and connector review has a clean
  or approving verdict explicitly tied to the exact current head and base SHA
  pair;
- no undispositioned actionable conversation comment, formal review, connector
  feedback, or review thread remains;
- the PR still matches its ticket and base;
- no other PR superseded it.

Treat every head change, including a push, rebase, conflict resolution, or
update-branch operation, and every base-branch advance as invalidating older
merge-candidate evidence. Rebuild and revalidate the current head/base candidate
before merge.

After merge, verify the remote state and base-branch result before cleanup.

### 9. Clean up and refresh

- Confirm merge or patch equivalence before deleting branch state.
- Confirm the disposable worktree is clean and contains no untracked or ignored
  user files.
- Confirm the local branch has no commit absent from its pushed PR branch, the
  pushed branch when it still exists has not advanced beyond the PR's recorded
  merged head, and that merged-head result is fully represented on the verified
  base by ancestry or patch equivalence. Never force cleanup past a failed
  precondition.
- Remove only the merged feature branch and disposable worktree.
- Preserve unrelated worktrees and edits.
- Verify the ticket closed as intended.
- Re-read the live graph before selecting another child.

## Close an epic conservatively

Use `references/closeout-and-cleanup.md`. Close an epic only when:

- every required child is closed;
- no unresolved blocker remains;
- every required PR is represented on the base branch;
- epic acceptance criteria are verified against resulting behavior;
- required documentation, compatibility, migration, rollout, and cleanup work is
  complete;
- no child closed as not planned leaves an unsatisfied outcome;
- the mandatory late-feedback sweep for every merged PR is complete and every
  finding has a recorded disposition;
- required clean-main and candidate checks passed.

For a series, validate each epic separately, then validate any umbrella parent.
Keep the parent open when any required outcome remains unsatisfied.

## Stop conditions

Stop and request direction when:

- graph and ticket scope conflict materially;
- implementation requires an unresolved product or architecture choice;
- a destructive migration, production cutover, or deployment lacks authority;
- credentials, external approval, or unavailable infrastructure are required;
- correctness would materially exceed ticket scope;
- review feedback requires redesigning the ticket;
- required validation remains unavailable after documented bootstrap attempts.

Difficulty, a long test suite, or ordinary CI wait time are not blockers.

## Final reporting

For each child, report the ticket, PR, merge result, validation, review state,
and cleanup result. At epic completion, report:

- closed and intentionally deferred children;
- final dependency-graph state;
- mainline and acceptance-criteria evidence;
- remaining parallel-ready work outside the requested scope;
- any limitation that prevented full closeout.
