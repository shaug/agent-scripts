# Review Fix Loop Design

Status: proposed\
Date: 2026-07-29

## Decision summary

Add a repository-owned `review-fix-loop` skill that takes cooperative ownership
of an existing committed candidate, runs the complete repository-owned review
suite, applies material ticket-scoped fixes, validates and commits each accepted
remediation, and repeats until the complete review converges or a bounded stop
condition is reached.

The skill owns review remediation and convergence. It does not replace
`review-code-change` or any individual review lens. It does not implement the
original ticket, create a pull request, watch CI or external feedback, determine
merge readiness, merge, transition a tracker item, deploy, or clean up branches
and worktrees.

`review-fix-loop` always operates with fix authority. It has no read-only mode,
and its invocation-scoped fix-cycle budget must be at least one. Users who want
a read-only review should invoke `review-code-change` or an individual review
lens directly.

Reviews run in a newly created read-only aggregate-review subagent by default.
An in-agent review is allowed only through an explicit invocation override.
Nested review lenses may share the aggregate-review subagent.

Fix commits remain local during ordinary iteration. Under `update_pr`, the skill
pushes the complete fast-forward range once after convergence. An intermediate
push is allowed only for an invocation-authorized mechanism that demonstrably
requires an origin-visible head. Every non-converged result reports the exact
local head and every unpushed commit relative to its recorded source. When no
source exists, it reports that explicitly instead of inventing remote
divergence.

The initial contract deliberately does not introduce a distributed ownership,
lease, fencing, or coordinator service. Competing worktrees in the same Git
common directory are prevented by a local candidate lock. Separate clones,
whether on the same or different hosts, may race at publication; that race is
detected by an exact expected-old, fast-forward-only Git ref update and
post-push readback. A losing invocation stops and preserves its local commits
for operator reconciliation.

This epic implements and validates the standalone skill. Existing workflow
owners continue using their current loops during the epic. Their migrations are
separate fast-follow tickets blocked by this epic or by the representative
`review-fix-loop` capability they consume.

## Context

The repository currently divides review responsibilities correctly but repeats
the mutating half of the workflow:

- `review-code-change` builds and validates one evidence packet, runs the
  repository-owned lenses, and returns one read-only aggregate result.
- `implement-ticket` owns the initial fix, validation, commit, and re-review
  loop before publication.
- `babysit-pr` owns similar repository-review remediation after a published
  candidate changes.
- `carve-changesets` applies accepted review fixes to local changeset candidates
  and rebuilds invalidated chain evidence.

The repeated behavior is also useful on its own. An implementation may be
interrupted after the candidate exists but before review converges, or an
operator may intentionally implement and review in separate tasks.
`implement-ticket` is too broad for that use case because it also owns initial
implementation, publication-path selection, tracker lifecycle, and cleanup.
`review-code-change` is too narrow because it must remain read-only.

The missing abstraction is a candidate-remediation workflow between those two
levels.

## Goals

`review-fix-loop` must:

01. Resume from live repository and optional pull-request state without
    requiring an uninterrupted implementation transcript.
02. Prove the exact candidate identity and acquire a same-common-directory local
    mutation lock before making a change.
03. Use the complete repository review suite as its sole initial review mode.
04. Run every review pass in a fresh read-only aggregate-review subagent by
    default.
05. Apply only material, evidenced, ticket-scoped findings.
06. Validate and commit every accepted remediation before reviewing the new
    head.
07. Invalidate all head-bound evidence after every candidate change.
08. Bound automatic remediation with one invocation-owned fix-cycle budget and
    explicit non-convergence stops.
09. Return a candidate-bound result that standalone operators and future callers
    can validate.
10. Work on a committed local candidate or an existing pull-request branch.
11. Keep fixes local until convergence unless a required mechanism can inspect
    only an origin-visible head.
12. Detect remote publication races without overwriting another candidate.

## Non-goals

The skill must not:

