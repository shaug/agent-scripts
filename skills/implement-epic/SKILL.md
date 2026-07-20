---
name: implement-epic
description: Implement one or more GitHub or Linear epics through their live dependency graphs by selecting ready PR-sized children and invoking the repository-owned implement-ticket skill exactly once per child. Use when an agent should sequence an entire epic, one named child, or a named subset; refresh graph state after merges; preserve authority and isolation boundaries; and verify epic-wide acceptance and closeout without duplicating single-ticket implementation, review, PR, merge, or cleanup mechanics.
---

# Implement Epic

Orchestrate the live work graph. Delegate each selected child to
`implement-ticket`; never reproduce its one-ticket workflow.

## Require the ticket skill

Before an epic run, verify that `implement-ticket` is available, readable, and
supports `ready_pr`, `merged`, `blocked`, and `requires_epic` terminal results.
Return `blocked` before mutation when the dependency or result contract is
missing or untrustworthy. Do not substitute a generic implementation agent,
inline a copy of the ticket workflow, or weaken any gate.

`implement-ticket` owns ticket readiness, isolated implementation, validation,
`review-code-change`, PR state, remote gates, merge, tracker transition, per-PR
cleanup, and terminal evidence. Do not invoke individual review lenses or
`review-code-change` directly from this skill.

## Load graph and closeout references

- Read [the GitHub graph adapter](references/github.md) whenever GitHub owns
  parent, child, or dependency state.
- Read [the Linear graph adapter](references/linear.md) whenever Linear owns
  parent, child, dependency, or status state.
- Always read [epic closeout](references/closeout.md) before closing a parent or
  umbrella epic.

Resolve issue-tracker ownership independently from repository and PR-host
ownership. Let `implement-ticket` load the applicable single-ticket adapters.

## Resolve the epic contract

Before selecting work, discover or receive and verify:

- the in-scope epic, epic series, named child, or named child subset;
- owning tracker, live native parent/sub-issue and blocker relationships, and
  current issue states;
- repository, PR host, current remote base, and applicable local instructions;
- named architecture, design, contract, migration, and rollout documents;
- completion policy: ready PRs only, merge children after gates, or merge plus
  separately authorized epic closeout;
- serial execution by default, with parallel execution only when explicitly
  authorized and proven non-overlapping; and
- authority for child execution, merge, manual transitions, graph edits,
  follow-up creation, branch deletion, parent closeout, deployment, production
  mutation, and destructive operations.

Pass authority into `implement-ticket` without expansion. Ready-PR authority
does not imply merge. Child merge authority does not imply parent closeout.
Words such as `finish`, `complete`, or `end to end` do not independently grant
merge, graph mutation, deployment, or closeout authority.

Use this source order:

1. Current user instructions.
2. Live epic, child, dependency, branch, and PR state.
3. Repository instructions.
4. Named specifications and rollout documents.
5. Current code and tests.
6. Prior summaries or memory.

Stop on material conflicts rather than selecting a convenient interpretation.

## Run the graph loop

Repeat until the requested scope reaches its completion policy or a genuine
blocker requires user input.

### 1. Refresh live state

- Read every in-scope epic and its current children.
- Read native parent, sub-issue, `blockedBy`, and `blocking` relationships.
- Read dispositions and delivered outcomes of closed blockers.
- Inspect existing branches and open or merged PRs before selecting a child.
- Separate the serial critical-path recommendation from other parallel-ready
  work.

Never infer the current graph from an old plan, issue list order, Markdown task
list, label, or previous loop iteration when native relationships are available.

### 2. Select one child

Select an open, in-scope, PR-sized child only when native graph state shows no
open blocker. At the graph boundary, verify that every required closed-blocker
outcome exists in its authoritative repository, artifact registry, tracker, or
environment. Treat canceled or not-planned blockers with missing required
outcomes as unresolved.

When multiple children are ready, prefer contracts and additive foundations
before consumers or cutovers, then prefer the child that unlocks the most
downstream work without widening scope. Do not absorb a missing sibling outcome
into the selected child.

### 3. Invoke exactly one ticket execution

Invoke `implement-ticket` once with a concise handoff containing:

- selected ticket identity and owning tracker;
- parent outcome and only the dependency/sibling evidence needed for safe
  independent shipping;
- repository, PR host, base, and named specifications;
- completion policy and every granted or withheld authority; and
- any epic-level rollout or merge-order constraint that qualifies the child.

The primary context may follow `implement-ticket` directly. A delegated worker,
subagent, or equivalent context must have exclusive ownership of one verified
ticket worktree and branch. Never run two mutating contexts against the same
candidate. Parallelize only explicitly authorized children whose graph,
repository, file/contract ownership, rollout, and merge-order analysis proves no
material overlap.

### 4. Verify the terminal result

Do not trust a reported result until ticket identity, repository, base,
branch/worktree, candidate, PR, validation, review, remote-gate, merge,
transition, and cleanup evidence are internally consistent and match live state.

- `ready_pr`: record the candidate and remaining gates. Do not count the child
  complete or unblock dependents that require merge. Continue only with another
  independently ready child when the requested scope permits it.
- `merged`: verify mainline and tracker evidence, then refresh the complete live
  graph before any selection or completion claim.
- `blocked`: preserve the exact reason and partial artifacts. Never count it as
  complete. Select another independently ready child only when the requested
  scope permits; otherwise stop for the missing decision, outcome, or
  capability.
- `requires_epic`: treat it as an invalid child selection or malformed handoff.
  Stop or refresh and resolve scope; never recursively invoke this skill, bounce
  back to `implement-ticket`, or flatten the returned epic into the child.

### 5. Refresh or stop at the requested boundary

After every verified merge or tracker transition, reread the native graph. Do
not reuse an earlier ready set. Report newly unblocked work even when the
requested boundary has been reached.

For one named child, stop after that child's completion policy. For a named
subset, process only that subset in dependency order. Do not implement unnamed
siblings or close the parent. For a full epic, continue until closeout is
eligible or a genuine blocker remains.

## Close epics conservatively

Follow [epic closeout](references/closeout.md). Close a parent only with
explicit parent-close authority and current evidence that:

- every required child and blocker outcome is satisfied;
- every required PR result is represented on the base;
- parent acceptance criteria hold against resulting behavior;
- required clean-main, documentation, migration, compatibility, rollout, and
  cleanup checks pass; and
- the epic-wide late-feedback sweep has no undispositioned material finding.

Validate and close each epic separately before an umbrella parent. A nearly
complete graph is not complete.

## Stop conditions

Stop and report `blocked` when:

- live graph and requested scope conflict materially;
- a required dependency outcome or `implement-ticket` capability is missing;
- a product, architecture, migration, destructive, or authorization decision is
  unresolved;
- delegated mutation ownership or returned evidence is ambiguous;
- epic-wide validation or late feedback shows a required unresolved gap; or
- parent closeout lacks authority.

Difficulty, ordinary CI wait time, or unrelated ready children are not blockers.

## Report the epic result

Report the requested scope, each invoked ticket and its terminal state, merged
and ready PRs, refreshed graph state, serial critical-path and parallel-ready
work, parent acceptance and closeout evidence, intentionally deferred work, and
one concrete next action. Never report a child or parent complete from stale or
unverified evidence.