- discover, select, or implement the original ticket;
- turn an uncommitted worktree into an inferred candidate;
- provide a read-only or zero-fix-cycle mode;
- create an initial branch, worktree, or pull request;
- push an intermediate fix merely because a remote branch exists;
- watch or retry CI;
- collect, reply to, or resolve human, connector, or inline review feedback;
- decide that a pull request is ready to merge;
- merge, deploy, transition tickets, close epics, or delete branches or
  worktrees;
- weaken `review-code-change` by allowing a partial lens run to return a
  certifying aggregate `clean`;
- reuse the mutating implementation context as the reviewer unless the
  invocation explicitly authorizes that override;
- own stack decomposition, immutable-source lineage, or changeset propagation;
- apply deferred, speculative, cosmetic, sibling, or parent-epic work;
- prevent concurrent work in unrelated clones before publication;
- provide distributed leases, fencing tokens, atomic cross-host handoff, or a
  coordinator service; or
- migrate existing caller skills as part of the initial implementation epic.

## Architectural position

The initial dependency graph is:

```text
standalone review-fix-loop
└── review-code-change
    ├── review-solution-simplicity
    ├── review-correctness
    └── review-code-simplicity
```

Future caller integrations may produce:

```text
implement-ticket ──> review-fix-loop ──> review-code-change
babysit-pr      ──> review-fix-loop ──> review-code-change
carve-changesets──> review-fix-loop ──> review-code-change
```

Those edges are not added by this epic. Each caller migration must prove that
its existing lifecycle, acceptance, publication, or chain invariants remain
caller-owned.

The graph remains acyclic:

- `review-fix-loop` never invokes `implement-ticket`, `implement-epic`,
  `babysit-pr`, or `carve-changesets`.
- Review skills remain read-only and never invoke `review-fix-loop`.
- A caller that later delegates to the loop stops candidate mutation until the
  loop returns and validates the returned head against live state.

## Responsibility boundary

### `review-code-change`

Continues to own:

- construction and validation of the shared evidence packet;
- full-suite lens order;
- lens-result validation;
- simplification-proposal disposition;
- finding reconciliation and deduplication;
- aggregate verdict semantics; and
- read-only candidate integrity.

It returns findings and the next required action. It never applies a fix.

### Individual review lenses

Continue to own their existing rubrics and shared result shapes. They remain
read-only and available through their existing skills. They are not directly
selectable modes of the initial `review-fix-loop`.

### `review-fix-loop`

Owns:

- candidate and authority resolution for the remediation interval;
- same-common-directory local mutation locking;
- reviewer-context selection and isolation;
- finding verification and disposition;
- the smallest sufficient ticket-scoped edits;
- affected and repository-required validation after edits;
- one commit for each successful remediation cycle;
- evidence invalidation after every new head;
- cycle accounting and convergence detection;
- optional exact-ref publication under `update_pr`; and
- its durable checkpoint and terminal result.

### Calling workflow

Continues to own:

- original ticket selection, readiness, implementation, and acceptance;
- any external review or CI findings that caused the candidate to change;
- publication-path selection and initial pull-request creation;
- pull-request watching, remote gates, feedback communication, and merge;
- stack topology, immutable-source lineage, and propagation;
- tracker, deployment, mainline, and cleanup outcomes; and
- reconciliation of caller-owned acceptance evidence after a returned head or
  base change.

## Invocation contract

The implementation should define a versioned schema for the following logical
contract. It should not add fields for hypothetical distributed coordination.

### Candidate

- repository identity and Git common-directory identity;
- dedicated candidate branch and globally clean worktree;
- exact committed head SHA;
- exact comparison-base ref and SHA;
- complete `base...HEAD` diff;
- tracked, staged, unstaged, untracked, and ignored state;
- optional existing pull-request identity;
- an optional read-only source binding containing the authenticated repository,
  remote URL, fully qualified source ref, and observed object ID, required when
  the candidate has a known pushable source;
- for `update_pr`, publication authority over that exact source binding plus the
  base ref and live base object ID; and
- evidence that all intended candidate changes are committed.

Every invocation requires a dedicated globally clean worktree. Dirty state,
including unrelated untracked artifacts, blocks startup. The skill does not
stash, delete, reset, or guess ownership of existing work.

A candidate without a source binding records an explicit `source_unavailable`
reason. A read-only source binding grants comparison authority only; it never
implies permission to push.

### Change contract

- observable goal;
- acceptance criteria;
- explicit non-goals;
- behavior and invariants to preserve;
- applicable repository instructions and named specifications;
- representative nearby code and tests; and
- allowed remediation scope.

For standalone use, the skill reconstructs this contract from current user
instructions, live ticket or pull-request state when supplied, repository
contracts, code, and tests. Missing essential intent is a blocker, not
permission to infer requirements from the implementation.

### Review execution

The default execution mode is `fresh_subagent`.

Each review pass:

- creates a new aggregate-review context;
- supplies the exact current candidate and base plus a raw evidence packet;
- withholds the implementation transcript, intended fix, prior conclusions,
  suspected findings, and expected result;
- grants no edit, commit, push, communication, merge, or tracker authority; and
- discards the reviewer context after the result.

The aggregate reviewer runs the complete `review-code-change` sequence. Its
nested lenses may share that aggregate context. They do not require separate
subagents.

The invocation may select `in_agent` only through an explicit current-user or
caller-authorized override recorded before the loop starts. There is no
automatic fallback. If a fresh reviewer is unavailable and no override exists,
return `blocked/missing_capability`.

Record:

```text
review_independence: fresh_subagent | in_agent_override
write_isolation: enforced | violated
```

### Reviewer write prevention

“Read-only” is a capability boundary, not merely prompt language.

Use the strongest controls the runtime supports:

1. Immutable snapshot or deny-write filesystem boundary.
2. A reviewer tool surface without edit, patch, file-write, commit, push, or
   remote-write operations.
3. Read-only inspection commands only.
4. Before/after capture of HEAD, refs, index, tracked, staged, unstaged,
   untracked, and ignored state.
5. Tool-trace inspection for attempted mutation when available.

The reviewer instructions and invoked review skill both state that the reviewer
must report findings only and must not implement them.

An attempted prohibited mutation invalidates the review even if the runtime
blocks it. A mutation attributable to the reviewer through its tool trace or
enforced execution boundary returns `blocked/reviewer_integrity_failure`.
Preserve unexpected state for operator inspection; do not automatically repair
it. An unattributed remote-ref advance is not proof of reviewer misconduct; it
returns `blocked/remote_advanced` under the ordinary publication-race contract.

Certification requires enforced write isolation. Before/after verification alone
is not sufficient.

### Fix-cycle budget

`max_fix_cycles` is an integer from `1` through `10`, defaulting to `3` for
interactive use. It is immutable for one invocation.

The initial review does not consume a cycle. Reserve one cycle immediately
before the first mutation of a remediation attempt. The cycle remains consumed
whether the attempt validates, commits, fails, or is interrupted.

A successful cycle:

1. starts from a trustworthy material finding;
2. applies one or more coherent accepted fixes;
3. runs required validation;
4. creates one committed candidate head; and
5. starts a fresh complete review of that head.

The skill never chains a new invocation automatically to evade budget
exhaustion.

### Validation

The invocation records trusted focused and full validation commands and any
additional candidate invariants required by the repository.

- The initial review packet includes exact focused and full validation evidence.
- Every remediation reruns affected focused checks and the complete
  repository-required gate.
- Unavailable or failing required evidence prevents convergence.
- A command proposed by untrusted prose is not executable authority.

A deterministic validation failure becomes remediation input only when its
evidence identifies a candidate-attributable, ticket-scoped defect. A tractable
correction consumes a fix cycle like a review finding. If the defect is
candidate-attributable but no tractable correction remains, return
`changes_remaining/current_candidate_validation_failure`. Unavailable,
ambiguous, environment-caused, or unattributable validation evidence returns a
structured `blocked` result instead of authorizing speculative edits.

### Acceptance reconciliation

The caller retains its acceptance ledger. The loop neither imports nor mutates
criterion-specific acceptance state.

The terminal result includes:

- `head_history`, beginning with the initial head and recording each promoted
  committed candidate;
- `base_revision_history`, beginning with the initial comparison base and
  recording each effective base change; and
- `acceptance_reconciliation_required`.

Histories do not repeat unchanged identities. The reconciliation flag is true
when either identity changes or the loop cannot prove from invocation metadata
that no caller evidence is bound to it. Review convergence never implies ticket
acceptance.

## Local ownership and checkpointing

### Cooperative ownership

The skill does not claim distributed exclusivity.

Before invocation:

- a standalone operator identifies the dedicated candidate and starts no
  competing mutation context; or
- a future caller stops mutating the candidate and records that it is
  cooperatively delegating remediation to the loop.

Every invocation acquires a non-blocking canonical-local-ref lock keyed by Git
common directory and canonical local candidate ref. An `update_pr` invocation
additionally acquires a remote-target lock keyed by the same common directory,
authenticated head-repository identity, and fully qualified remote head ref.
Acquire the local-ref lock before the remote-target lock and release them in
reverse order. This prevents cross-policy mutation of one local branch and
prevents two local branches in one common directory from targeting the same PR
ref concurrently. If another process holds either required lock, the invocation
returns `blocked/candidate_busy` without mutation.

The applicable locks are held for the complete invocation, including review
passes, fix attempts, local commits, optional publication, and checkpoint
reconciliation. The operating system releases them when the process exits. The
durable checkpoint never pretends that an expired process still owns a
distributed lease.

The skill rereads the comparison-base ref before every remediation attempt,
before review, before publication, and before terminal return. If the base
changes, record it in `base_revision_history`, invalidate review and validation
evidence bound to the old base, and rebuild the complete required evidence
before applying any old finding. Evidence rebuilding does not consume a fix
cycle. If rebuilding cannot establish a current-base result, return
`blocked/base_drift`.

Whenever a source binding is available, and always under `update_pr`, the skill
also rereads the exact remote head at those boundaries. A remote head change
stops mutation with `blocked/remote_advanced`. A source-unavailable
`local_commit` invocation may continue locally, but its terminal result must
state that remote divergence and unpushed-commit comparison could not be
determined.

### Durable invocation checkpoint

Record invocation state under a skill-local ignored directory such as
`.review-fix-loop/`. The checkpoint contains:

- invocation ID and schema version;
- repository, branch, worktree, initial head, current head, and comparison base;
- publication policy and optional pull-request identity;
- original cycle budget and consumed attempts;
- ordered phase and head history;
- review identities and finding dispositions;
- validation outcomes;
- committed fixes and preserved failed-attempt artifacts;
- last verified source head and local ahead/behind state, or the explicit
  source-unavailable reason; and
- current phase and one expected next action.

Write checkpoints atomically. Git and live repository state remain
authoritative; the checkpoint records continuity but cannot make stale evidence
current.

Resume requires:

- the same invocation ID;
- no active local lock holder;
- an exact checkpoint schema and repository identity match;
- a clean candidate;
- live head, base, and optional remote identities reconcilable with the
  checkpoint; and
- the same original budget and authority.

If exact reconciliation is impossible, return `blocked/checkpoint_mismatch` and
preserve the checkpoint and candidate for inspection. Starting a new invocation
requires an explicit operator decision and a new invocation ID.

### Transactional remediation attempts

Apply each remediation in an invocation-owned temporary worktree or attempt
branch created from the exact canonical head. The canonical candidate remains
unchanged while edits and validation are in progress.

On success:

1. create one commit on the attempt branch;
2. verify its parent is the exact pre-attempt canonical head;
3. reread the comparison-base ref and reacquire live candidate and optional
   remote-head evidence;
4. if the base changed, leave the canonical head unchanged, preserve the attempt
   as a stale-base artifact, record the new base, and rebuild all base-bound
   review and validation evidence before deciding whether remediation remains;
5. otherwise perform a verified fast-forward-only update through the clean
   canonical worktree so its branch, symbolic HEAD, index, and files advance
   together;
6. verify the canonical HEAD equals the promoted commit, the index tree and
   filesystem equal the promoted candidate tree, and the worktree is globally
   clean; and
7. only then checkpoint the new head.

The attempt already consumed its reserved cycle. Rebuilding evidence after base
drift consumes no additional cycle.

On failure, keep the canonical candidate at its prior clean head and preserve
the attempt patch and diagnostics. Do not present failed work as the candidate.

If interruption leaves an attempt branch or the canonical branch at an
unexpected head, reconcile it from live Git and the checkpoint. Accept only a
uniquely identifiable expected commit. Ambiguity returns
`blocked/candidate_integrity_failure`; the skill does not reset or delete
evidence automatically.

## Publication policy

### `local_commit`

All successful fixes remain committed locally. No remote write is permitted.

### `update_pr`

The invocation must identify an existing pull request, its authenticated head
repository, exact fully qualified head ref, and expected remote-head object ID.

Ordinary iteration remains local. After complete convergence:

1. fetch and reread the exact remote head and base;
2. require the remote head to equal the invocation's expected old object ID;
3. prove the local candidate is a non-rewriting descendant;
4. perform one expected-old, fast-forward-only ref update;
5. read the remote ref back; and
6. require it to equal the converged local head.

Use the strongest exact-old primitive supported by the Git transport, such as an
explicit `--force-with-lease=<ref>:<expected-old>` combined with an independent
ancestry check. This is a compare-and-swap guard, not authority to rewrite
history.

If another clone wins the race, the push must fail without overwriting it.
Return `blocked/remote_advanced` with:

- the expected and observed remote heads;
- the final local head;
- every unpushed commit; and
- the required operator reconciliation.

The skill does not attempt to merge, rebase, force-update, or supersede the
other candidate.

### Origin-visible exception

An intermediate push is permitted only under `update_pr` when a required
reviewer, validation command, or repository gate cannot evaluate the local
candidate.

Before invocation, `remote_iteration_grants` enumerates each authorized
mechanism by stable identifier and kind, exact repository and fully qualified
ref, and evidence of its origin-only limitation. A grant applies only to that
mechanism within that invocation.

Each exceptional push uses the same expected-old, fast-forward-only update and
readback as final publication. It is performed immediately before the named
mechanism. The result records that a non-converged head was exposed and advances
the invocation's expected remote head.

Unknown mechanisms, repository/ref mismatches, missing evidence, and every
`local_commit` invocation fail closed without a remote write.

## Workflow

### 1. Resolve

Validate the invocation, repository instructions, dependencies, change contract,
candidate identity, clean worktree, budget, authority, validation commands,
reviewer-isolation capability, publication policy, and optional remote-iteration
grants.

Acquire the local candidate lock before any review or mutation.

### 2. Establish evidence

Capture the exact head, base, diff, worktree state, validation evidence, and
optional read-only source head. Reconcile a supplied checkpoint before using it.
Classify any failing validation evidence under the validation contract before
authorizing remediation.

### 3. Review

Use the review mode recorded by the invocation. By default, create a fresh
read-only aggregate-review subagent. Only when the invocation contains the
explicit override, run the same complete aggregate review in-agent. In either
mode, invoke `review-code-change` with a new raw packet bound to the exact head
and base and enforce the same write-isolation and integrity requirements. Reject
stale, partial, malformed, or integrity-violating results.

### 4. Decide

For each material review finding or candidate-attributable validation failure:

- verify its evidence against the candidate;
- confirm it is within the change contract;
- accept, reject with rationale, or defer only when deferral is permitted; and
- stop for operator input when a required fix would expand scope or authority.

### 5. Fix

If accepted remediation input remains and budget is available, reserve one cycle
and create an isolated attempt from the exact current head. Apply the smallest
coherent remediation.

### 6. Validate and commit

Run focused and full validation in the attempt. On success, create one commit
and promote it by verified local fast-forward. On failure, preserve the attempt
artifact and leave the canonical candidate unchanged.

### 7. Invalidate and repeat

Discard old-head review and validation claims, set acceptance reconciliation as
required, rebuild the raw packet, and begin a fresh complete review.

Do not push during ordinary iteration.

### 8. Publish after convergence

Under `local_commit`, perform no remote write. Under `update_pr`, use the exact
expected-old publication procedure. If publication-time base drift invalidates
review or validation, revoke convergence and rebuild the affected evidence
before publishing.

### 9. Return

Write the terminal checkpoint, release the local lock, and return one
candidate-bound result. A future caller validates the returned identities
against live Git before resuming mutation.

## Convergence and stop conditions

Terminal states are:

- `converged`: the complete aggregate review is `clean` for the exact final head
  and base, required validation passes, reviewer integrity is verified, and the
  selected publication policy completed.
- `changes_remaining`: bounded remediation stopped with actionable work after
  consuming allowed cycles or detecting non-convergent behavior.
- `blocked`: the loop cannot continue safely because capability, authority,
  evidence, ownership, integrity, scope, validation, publication, or operator
  input is missing.

`changes_remaining` reasons:

- `cycle_budget_exhausted`;
- `repeated_finding`;
- `oscillation`;
- `expanding_findings`;
- `repeated_failed_attempt`; or
- `current_candidate_validation_failure`.

Representative `blocked` reasons:

- `candidate_busy`;
- `candidate_integrity_failure`;
- `checkpoint_mismatch`;
- `missing_capability`;
- `missing_authority`;
- `insufficient_change_contract`;
- `reviewer_integrity_failure`;
- `validation_unavailable`;
- `base_drift`;
- `remote_advanced`;
- `publication_failed`;
- `scope_decision_required`; or
- `operator_input_required`.

Stop early when the same material finding survives its claimed fix, finding sets
oscillate, findings materially expand across cycles, or repeated attempts fail
without progress. These stops preserve budget and expose the actual remaining
work.

## Terminal result contract

Return one versioned result containing:

- terminal state and structured reason;
- invocation ID, original budget, consumed cycles, and resume status;
- repository, worktree, branch, pull-request identity when present;
- initial and final head;
- comparison base;
- ordered head and base-revision histories;
- complete aggregate review identity and exact candidate binding;
- reviewer identities, independence mode, write-isolation evidence, and any
  mutation attempts;
- validation commands and outcomes;
- finding dispositions and fix-to-commit linkage;
- created commits and preserved failed-attempt artifacts;
- initial and final source heads, or the explicit source-unavailable reason;
- local ahead/behind state and every unpushed commit when a source is bound;
- publication state and any non-converged remote exposure;
- `acceptance_reconciliation_required`;
- unresolved or deferred findings; and
- one next action.

A future caller must validate the result against live Git. The result does not
claim ticket acceptance, PR readiness, merge authority, deployment, or cleanup.

## Effects on existing skills

### `review-code-change` and individual lenses

No behavioral or verdict change is required. `review-fix-loop` consumes the
existing complete aggregate result and reinforces the existing read-only
boundary.

Packaging may add documentation identifying `review-fix-loop` as a consumer, but
review skills do not gain mutation authority or invoke it.

### `implement-ticket`

No migration occurs in this epic. Its existing initial review/fix loop remains
authoritative.

Create this fast-follow migration ticket alongside the implementation epic and
record its dependency immediately. Block it on the completed `review-fix-loop`
epic or the child that delivers and evaluates the end-to-end `local_commit`
capability, including reviewer isolation and recovery. A contract-only child is
not sufficient. The ticket must prove:

- cooperative same-common-directory ownership transfer;
- one shared invocation-scoped cycle budget;
- current-head aggregate review equivalence;
- caller-owned acceptance reconciliation;
- interruption and response-loss handling; and
- removal of duplicated mechanics only after equivalence passes.

### `babysit-pr`

No migration occurs in this epic. It continues to own CI, external feedback,
review communication, mergeability, and optional merge, including its current
repository-review remediation loop.

Create this fast-follow migration ticket alongside the implementation epic and
block it on the completed epic or the child that delivers and evaluates the
end-to-end `update_pr` capability. The ticket must prove:

- fixes remain local until convergence;
- exact expected-old publication and remote-head reconciliation;
- watcher and remote-gate restart after a returned head;
- one repository-review cycle budget;
- non-converged unpushed-commit reporting; and
- no transfer of CI, feedback, or merge lifecycle ownership.

### `carve-changesets`

No migration occurs in this epic. Its immutable-source, ordering, chain
equivalence, published topology, and recovery rules remain authoritative.

Create this fast-follow evaluation-and-migration ticket alongside the
implementation epic and block it on the completed epic or the narrowest usable
end-to-end evaluated capability it consumes. It may also depend on the
`babysit-pr` migration where published changesets use that lifecycle. Migration
proceeds only if fixtures prove that per-changeset convergence does not replace
or weaken whole-chain equivalence.

### `implement-epic`

No direct integration is required. If `implement-ticket` later migrates,
`implement-epic` observes the new terminal evidence indirectly. Create a
documentation or compatibility follow-up only if the `implement-ticket`
migration changes the child handoff it consumes.

### Other workflow owners

Search the live repository for any skill that implements a mutating
review/fix/re-review loop. Create a separate migration ticket for each real
consumer. Each ticket is blocked by the completed epic or the narrowest stable
and end-to-end evaluated capability it requires. A schema or contract-only child
does not unblock migration. Do not absorb those migrations into the skill
implementation epic.

## Compatibility and rollout

The epic should deliver the standalone skill in this order:

1. Define the invocation, checkpoint, and terminal-result schemas.
2. Implement local locking, isolated remediation attempts, recovery, and cycle
   accounting.
3. Implement reviewer isolation and complete-review orchestration.
4. Deliver and evaluate standalone `local_commit`.
5. Add and evaluate `update_pr` with exact expected-old publication.
6. Add packaging, discovery metadata, dependency-closure tests, and
   documentation.
7. Run result-blind forward evaluations and exact-head repository review.

Existing callers remain unchanged throughout.

Create the caller-specific fast-follow tickets alongside the epic and record
their native dependencies immediately. Completing the epic or representative
capability child unblocks them. A caller uses either its current loop or
`review-fix-loop` for a candidate, never both.

## Validation strategy

Deterministic contract tests cover:

- rejection of zero or negative cycle budgets and read-only invocations;
- exact invocation identity and immutable budget across resume;
- dirty worktree, stale head, stale base, and missing-contract rejection;
- base drift before remediation, review, publication, and return, including full
  evidence invalidation and cycle-free rebuilding;
- canonical-local-ref locking for every policy plus the additional `update_pr`
  remote-target lock, including cross-policy contention and two local branches
  targeting the same PR ref;
- local lock release after process exit;
- checkpoint atomicity, resume, mismatch, and explicit new invocation;
- isolated failed attempts that leave the canonical candidate clean;
- successful promotion that leaves canonical HEAD, branch, index tree,
  filesystem tree, and checkpoint identity equal to the promoted commit;
- base drift immediately before canonical promotion, leaving the candidate
  unchanged and preserving the stale-base attempt;
- uniquely identifiable interrupted-commit recovery and ambiguous-state
  blocking;
- default fresh reviewer selection and different reviewer identities per head;
- shared aggregate context for nested lenses;
- explicit in-agent override and no automatic fallback;
- deny-write enforcement, mutation-tool exclusion, and integrity auditing;
- blocked or attempted reviewer mutation;
- initial convergence without artificial commits;
- one or more successful fix cycles followed by fresh complete review;
- stale or partial aggregate-result rejection;
- exact cycle accounting for successful, failed, and interrupted attempts;
- repeated-finding, oscillation, expansion, and budget stops;
- acceptance-reconciliation signaling and ordered identity histories;
- no remote write under `local_commit`;
- read-only source divergence reporting under `local_commit` without implied
  publication authority, plus an explicit unavailable reason when no source
  exists;
- one post-convergence expected-old fast-forward publication;
- rejection of non-fast-forward or changed expected remote heads;
- cross-clone publication race with one winner and one preserved blocked
  candidate;
- post-push exact-ref readback;
- non-converged local/remote divergence and unpushed-commit reporting;
- authorized origin-visible review and rejection of unlisted mechanisms; and
- fork pull-request head-repository and fully qualified ref targeting.

Result-blind forward evaluations include:

- a clean initial candidate;
- a correctness defect requiring one fix;
- a fix that introduces a new solution-level issue;
- an unsafe simplification proposal;
- a code-simplicity finding that converges;
- the same finding surviving its claimed fix;
- a scope-expanding proposed fix;
- a deterministic validation failure with and without a tractable correction;
- unavailable, environment-caused, and unattributable validation failures that
  block without speculative remediation;
- an interrupted invocation resumed from its checkpoint;
- a reviewer that attempts to modify the candidate;
- a stale remote head;
- a publication race;
- a non-converged candidate with unpushed commits; and
- an origin-only mechanism with and without a valid grant.

Repository-wide checks remain:

```bash
just format
just lint
just test
```

## Trade-offs

### Benefits

- Makes interrupted and piecemeal review remediation first-class.
- Centralizes convergence behavior without weakening read-only review skills.
- Uses local isolation and Git-native publication guards already available in
  the operating environment.
- Keeps the common local path understandable and implementable.
- Detects remote races without silently overwriting another candidate.
- Allows caller migrations to be evaluated independently after the skill is
  stable.

### Costs and accepted limitations

- Fresh reviewer contexts add startup, token, and latency cost.
- Deny-write enforcement depends on runtime capabilities and fails closed when
  unavailable.
- Two unrelated clones may perform redundant local work before one loses the
  publication race.
- Cooperative caller ownership is a workflow contract, not a distributed
  transaction.
- A crash may require explicit operator reconciliation when live Git and the
  checkpoint do not identify one safe continuation.
- Caller-specific duplicated loops remain temporarily until their fast-follow
  migrations are completed.

These limitations are acceptable for the controlled operating environments
targeted by the initial skill. A distributed coordination system would require a
separate demonstrated use case and a separate design.

## Rejected alternatives

**Add a distributed ownership or coordinator service.** This is outside the
scope of the skill and disproportionate to the observed operating environment.
Local locking plus expected-old Git publication provides the required safety
without new infrastructure.

**Keep the loop duplicated indefinitely.** This preserves the current state but
does not support standalone resumption and allows convergence behavior to drift.

**Add mutation to `review-code-change`.** This collapses reviewer and
implementation contexts and weakens read-only integrity.

**Add a read-only mode or permit zero fix cycles.** Existing review skills
already own that use case.

**Include focused or arbitrary lens subsets initially.** No demonstrated
consumer requires them, and they complicate convergence semantics.

**Migrate all callers inside the implementation epic.** This combines a new
contract with several lifecycle migrations and makes failures difficult to
attribute. Caller migrations are dependent fast follows.

**Fold CI or external feedback into the skill.** That duplicates `babysit-pr`
and creates competing PR-lifecycle owners.

**Teach the skill stack semantics.** That duplicates `carve-changesets` lineage
and equivalence responsibilities.
