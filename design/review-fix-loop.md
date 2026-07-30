# Review Fix Loop Design

Status: proposed\
Date: 2026-07-29

## Decision summary

Add a repository-owned `review-fix-loop` skill that takes exclusive ownership of
an existing mutable candidate, runs the complete repository-owned review suite,
applies material ticket-scoped fixes, validates and commits the resulting head,
and repeats until the full review converges or a bounded stop condition is
reached.

The skill owns remediation and convergence. It does not replace
`review-code-change` or any individual review lens. It does not implement the
original ticket, create a pull request, watch CI or external feedback, determine
merge readiness, merge, transition a tracker item, deploy, or clean up branches
and worktrees.

`review-fix-loop` always operates with fix authority. It has no read-only mode,
and its fix-cycle budget must be at least one. Users who want a read-only review
should invoke `review-code-change` or an individual review lens directly.

Fix cycles are local by default. When the candidate has a pushable source, the
skill accumulates fix commits locally and pushes them once, only after the full
review converges. It may expose an intermediate head remotely only when a
required review or validation mechanism demonstrably cannot evaluate the local
candidate. A non-converged handoff must prominently identify every unpushed
commit and the exact local/remote divergence.

Local-only runs fence one local candidate and make no cross-clone claim. Any
invocation that owns or updates an existing remote ref requires an explicitly
configured, authorized shared ownership provider. Delegated composition also
requires a successor to delegated-execution v2 for recoverable coordinator
responses, constrained base revisions, and atomic terminal handoff.

## Context

The repository currently divides review responsibilities correctly but repeats
the mutating half of the workflow:

- `review-code-change` builds and validates one evidence packet, runs the
  repository-owned lenses, and returns one read-only aggregate result.
- `implement-ticket` owns the initial fix, validation, commit, and re-review
  loop before publication.
- `babysit-pr` owns the same repository-review remediation behavior after a
  published candidate changes.
- `carve-changesets` applies accepted review fixes to local changeset candidates
  and rebuilds invalidated chain evidence.

The repeated behavior is useful outside those larger workflows. An
implementation may be interrupted after the candidate exists but before its
review converges, or an operator may intentionally implement and review in
separate tasks. Invoking `implement-ticket` again is too broad because it also
owns readiness, initial implementation, publication-path selection, tracker
lifecycle, and cleanup. Invoking `review-code-change` is too narrow because it
must remain read-only.

The missing abstraction is a candidate-remediation workflow between those two
levels.

## Goals

`review-fix-loop` must:

01. Resume from live repository and optional pull-request state without
    requiring an uninterrupted `implement-ticket` transcript.
02. Prove exact candidate identity and exclusive mutation ownership before
    making a change.
03. Use the complete repository review suite as the sole initial review mode.
04. Apply only material, evidenced, ticket-scoped findings.
05. Validate and commit every accepted fix before reviewing the new head.
06. Invalidate all head-bound evidence after every candidate change.
07. Bound automatic remediation by a clear fix-cycle budget and stronger
    non-convergence stop conditions.
08. Return a candidate-bound result that larger skills can validate and consume.
09. Preserve the existing meaning of a full-suite `clean` result.
10. Work on a committed local candidate or an exclusively owned existing pull
    request branch.
11. Keep intermediate fixes local until convergence unless required review or
    validation evidence can only be obtained from a remote candidate.
12. Run each review pass in a newly created read-only reviewer subagent by
    default when the operating runtime supports it.

## Non-goals

The skill must not:

- discover, select, or implement the original ticket;
- turn an uncommitted worktree into an inferred candidate;
- provide a read-only or zero-fix-cycle mode;
- create an initial branch, worktree, or pull request;
- push an intermediate fix merely because the candidate has a remote branch;
- watch or retry CI;
- collect, reply to, or resolve human, connector, or inline review feedback;
- decide that a pull request is ready to merge;
- merge, deploy, transition tickets, close epics, or delete branches or
  worktrees;
- weaken `review-code-change` by allowing a partial lens run to return a
  certifying aggregate `clean`;
- reuse the mutating implementation context as the reviewer when fresh subagents
  are available, unless the caller explicitly requests that override;
- own stack decomposition, immutable-source lineage, or changeset propagation;
  or
- apply deferred, speculative, cosmetic, sibling, or parent-epic work.

## Architectural position

The proposed dependency graph is:

```text
implement-epic
└── implement-ticket
    ├── review-fix-loop             # initial candidate convergence
    │   └── review-code-change      # complete certifying review
    ├── babysit-pr
    │   └── review-fix-loop         # repository review after published changes
    └── carve-changesets
        ├── review-fix-loop         # per-changeset convergence, when integrated
        └── babysit-pr
            └── review-fix-loop

standalone review-fix-loop
└── review-code-change
```

The graph remains acyclic:

- `review-fix-loop` never invokes `implement-ticket`, `implement-epic`,
  `babysit-pr`, or `carve-changesets`.
- Review skills remain read-only and never invoke `review-fix-loop`.
- Callers transfer exclusive candidate mutation ownership to `review-fix-loop`.
  Before a composed terminal handoff, the loop durably transfers the fenced
  lease directly back to the named caller; standalone invocations release it.

## Responsibility boundary

### `review-code-change`

Continues to own:

- construction and validation of the shared evidence packet;
- full-suite lens order;
- lens-result validation;
- simplification proposal disposition;
- finding reconciliation and deduplication;
- aggregate verdict semantics; and
- read-only candidate integrity.

It returns findings and the next required action. It never applies a fix.

### Individual review lenses

Continue to own their existing rubrics and shared result shapes. They remain
read-only and available to users through their existing skills. They are not
direct dependencies or independently selectable modes of the initial
`review-fix-loop`. A future focused-remediation extension requires a
demonstrated consumer and a separate design revision.

### `review-fix-loop`

Owns:

- candidate and authority resolution for the remediation interval;
- reviewer-context selection and isolation;
- finding verification and disposition;
- the smallest sufficient ticket-scoped edits;
- affected and required validation after edits;
- fix commits;
- under `update_pr`, one post-convergence push to an already existing,
  exclusively owned pull-request branch, plus only those intermediate pushes
  authorized for invocation-enumerated remote-only mechanisms;
- evidence invalidation and reconstruction after every new head;
- cycle accounting and convergence detection; and
- its terminal result.

### Calling workflow

Continues to own:

- original ticket selection, readiness, implementation, and acceptance;
- any external review or CI findings that caused the candidate to change;
- publication-path selection and initial pull-request creation;
- pull-request watching, remote gates, feedback communication, and merge;
- stack topology, immutable-source lineage, and propagation;
- tracker, deployment, mainline, and cleanup outcomes; and
- validation of the `review-fix-loop` handoff against live state, including
  rebuilding any required acceptance evidence invalidated by the returned head.

## Invocation contract

The exact serialized schema should be designed during implementation, but the
logical invocation contains the following sections.

### Candidate

- repository identity;
- dedicated local candidate branch and globally clean invocation-owned worktree;
- exact committed head SHA;
- exact comparison-base SHA and base branch;
- complete `base...HEAD` diff;
- tracked, staged, unstaged, untracked, and ignored worktree state;
- optional existing pull-request identity;
- when a pull request exists, its exact head repository, authenticated remote
  identity and URL, fully qualified head ref, expected remote-head object ID,
  base repository, fully qualified base ref, and live base object ID;
- when remote-ref exclusivity or `update_pr` is requested, the resolved
  authoritative provider binding, capability version, canonical provider
  instance identity, authenticated access boundary, supported operation set, and
  exact lease key.
- evidence that all intended candidate changes are committed.

Every mutating invocation requires a dedicated globally clean worktree. A dirty
worktree, including unrelated tracked or untracked artifacts, blocks startup;
the skill must not guess ownership, hide artifacts behind “candidate-clean,” or
run mutation-capable commands beside user work. When a remote source exists, the
initial capture also establishes which local commits, if any, are already ahead
of that exact fully qualified ref.

### Change contract

- observable goal;
- acceptance criteria;
- explicit non-goals;
- behavior and invariants to preserve;
- applicable repository instructions and named specifications;
- representative nearby code and tests; and
- allowed fix scope.

When invoked by another skill, this material should come from its already
resolved live contract. For standalone use, `review-fix-loop` reconstructs it
from current user instructions, live ticket or pull-request state, native
relationships, repository contracts, code, and tests. Missing essential intent
is a blocker, not permission to infer requirements from the implementation. A
tracker identity is optional when the user supplies a complete observable change
contract with the same required goal, acceptance, non-goals, preserved behavior,
source, and validation evidence.

### Acceptance reconciliation

The caller retains its complete acceptance ledger and all criterion-specific
semantics. The loop does not import, checkpoint, revise, or return that ledger.
Its invocation instead records whether the caller has candidate- or base-bound
acceptance evidence whose currency may be affected.

The terminal result returns exact initial and final candidate/base identities,
validation evidence produced by the loop, and two ordered histories:

- `head_history` begins with the captured initial candidate head, records every
  promoted canonical candidate head in order, and ends with the final candidate
  head.
- `base_revision_history` begins with the captured comparison base, records
  every effective base change in order, including standalone and local changes,
  and ends with the comparison base used by the terminal review result.

Neither history repeats an unchanged identity. Both are present in every
terminal variant, independent of whether a coordinator exists. When
coordinator-backed invocation revisions also record a base history, it must
exactly match `base_revision_history`.

The result also contains:

```text
acceptance_reconciliation_required: true | false
```

The value is `true` whenever either ordered history contains an identity after
its initial entry, or when the loop cannot prove from caller-supplied identity
metadata that no acceptance evidence is bound to the candidate and base
identities. The caller then applies its own acceptance-ledger retention,
invalidation, and rebuilding rules before claiming readiness. Review convergence
never implies ticket acceptance.

### Review scope

The initial skill has one review mode: invoke `review-code-change` and require
its complete repository-owned sequence and aggregate result. The loop never
invokes individual lenses directly, never constructs a partial aggregate, and
never returns focused convergence.

This keeps lens order, simplification-proposal disposition, stop-on-first-gating
behavior, deduplication, and conflict resolution wholly inside
`review-code-change`. After every new head, the loop supplies a new raw packet
to a fresh complete review and does not retain old-head lens evidence.

Direct read-only lens skills remain available outside the loop. Focused
remediation, custom subsets, or a focused-then-full optimization are deferred
until a concrete consumer justifies their additional orchestration and terminal
semantics.

### Review execution context

The default execution mode is `fresh_subagent`.

When the operating runtime supports subagents or an equivalent newly isolated
reviewer context:

- every review pass is delegated to a newly created read-only reviewer;
- the reviewer receives the validated raw evidence packet and only the minimum
  trusted operating instructions needed to run the complete review;
- the reviewer does not inherit the implementation transcript, intended fix,
  prior conclusions, suspected findings, or expected evaluation outcome;
- the reviewer receives no mutation, commit, push, communication, merge, or
  tracker authority; and
- the reviewer context is discarded after returning its result and is never
  reused for another candidate head or fix cycle.

One fresh aggregate-review subagent runs `review-code-change` and its
repository-owned orchestration contract. The three nested lenses may share that
aggregate-review subagent; they do not need separate subagents. The aggregate
subagent is the independence boundary. Filesystem deny-write enforcement,
mutation-tool exclusion, remote-write removal, before/after integrity capture,
and mutation-attempt auditing apply to the entire nested review call tree.

The aggregate reviewer runs nested lenses in its own context by default. It may
create descendant reviewer contexts only when the runtime proves that each
descendant inherits the same immutable deny-write filesystem boundary,
mutation-free tool surface, and absence of remote-write credentials. Record
every descendant identity and capability attestation and include its tool trace
in the aggregate integrity audit. If capability inheritance or descendant
auditing cannot be proven, further delegation is prohibited. Local candidate
fingerprints alone are insufficient because a descendant could mutate remote or
out-of-tree state without changing the candidate.

Record reviewer isolation on two independent dimensions:

```text
review_independence: fresh_subagent | in_agent_override
write_isolation: enforced | verification_only | violated
```

The invocation may select `in_agent` only through an explicit current-user or
caller-authorized override whose authority is recorded in the invocation. This
is never an automatic fallback or optimization. It relaxes reviewer independence
but never write isolation. The terminal result records the override, and
downstream callers may reject it when their repository or readiness contract
requires an independent context.

When the runtime cannot create a fresh subagent or equivalent isolated context
and the invocation does not already contain that explicit override, the skill
fails closed with `blocked/missing_capability`. It does not solicit, infer, or
manufacture an override after starting the loop.

### Reviewer write prevention and integrity

“Read-only” is a capability boundary, not merely prompt language. A review
result is trustworthy only when the caller both instructs the reviewer not to
mutate and enforces or verifies that constraint.

Use the strongest controls the runtime supports, in this order:

1. Run the reviewer against an immutable snapshot or a filesystem mounted
   read-only at the captured candidate.
2. Apply a deny-write sandbox to the candidate repository and its Git metadata.
3. Restrict the reviewer tool set so it has no edit, patch, file-write, commit,
   push, review-posting, or other mutation tool.
4. When a shell is required for search or inspection, restrict it to read-only
   commands. Do not allow formatters, generators, dependency installation, test
   commands that write fixtures or snapshots, or other mutation-capable
   validation. The reviewer should consume the exact validation evidence in the
   packet rather than rerun a command whose write behavior is uncertain.
5. Capture and compare candidate integrity before and after review: HEAD, refs,
   commit history, index, tracked, staged, unstaged, untracked, and ignored
   state, plus content identities where the runtime can record them.
6. Inspect the reviewer tool trace for attempted mutation when the runtime
   exposes it.

The reviewer task and the invoked review-skill instructions must both state,
prominently and unambiguously:

- review and report findings only;
- do not edit, format, generate, delete, rename, or create files;
- do not apply any proposed fix;
- do not commit, amend, rebase, push, or mutate refs;
- do not post, reply to, resolve, approve, or otherwise mutate remote review
  state; and
- return the structured review result to the mutating caller, which alone owns
  implementation.

Prompt reinforcement is defense in depth and never substitutes for tool,
filesystem, or integrity controls.

An attempted prohibited mutation is a reviewer-integrity failure even if the
runtime blocks it before the worktree changes. A detected worktree, Git, or
remote mutation also invalidates the entire review result. Stop the loop and
return `blocked` with the attempted action, before/after evidence, reviewer
identity, and affected paths or refs. Preserve unexpected changes for operator
inspection; never reset, delete, revert, or silently incorporate them.

The same write-prevention rules apply to an explicit `in_agent` review. The
minimum write isolation for a certifying result is an enforced deny-write
candidate boundary plus removal or blocking of mutation-capable tools and remote
writes. Before/after integrity verification is mandatory defense in depth, not a
substitute.

If the runtime offers only before/after verification, it cannot produce a
certifying result or authorize publication. The invocation returns `blocked`
with `blocker_kind: missing_capability`. `write_isolation: violated` always
blocks.

### Invocation identity and checkpoint

The fix-cycle budget and convergence history belong to one invocation, not to
one agent turn or process. Each invocation receives an immutable
`invocation_id`, an ownership epoch, and one original budget. The caller
generates the invocation ID with collision-resistant uniqueness. The durable
invocation registry rejects reuse of that ID with a different root-invocation
digest or identity tuple; recovery and redelivery must reuse the original ID and
root digest exactly.

Maintain a candidate-bound checkpoint snapshot plus an append-only monotonic
phase journal. The checkpoint contains:

- invocation ID and ownership epoch, plus active worker identity/epoch/token
  when the runtime can redeliver work;
- active candidate-effect operation ID, token, matcher, and state when one is
  reserved;
- repository, worktree, branch, initial head, and current head;
- optional exact remote and pull-request identities;
- complete-review requirement, execution policy, publication policy, and
  authority ceiling;
- an immutable allowlist of mechanism-specific remote-iteration grants when
  `update_pr` requires origin-visible evaluation;
- original fix-cycle budget and consumed attempts;
- ordered head sequence and phase transitions;
- finding dispositions, failed-attempt artifacts, and validation outcomes; and
- current mutation owner, explicit release, or explicit takeover receipt.

The journal uses phase-specific records for every cross-boundary transition that
cannot be atomically combined:

- fix-attempt reservation;
- candidate-effect reservation, observation, or reconciliation;
- provisional commit creation;
- canonical-branch promotion;
- remote publication;
- coordinator acknowledgement; and
- terminal body and atomic ownership transfer or release.

Fix-attempt reservation is a single atomic journal append and is itself the
authoritative budget-consumption event; it is not represented as a
`prepared`/`observed_complete` pair. All other phases write `prepared` before
proposing the effect and `observed_complete` only after independently reading
the authoritative resulting state.

A `prepared` record contains a phase-specific effect matcher, not an exact
post-state object ID when that identity cannot exist yet. Provisional commit
creation records the attempt ID, exact parent, intended tree identity, commit
message digest, relevant identity/signing policy, and an invocation-owned
provisional ref. The attempt performs commit creation only on that ref. Recovery
accepts a commit only when the ref and every recorded invariant match; hooks,
signing, or other behavior that makes the effect unidentifiable blocks recovery.
Promotion and publication records can name exact proposed object IDs because the
provisional commit already exists.

Sequence numbers, invocation ID, attempt ID when applicable, ownership epoch,
fencing token, active worker epoch/token and candidate-effect operation/token
when applicable, pre-state identity, phase-specific effect matcher, and
applicable coordinator request identity bind every record.

A terminal-handoff `prepared` record contains `terminal_body_v1` and its digest.
For provider-backed composition, `observed_complete` is written only after
`read_handoff` returns the matching authorization and transfer receipts. For
local composition, it is written only after the durable body and local lease
record return the matching local receipt. The authoritative lease transaction,
not the journal projection, determines whether ownership transferred.

The checkpoint snapshot is a compact projection of the journal; it never claims
that Git refs, remote refs, and local state changed in one atomic transaction.

This checkpoint is authoritative only for invocation continuity, budget
accounting, and recorded ownership history. The applicable local lease or shared
provider is authoritative for the current owner, epoch, and fencing token. Live
Git, tracker, pull-request, and repository state remain authoritative for the
candidate itself. The checkpoint cannot grant new authority or make stale
candidate evidence current.

A resume must match both the checkpoint and live candidate state. Ownership
transfer or stale-owner takeover requires an explicit epoch transition against
the last verified head. Missing, malformed, or mismatched checkpoint data cannot
silently reset the budget or claim to resume. The operator may explicitly start
a new invocation with a new budget, but callers must never chain invocations
automatically to evade exhaustion.

### Fix-cycle budget

The serialized invocation requires `max_fix_cycles` as an integer from `1`
through `10`. Interactive entrypoints default it to `3` before creating the
invocation. The resulting value is immutable for that invocation.

The initial review does not consume a fix cycle. Reserve and consume one cycle
immediately before the first mutation of a fix attempt. The attempt remains
consumed whether it validates, commits, fails, or is interrupted. A successful
cycle:

1. a trustworthy review produces an actionable material finding;
2. the skill applies one or more accepted fixes;
3. required validation runs;
4. a new committed candidate head is created; and
5. fresh review begins for that new head.

If the complete review is already converged on the initial head, the skill
returns without creating an artificial change or consuming a cycle.

The skill never starts another automatic fix after the configured budget is
exhausted. Failed validation cannot create an unbounded sequence of free
attempts. The final result preserves unresolved findings, failed-attempt
artifacts, and the candidate at its last clean committed head.

### Publication policy

- `local_commit`: fixes may be committed only in the local candidate worktree.
  No remote write is permitted.
- `update_pr`: fixes are committed locally during the loop. After the requested
  complete review converges, the complete fast-forward commit range is pushed
  once to the fully qualified head ref in the exact head repository of an
  existing pull request owned exclusively by this invocation.

The skill does not create a pull request. `update_pr` authority does not imply
force-push, review communication, merge, ticket transition, deployment, or
cleanup authority. It also does not authorize routine per-cycle pushes.

An intermediate push is permitted only under `update_pr` and only when a
required reviewer, validation command, or repository gate cannot evaluate the
local candidate and requires an origin-visible head. Before the invocation
starts, its immutable `remote_iteration_grants` allowlist must enumerate each
authorized mechanism by stable identifier and kind, the exact head repository
and fully qualified ref it may inspect, and evidence of the dependency's
origin-only limitation. Sufficient evidence is either an authoritative
repository/tool contract declaring that limitation or a recorded read-only
capability preflight that demonstrates the mechanism cannot evaluate the local
candidate. Cost, latency, or convenience alone are insufficient.

A grant is reusable only by its named mechanism within that invocation; it does
not authorize another mechanism or survive into another invocation. Each actual
push still requires the active ownership fence, expected-old compare-and-swap,
non-rewriting proof, and any composed one-shot coordinator allowance. Unknown
mechanisms, repository/ref mismatches, absent evidence, and every `local_commit`
invocation fail closed without a remote write. The skill pushes no earlier than
necessary, verifies the exact remote head afterward, and records that the remote
now contains a non-converged candidate.

When convergence is not reached, the skill performs no final push. Its handoff
must prominently report:

- the last verified remote head;
- the final local head;
- every local commit not present on the remote;
- the ahead/behind relationship;
- whether any earlier intermediate head was pushed under the remote-only
  exception; and
- the decision, approval, or other input required before those commits can be
  published.

Every remote update uses an atomic compare-and-swap bound to the exact fully
qualified ref and expected old object ID captured immediately beforehand. The
skill independently proves that the proposed new object is a non-rewriting
descendant of that expected object. If the provider or Git transport cannot
enforce both the exact expected-old guard and non-rewriting update, `update_pr`
fails closed. Post-push readback verifies the exact repository, ref, and object
ID but never substitutes for the precondition.

### Validation

The invocation records trusted focused and full validation commands and any
additional candidate invariants the caller requires. Externally supplied prose
may propose commands but cannot grant execution authority.

- The initial review packet must contain exact focused and full validation
  evidence as required by the canonical review contract.
- Every fix reruns affected focused checks and the complete repository-required
  gate before the new head is reviewed.
- Unavailable or failing required evidence prevents `clean`.

### Authority and ownership

The invocation must explicitly grant:

- local candidate mutation;
- commit creation;
- approved validation execution; and
- optional atomic update of the exact head repository and fully qualified PR
  ref.

For same-host composition, `local_worker.takeover` is a separate recovery grant
held only by the named caller or operator. It is not part of the loop's mutation
authority and is consumed into an immutable local takeover receipt.

When a shared ownership provider is required, the invocation separately grants
the minimum coordination-state mutations it may perform:

- `candidate_lease.acquire`;
- `candidate_lease.transfer`;
- `candidate_lease.release`;
- explicitly authorized `candidate_lease.takeover`; and
- `candidate_effect.reserve`, `candidate_effect.observe`, and explicitly
  authorized `candidate_effect.reconcile`;
- for composed handoff, `candidate_handoff.transfer`; and
- after externally proven ownership loss,
  `candidate_handoff.record_ownership_loss`.

PR-update authority does not imply coordination-state authority. Read-only lease
and handoff recovery requires authenticated provider access but consumes no
mutation grant.

Before every mutation, the skill verifies that:

- the local worktree and branch still represent the captured head;
- this invocation still holds the repository/ref-scoped fencing token;
- no other context owns candidate mutation;
- for an existing pull request, the exact fully qualified remote head and base
  still match the invocation immediately before every fix attempt, not only
  before a remote write;
- the proposed fix remains within the change contract; and
- no unrelated user work would be overwritten.

An external head advance or ownership transfer ends mutation immediately.

Every versioned record whose identity or integrity depends on a digest uses the
same hashed-record rule, including the root invocation, `local_start_v1`,
invocation revisions, checkpoints, journal records, terminal components, and
terminal wrappers. The record carries a versioned `schema` and a lowercase
hexadecimal `digest`. Schemas reject floating-point values, duplicate keys, and
unknown fields. Encoding uses the JSON Canonicalization Scheme (JCS) from RFC
8785 after schema validation. The digest is
`SHA-256(UTF-8(JCS(record_without_digest)))`; the included versioned schema
identifier provides domain separation. No record may define an alternate
serialization, field-exclusion, or digest rule unless a future schema version
states it explicitly.

Remote-ref exclusivity comes from a caller- or runtime-owned shared ownership
provider, never from the skill-local journal. The provider is an authenticated,
durable, linearizable CAS service or command adapter reachable from every clone
that may operate on the candidate. It owns:

- one authoritative binding namespace from canonical head-repository identity to
  exactly one provider instance and configuration revision;
- canonicalization of a key containing only head-repository identity and fully
  qualified remote candidate ref;
- `read`, `acquire`, `validate`, `transfer`, `release`, and explicit `takeover`
  operations;
- atomic effect reservation, observation, and reconciliation operations;
- idempotent `record_ownership_loss_terminal` for a receipt-proven former owner;
- authenticated `read_ownership_loss_terminal` by deterministic record ID;
- monotonically increasing ownership epochs and opaque fencing tokens;
- immutable operation receipts addressable by invocation and request ID; and
- the composed terminal-handoff records defined below.

Every provider response binds provider identity and capability version, lease
key, invocation, owner, epoch, fencing token, expected prior epoch, request ID,
candidate head/base, operation, and resulting state. Mutations use atomic
expected-epoch CAS. Abandoned ownership is not inferred from elapsed time:
takeover requires explicit caller authority, the exact observed epoch and
candidate, and an immutable takeover receipt.

Token validation and a candidate effect are one fenced phase, not a
check-then-act pair. Before changing files, creating or promoting a commit, or
updating a ref, the loop atomically reserves one `candidate_effect_v1` against
the current lease and active-worker tokens. The reservation binds a stable
operation ID, exact expected candidate and base identities, effect kind,
permitted paths or fully qualified ref, and enough proposed post-state metadata
to reconcile the effect. While it is active, the same provider or local lease
implementation rejects lease release, transfer, takeover, worker takeover, and
any second candidate effect.

The loop executes only the reserved effect, then observes the authoritative Git
and worktree state and atomically records the outcome before clearing the
reservation. A remote update still uses the exact expected-old Git ref CAS and
ancestry rule, but the provider reservation remains active across that CAS and
readback. Same-host file, index, ref, and commit mutations remain under the
equivalent non-transferable local reservation for the entire transactional fix
attempt.

A crash leaves the reservation durable. Recovery must first determine whether
the exact effect occurred, did not occur, or is ambiguous. The current owner may
finish observation; a separately authorized caller or operator may use only
`candidate_effect.reconcile` to record a provable outcome. No takeover or new
mutation can proceed until reconciliation clears the reservation. Ambiguity
returns `blocked/candidate_integrity_failure` without transferring ownership.
Elapsed time never clears an active effect. Consequently, once ownership or the
active-worker epoch changes, the old token cannot still have an in-flight or new
candidate effect.

The invocation does not choose a provider instance. It records the result of
resolving the canonical repository through repository policy or one
host-controlled provider registry trusted by every participating clone.
Resolution returns one provider identity, endpoint or command capability,
configuration revision, and authentication policy. Missing, ambiguous, or
conflicting bindings fail closed before ownership acquisition. The provider
rejects lease keys for repositories outside its binding and receipts from a
different configuration revision.

The first supported remote adapter co-locates coordinator and ownership state in
one successor service and one transaction domain; its allowance verifier is
therefore the same authenticated service that executes the lease operation.
Cross-service allowance verification is a future extension and is unsupported
until a provider binding pins the issuer and audience and defines authenticated
receipt verification. Merely injecting two “compatible” endpoints is never
sufficient.

Two clones of the same remote contend on the same provider key. A second lock
keyed by Git common directory and local ref guards same-clone worktrees but does
not replace the shared provider. A local-only invocation, including a
`local_commit` run that does not claim ownership of the remote ref, uses only
the common-directory/local-ref fence, continuously rereads any observed remote,
and reports `ownership_scope: local_candidate`. It cannot publish or claim
cross-clone exclusivity.

Any invocation using `update_pr`, and any composed invocation whose caller
transfers ownership of an existing PR ref, requires the shared provider and
reports `ownership_scope: remote_ref`. Missing discovery metadata, unsupported
capability version, unauthenticated access, unavailable linearizable read/CAS,
an ungranted provider mutation, or a receipt mismatch returns
`blocked/missing_capability` or `blocked/missing_authority` before candidate
mutation. The initial implementation may therefore support standalone
`local_commit` without a provider while failing closed for standalone
`update_pr` until one is configured.

The first composed production adapter uses the successor coordinator's durable
state service as the shared provider, with lease and handoff operations defined
in that versioned capability. Standalone `update_pr` has no implicit default
provider; it remains disabled unless repository policy or the host registry
resolves the same compatible authoritative service. A test double can prove the
protocol but does not authorize production remote-ref ownership.

Acquire, transfer, take over, and release each applicable lease through the
provider's atomic ownership-epoch compare-and-swap. Every mutating phase and
checkpoint transition carries the current lease, active-worker, and
active-effect tokens. Local file locking may implement the same-host fast path,
but it must enforce the same non-transferable effect reservation and does not
replace provider epochs or remote-head checks.

Before every review, remote update, and terminal return, reread the current head
and base. When only the base advances, apply the canonical review-suite drift
rules: retain evidence only when the effective diff and resulting tree are
unchanged, no conflict or relevant overlap exists, repository policy permits
retention, and the decision is recorded. Otherwise invalidate affected
validation and review evidence and rebuild it against the current base. No
terminal convergence or publication claim may cite a stale comparison base.

In a composed invocation, base drift also changes the outer authority binding.
The loop may continue only through an explicit coordinator-approved
`candidate_base_rebind` transition. It creates the constrained invocation
revision defined below. When the coordinator protocol cannot rebind a base, any
base advance ends the composed loop with `blocked/base_drift`; the caller may
start a fresh outer invocation against the new base. The loop never certifies
against the stale base merely to satisfy an older caller contract.

### Local composed ownership return

Ordinary non-delegated `implement-ticket` composition is a controlled same-host
case: caller and loop share one Git common directory, invocation-state
directory, and local lease implementation. It does not require a remote provider
or coordinator.

The local lease record is keyed by Git common directory and canonical local
candidate ref and contains owner, monotonic epoch, opaque token, invocation ID,
candidate head/base, and optional terminal-handoff reference. For terminal
ingress, the caller:

1. stops candidate mutation and constructs the immutable invocation, initial
   checkpoint, budget, authority ceiling, candidate snapshot, intended loop
   owner, and invocation digest;
2. durably writes a `local_start_v1` record under the shared invocation-state
   directory;
3. atomically compare-and-swaps the local lease from the caller epoch to a
   loop-owned epoch while attaching the start-record digest; and
4. only after observing that transfer receipt, dispatches or resumes the loop.

The loop may mutate only after reading the same start record, candidate
identities, and loop-owned lease receipt and atomically claiming the
invocation's active-worker slot. The claim adds a worker identity, monotonically
increasing worker epoch, and opaque worker token to the local lease. Every
candidate mutation, budget reservation, journal append, promotion, and handoff
must carry both the invocation fencing token and current worker token.

A crash before ingress CAS leaves caller ownership. A crash after CAS but before
dispatch leaves a durable `transferred_not_started` invocation. The caller may
redeliver only that exact invocation without changing its budget or authority;
duplicate workers race for one atomic claim, and only the winner may execute.
Redelivery while a claim exists observes the active invocation and performs no
mutation. A dispatch timeout alone never authorizes replacement. If the claimed
worker is gone, only the original caller or an explicit operator holding the
invocation's `local_worker.takeover` grant may authorize replacement. The retry
worker cannot authorize its own takeover. The operation atomically
compare-and-swaps the exact invocation ID, candidate head/base, local lease
epoch/token, active worker identity/epoch/token, and journal sequence;
increments the worker epoch; installs a new opaque worker token; and persists an
immutable receipt naming the authorizer and replaced and replacement workers.
The receipt is included in the terminal body's worker-claim history. The old
token is invalid before another worker resumes. The caller must not mutate the
candidate or silently create a replacement invocation.

For terminal return, the loop:

1. constructs the local terminal body defined below;
2. durably writes it under the invocation-state directory using atomic
   create-or-replace and records its digest;
3. atomically compare-and-swaps the local lease from the loop epoch to the
   caller-owned epoch while attaching a local transfer receipt that references
   that digest; and
4. returns `terminal_envelope_v1` with null handoff authorization and that local
   transfer receipt.

A crash before the lease CAS leaves loop ownership and a harmless prepared body;
resume may verify and reuse it. A crash after the CAS leaves caller ownership;
the caller reads the body and receipt by invocation ID and resumes without loop
response delivery. The loop never reacquires a successfully returned lease. The
caller validates the candidate identities and digest against live Git before
mutation.

This protocol is intentionally limited to one host and one Git common directory.
If caller and loop cannot share the atomic local lease and durable
invocation-state directory, local composition returns
`blocked/missing_capability` or uses an explicitly configured shared provider.
It does not add distributed coordination to the common local path.

### Terminal handoff envelope

Local and provider-backed ownership return use one logical versioned envelope
with three non-overlapping layers:

1. `terminal_body_v1` is sealed before transfer. It contains every fact already
   knowable: terminal state, invocation and budget history, candidate and base
   identities, review and validation evidence, the ordered head and
   base-revision histories, the acceptance-reconciliation-required flag, commits
   and failed attempts, publication and unpushed-commit state, unresolved work,
   invocation journal sequence, effective invocation revision, pre-transfer
   owner/epoch, intended return owner, and the authority-ledger prefix. For
   provider composition it also contains the deterministic handoff ID. It
   explicitly excludes the transfer authorization, final coordinator
   sequence/token, returned owner/epoch/token, final authority ledger, and
   transfer receipt.
2. `handoff_authorization_v1` is `null` for the same-host local protocol. For a
   provider-backed composed return without an outer coordinator, it is also
   `null`; the provider instead validates the invocation's explicit
   `candidate_handoff.transfer` grant. When an outer coordinator exists, it is
   the recovered coordinator allowance for the exact handoff ID, body digest,
   and transfer effect, including the resulting sequence, continuation token,
   and authority entry.
3. `ownership_transfer_v1` is itself the atomic local-lease or provider receipt,
   not a wrapper containing another receipt. It contains the body digest,
   optional authorization digest, provider handoff ID or explicit null, returned
   owner/epoch/token, lease identity, operation ID, and resulting state.
   Candidate head/base and previous owner/epoch/token may appear only as
   explicitly named `asserted_*` CAS bindings. Those assertions are audit
   evidence, not a second authoritative source, and must exactly equal the
   corresponding `terminal_body_v1` values.

`terminal_envelope_v1` contains those three objects without copying their
fields. Every component uses the repository-wide hashed-record rule above:
schema validation followed by RFC 8785 JCS encoding and
`SHA-256(UTF-8(JCS(component_without_digest)))`.

The envelope itself uses that same hashed-record rule over its schema identifier
and three component objects. There is no wrapper-specific digest algorithm.

The final coordinator sequence/token come only from `handoff_authorization_v1`;
the returned owner/epoch/token come only from `ownership_transfer_v1`; and final
`authority_used` is exactly the body prefix plus the authorization entry when
present. The provider must reject transfer unless the receipt's returned owner
equals the body's intended return owner and, when authorization is present, the
coordinator-authorized intended caller. Envelope validation independently
enforces the same equality. Unknown fields, copied projections of authoritative
values, assertion mismatch, owner mismatch, digest mismatch, or a receipt
inconsistent with the body is invalid. Named `asserted_*` receipt fields are
permitted only for the CAS bindings defined above. Local and provider callers
use the same deterministic projection; authorization presence reflects whether
an outer coordinator exists, and the transfer-receipt type reflects the lease
implementation.

A non-composed invocation returns `standalone_terminal_v1`, containing
`terminal_body_v1`, one `ownership_release_v1` component that is itself the
atomic local or provider release receipt. The wrapper uses the common
hashed-record rule over its schema identifier and two component objects.

It has no handoff authorization, return owner, or copied ownership fields. This
keeps standalone release explicit without pretending it is a caller handoff.

If a live lease read proves that ownership already transferred externally, the
former owner cannot manufacture a release or return transfer. It instead returns
`ownership_loss_terminal_v1`, containing a `terminal_body_v1` whose outcome is
`blocked/ownership_lost`, one `ownership_loss_evidence_v1`, and the wrapper
digest produced by the common hashed-record rule. The evidence is the
authenticated linearizable lease observation plus the provider or local
takeover/transfer receipt when one exists. It binds the invocation, lease key,
last loop-owned epoch/token, observed successor owner/epoch/token, candidate
head/base, operation identity, and observation sequence. This variant reports an
ownership disposition performed outside the loop; it does not claim that the
loop authorized, released, or transferred anything. The ownership provider and
same-host lease protocol must retain sufficient immutable history to produce
this evidence. Before response delivery, the local path durably writes the body,
evidence, and wrapper to the shared invocation-state directory. The provider
path idempotently attaches the same objects to a deterministic
`ownership_loss_record_id` through `record_ownership_loss_terminal`. That ID is
the hashed-record digest of `ownership_loss_identity_v1`, containing provider
identity and configuration revision, canonical lease key, and loop invocation
ID. It is caller-known for both composed and standalone invocations. The record
operation may not change the lease and succeeds only for the invocation and
immediately prior owner bound by the authenticated takeover/transfer receipt. It
consumes the invocation's explicit grant and, when coordinator-backed, the exact
coordinator allowance. Authenticated
`read_ownership_loss_terminal(ownership_loss_record_id)` recovers this variant;
`read_handoff(handoff_id)` remains the lookup for successful composed return
transfers.

A sealed body is a prepared artifact, not a terminal result, until paired with a
valid ownership-transfer receipt, ownership-release receipt, or ownership-loss
evidence. Its stated outcome is the outcome proposed if ownership disposition
succeeds or the observed loss is authenticated. If transfer or release fails or
ownership changes, the loop reconciles live ownership and prepares a new blocked
body for the applicable receipted return; it never presents an unreceipted body
as a completed result.

### Composed coordinator fencing

When a caller supplies a delegated-execution or equivalent coordinator contract,
pass it into `review-fix-loop` as an additional authority ceiling. The handoff
includes:

- outer invocation identity;
- checkpoint command or equivalent synchronous authorization mechanism;
- last consumed sequence and opaque continuation token;
- covered consequential-action vocabulary;
- caller authority-ledger tail; and
- required post-publication acknowledgement protocol.

For remote-ref composition, the covered vocabulary includes every granted
`candidate_lease.*` mutation, `candidate_handoff.transfer`,
`candidate_handoff.record_ownership_loss`, and `candidate_base_rebind`. These
are consequential coordination-state mutations even when they do not alter the
Git provider directly.

The adapter also requires stable request IDs and one of two authenticated
recovery mechanisms:

- exact duplicate requests return the original durably persisted response
  without consuming another sequence or allowance; or
- a read-only ledger-tail operation returns the response, sequence, token, and
  acknowledgement previously persisted for a request ID.

For either mechanism, the coordinator atomically persists the complete response
with its allowance or acknowledgement before replying. Reusing a request ID with
different content is a hard replay violation. A protocol that rejects an
identical consumed request but cannot recover its persisted response is
insufficient for resumable composed execution.

#### Constrained base-rebinding revision

The root outer invocation remains immutable. Each approved rebind appends one
`invocation_revision` containing:

- root invocation ID;
- revision number exactly one greater than the preceding revision;
- preceding revision digest, or the root invocation digest for revision one;
- immutable base ref, old effective base SHA, and new base SHA;
- exact candidate head, effective-diff identity, and resulting-tree identity
  before and after drift reconciliation;
- canonical retain-or-invalidate dispositions for validation and review, plus
  the resulting acceptance-reconciliation-required flag;
- coordinator request ID, sequence, continuation token, authority receipt, and
  revision digest.

A revision may replace only the effective base SHA and the status or candidate
binding of evidence whose definition was already present in the root invocation.
It may retain passing evidence only under the canonical base-drift rules;
otherwise that evidence becomes missing and must be rebuilt. It may not change
ticket or tracker identity, repository or base ref, observable goal, scope,
non-goals, constraints, acceptance-criterion definitions, validation or review
requirements, authority ceiling, desired outcome, allowed terminal states,
checkpoint mechanism, or caller identity. A ticket observation change, new
repository requirement outside the original authority, criterion change, or
other attempted immutable-field change requires a fresh outer invocation.

The effective invocation is a deterministic projection of the immutable root
plus every valid revision in uninterrupted digest order. Every later checkpoint
request carries the effective revision number and digest. The terminal result
does the same. Coordinator and terminal validators independently reconstruct the
projection, reject gaps, forks, reordered revisions, unknown fields, or digest
mismatch, and validate all candidate, base, evidence, and authority claims
against that effective projection rather than either an ad hoc mutable
invocation or the stale root base.

Immediately before every loop action covered by that outer vocabulary, invoke
the coordinator with the exact current candidate, sequence, token, proposed
effect, repository, remote, and fully qualified ref. One allowance authorizes
only that exact action. A denial, mismatch, unavailable command, replay, or
malformed response blocks the action without consuming or inventing authority.

Immediately after every successful candidate publication or advancement, send
the required `candidate_published` acknowledgement with the verified remote,
full ref, base SHA, and published head SHA before any later mutation or terminal
result. If acknowledgement fails, preserve and report the verified published
candidate but return `blocked`. When the invocation performs no covered remote
publication, including `local_commit`, the terminal field is explicitly null and
no publication acknowledgement is requested or invented.

Composed ownership return is one durable handoff transaction, not a
release-and-reacquire race. The caller supplies its return-owner identity and
expected token. After the final live-state read and before ownership transfer,
the loop constructs and journals `terminal_body_v1` with a stable handoff ID and
digest. The handoff ID is caller-known before transfer and deterministically
equals the hashed-record digest of a `handoff_identity_v1` record containing
provider identity and configuration revision, canonical lease key, caller
composition ID, and loop invocation ID. The caller composition ID is the outer
invocation ID when coordinator-backed and an equally unique caller-owned
composition ID otherwise. Because one loop invocation has exactly one terminal
ownership disposition, retries reuse the same ID and conflicting content for
that ID is invalid.

After preparation, the loop performs no candidate, remote, or evidence mutation.
When an outer coordinator exists, it obtains one allowance for
`candidate_handoff.transfer`, bound to the body digest, candidate, lease, and
intended caller; that recovered allowance is `handoff_authorization_v1`. Without
an outer coordinator, authorization is null and the provider validates the
invocation's explicit handoff grant. The provider then executes one atomic
`transfer_with_handoff` operation that verifies the body, optional authorization
digest, invocation grant, and expected current lease; persists the body and
authorization value; transfers the lease to a new caller-owned epoch and opaque
token; and attaches `ownership_transfer_v1`. No later coordinator action is
permitted when a coordinator was used. Terminal validation builds
`terminal_envelope_v1` through the single projection above and, when applicable,
requires its final authority ledger to match the coordinator's durable tail.

The provider exposes an authenticated, caller-addressable
`read_handoff(handoff_id)` operation. A crash before the provider transaction
leaves ownership with the loop; recover the coordinator allowance by stable
request ID, then execute the exact body-bound transfer without requesting new
authority. A crash after the transaction leaves ownership with the caller, which
reconstructs the exact terminal envelope from `read_handoff` without relying on
loop response delivery. A missing, mutable, mismatched, or unreadable handoff
record blocks transfer; a receipt mismatch blocks caller consumption. The loop
never reacquires a successfully transferred lease. Standalone invocations
instead release their local or shared lease after durably recording terminal
state and do not create a caller handoff.

The terminal result returns the updated outer sequence, continuation token, and
exact consumed-authority ledger for caller validation. The loop's own invocation
checkpoint cross-references these transitions but never substitutes for the
coordinator ledger. Standalone invocations without a coordinator omit this
adapter.

The current `agent-scripts.implement-ticket/delegated-execution/v2` protocol
cannot meet this adapter: it rejects consumed-request replay, exposes no
ledger-tail recovery operation, and binds the invocation to one immutable base
SHA. Its vocabulary also has no shared-lease or terminal-handoff operations.
Composed adoption therefore requires a new version that supplies response
recovery, constrained base revisions, an authorized shared ownership provider,
and recoverable terminal handoff. Until that version is implemented and
validated, delegated callers retain their existing loop rather than invoking
`review-fix-loop`.

## Workflow

### 1. Resolve

Read live repository, worktree, branch, ticket, and optional pull-request state.
Validate the invocation or construct the standalone operating contract. Capture
the exact candidate and prove exclusive mutation ownership.

### 2. Establish evidence

Run or verify the required initial validation. Build fresh raw review evidence
without implementation transcripts, intended answers, prior conclusions,
suspected findings, or expected evaluation outcomes.

A deterministic required-gate failure on the committed current candidate is
actionable evidence, not `blocked/validation_failed`. Record a stable synthetic
validation finding bound to the command, head, base, and failure identity, then
enter the ordinary decide/fix path. If trustworthy diagnosis attributes the
failure to the candidate but cannot identify a safe autonomous correction,
return `changes_remaining` with `current_candidate_validation_failure`. Use
`blocked` instead when authority, allowed scope, evidence attribution, or a
required decision prevents a known correction.

### 3. Review

Invoke `review-code-change` according to the review execution-context policy.
Create a new read-only aggregate reviewer subagent for this exact pass when
supported and required. Do not reuse a reviewer from an earlier pass or head.
Consume only a valid aggregate result bound to the expected head and comparison
base. Verify that neither the reviewer nor any delegated lens mutated the
candidate.

### 4. Decide

- Mark the loop converged when the current-head complete aggregate review has no
  gating finding, then calculate reviewer-isolation and publication fields
  before returning.
- Stop with `blocked` when evidence, identity, ownership, authority, a required
  dependency, or a product or architecture decision is missing.
- Stop with `blocked` and `blocker_kind: redesign_required` when the review
  requires replacement of the implementation strategy rather than a tractable
  in-strategy correction.
- Otherwise verify and disposition each actionable finding before mutation.

### 5. Fix

Reserve one invocation cycle before editing and open a transactional fix
attempt. The canonical candidate branch and worktree remain at the last clean
committed head while the attempt owns its edits in an invocation-owned isolated
worktree or an equivalently exact restorable boundary.

Apply the smallest sufficient correction for compatible `blocking` and
`strong_recommendation` findings. Batch findings into one cycle only when their
fixes are compatible and can be validated coherently.

Do not apply:

- `defer` findings;
- unsupported or stale findings;
- cosmetic preferences;
- speculative hardening;
- broad modernization;
- sibling or parent work;
- a simplification proposal that correctness marked unsafe; or
- a fix that requires an unresolved decision.

Record each applied, rejected, deferred, superseded, and unresolved finding by
stable identifier with its evidence-based disposition.

### 6. Validate and commit

Run affected focused validation and every required full gate inside the
transactional attempt. If formatting or another approved command changes tracked
files, treat those changes as part of the attempt and inspect them before
committing.

When validation demonstrates a candidate- or fix-attempt-caused failure:

- consume the reserved cycle;
- preserve an exact patch and any generated diagnostic needed to understand the
  failed attempt in the ignored invocation state;
- leave the canonical candidate branch and worktree unchanged at the last clean
  committed head;
- record the attempted finding dispositions and validation evidence; and
- retry only when budget remains and a materially different tractable correction
  is justified.

After bounded retries, these demonstrated failures return `changes_remaining`
with `non_convergence_reason: repeated_failed_attempt` or
`cycle_budget_exhausted`. When required validation is unavailable, malformed, or
cannot be attributed trustworthily after documented bootstrap attempts, return
`blocked` with `blocker_kind: validation_failed` instead.

If the runtime cannot guarantee that a failed attempt leaves the canonical
candidate clean and unchanged, stop with `blocked` and
`blocker_kind: candidate_integrity_failure`; preserve the dirty attempt for
operator inspection without presenting it as the candidate.

Create one additive commit for the coherent remediation cycle. The commit body
may summarize which finding identifiers it addresses, but the checkpoint and
terminal result own the required finding-to-commit linkage; no standardized Git
trailer is required. Do not amend, squash, rebase, force-push, or rewrite
earlier commits unless a separate future contract explicitly authorizes that
behavior.

After a successful attempt, promote its commit to the canonical candidate only
through a verified non-rewriting fast-forward from the exact pre-attempt head.
Confirm a globally clean canonical worktree and record the new head in the
checkpoint.

### 7. Invalidate and repeat

Discard every old-head review result and head-bound validation claim. Set
`acceptance_reconciliation_required: true` whenever the candidate or effective
base changes. Capture the new head and applicable base, rebuild the packet, and
restart the complete suite.

Do not push the new head during ordinary iteration. Under `update_pr`, if a
required review or validation mechanism has a matching invocation grant and
needs an origin-visible head, apply that remote-only exception immediately
before the named mechanism and record the exposed intermediate state.
`local_commit` never uses this exception.

### 8. Publish after convergence

After the complete review converges, apply the publication policy:

- Under `local_commit`, perform no remote write.
- Under `update_pr`, fetch and reread the exact head repository, fully qualified
  head ref, expected old object ID, base ref, and base object ID. Reconcile any
  base drift under the canonical rules. If drift invalidates any validation or
  review evidence, revoke convergence and return to **Establish evidence**; do
  not proceed to publication until a new current-base aggregate `clean` and
  required validation exist. Otherwise require the local candidate to be a
  non-rewriting descendant of the exact expected head, then atomically
  compare-and-swap the complete local commit range once. Verify the full remote
  identity, ref, and exact final SHA afterward.

If the remote advanced, the push failed, or the final ref cannot be verified,
return `blocked/publication_failed` while the loop still owns its lease and
complete the ordinary release or caller-return protocol. Use
`blocked/ownership_lost` only when an authenticated live lease read proves
external transfer and `ownership_loss_terminal_v1` can be constructed. Preserve
the converged local candidate and report all unpushed commits rather than
retrying with a rewrite.

### 9. Return

Reread live local and optional remote state. Return exactly one terminal result
bound to the final observed candidate. Every non-converged result explicitly
distinguishes the reviewed local head from the published remote head.

## Convergence and stop conditions

The numeric budget is a ceiling, not the only convergence control.
`review-fix-loop` returns `changes_remaining` before exhausting the numeric
budget when:

- the same root-cause finding remains after its claimed correction;
- candidate changes oscillate between incompatible solutions;
- material findings expand across cycles instead of converging; or
- repeated failed attempts demonstrate that the current correction strategy is
  not converging.

It returns `blocked` when:

- the required correction materially exceeds the ticket's allowed scope;
- review requires replacing the implementation strategy;
- a product, architecture, migration, data, authorization, or destructive
  decision is unresolved;
- required validation is unavailable, malformed, or cannot be attributed
  trustworthily after documented bootstrap attempts;
- a reviewer result is malformed, stale, wrongly bound, or mutates the
  candidate;
- base drift prevents safe reconstruction of the effective candidate, creates a
  conflict requiring unauthorized mutation, or leaves current identity or
  ownership unprovable;
- the local or remote head advances externally;
- mutation ownership becomes ambiguous; or
- another required dependency or authority is unavailable.

The skill must not consume remaining cycles merely because budget remains. Every
stop leaves the canonical candidate at a globally clean committed head and
reports any failed-attempt patches separately.

Ordinary relevant base drift is not itself a blocker and consumes no fix cycle.
Invalidate and rebuild the affected or complete validation and review evidence
under the canonical drift contract. Use `blocker_kind: base_drift` only for the
unreconstructable, conflicting, unauthorized, or identity-ambiguous cases above.

## Resume and interruption recovery

Interruption recovery is a first-class use case. Persist the invocation
checkpoint and append-only phase journal under a skill-local ignored directory
such as `.review-fix-loop/`. They are durable authority for invocation identity,
consumed budget, phase history, and expected ownership lineage, but not for
current provider ownership or mutable repository, tracker, coordinator, or
remote facts.

Every resume:

1. loads and validates the exact invocation checkpoint and complete journal;
2. validates the still-current local or provider-owned epoch, or performs an
   explicitly authorized transfer or takeover;
3. reconstructs candidate, ticket or pull request, head, base, remote refs,
   worktree, coordinator ledger, effective invocation revision, provider lease,
   any handoff record, and authority from live sources;
4. reconciles every prepared-but-not-observed journal transition against live
   state; and
5. preserves the original budget and consumed-attempt count.

For each incomplete transition:

- when the authoritative effect is absent and the fencing token and authority
  remain current, retry or abandon the prepared operation according to its phase
  without duplicating budget consumption;
- when the exact intended effect or phase-specific effect matcher is satisfied,
  append `observed_complete` and continue without performing it again; and
- when authoritative state differs from both the recorded pre-state and the
  phase-specific effect matcher, return `blocked` with the applicable ownership,
  integrity, checkpoint, or publication reason.

A reservation append that exists is consumed exactly once; an absent reservation
was never consumed. For provisional commit recovery, inspect only the
invocation-owned provisional ref and accept it only when its parent, tree,
message digest, attempt identity, and applicable signing policy satisfy the
prepared matcher. Never infer intent from an arbitrary dangling commit.

A crash after canonical fast-forward but before checkpoint projection therefore
observes and records the existing promoted head rather than treating it as
external. A crash after remote publication but before readback or coordinator
acknowledgement reads the exact remote ref, never republishes an already-present
head, then resumes the required acknowledgement. A failed acknowledgement
preserves the published artifact and returns `blocked`.

If a coordinator allowance or acknowledgement may have been durably consumed
before the local journal recorded its response, recover it by stable request ID
before issuing any new request. An exact recovered response advances the local
journal without consuming authority again. A mismatched response, or a
coordinator that supports neither idempotent identical replay nor authenticated
ledger-tail recovery, returns `blocked/checkpoint_mismatch`.

If a composed invocation crashes after its lease was transferred to the caller
but before response delivery, the caller reads the terminal envelope and
caller-owned fencing token from the shared provider by handoff ID, verifies both
receipts and the effective invocation projection, and consumes that recovered
result. The loop must not reacquire that lease or repeat the transfer. If the
local journal says `prepared`, always read provider lease and handoff state
before acting: caller ownership plus a matching handoff completes recovery; loop
ownership plus no handoff permits the exact authorized transaction to resume;
any other combination blocks. A standalone release is similarly reconciled from
the authoritative provider or local lease and journal before any new mutation.
After externally proven ownership loss, the caller recovers
`ownership_loss_terminal_v1` by deterministic ownership-loss record ID from the
provider or by invocation ID from the shared local invocation-state directory
and validates it against the takeover/transfer receipt. It never asks the former
loop owner to reacquire or recreate candidate state.

If an interruption occurred inside a transactional attempt, treat that reserved
cycle as consumed. Recover the canonical candidate at its checkpointed clean
head and preserve the isolated attempt patch. If exact recovery cannot be
proven, return `blocked` with `blocker_kind: candidate_integrity_failure`.

A missing or mismatched checkpoint cannot resume. Return `blocked` with
`blocker_kind: checkpoint_mismatch`, or begin a clearly new invocation only
after explicit operator authorization. No intermediate state is committed to the
candidate; the skill-local `.gitignore` excludes it.

## Terminal result contract

The serialized result is exactly one of `standalone_terminal_v1`,
`terminal_envelope_v1`, or `ownership_loss_terminal_v1`. There is no additional
top-level projection. The following inventory defines each field's sole
component.

`terminal_body_v1` contains:

- proposed terminal state;
- invocation ID, original budget, consumed attempts, journal sequence, and
  active-worker claim/takeover history when applicable;
- ownership scope, applicable provider identity/version/configuration, canonical
  local or remote lease key, pre-disposition owner/epoch/token, and intended
  return owner when composed, plus the deterministic handoff ID when
  provider-composed;
- repository and optional pull-request identity, initial and final head SHA,
  comparison-base SHA, local branch, and worktree;
- ordered `head_history` and `base_revision_history`, present for every terminal
  variant and consistent with the initial/final head and comparison-base fields;
- complete aggregate review identity, independence and write-isolation evidence,
  reviewer identities, overrides, write-prevention mechanisms, integrity
  evidence, and mutation attempts;
- validation commands and exact outcomes;
- `acceptance_reconciliation_required`;
- review-result identities, candidate bindings, applied fixes, finding
  dispositions, created commits, failed-attempt patches, and diagnostics;
- initial and final remote head, local ahead/behind state, every unpushed
  commit, verified pushed state, and publication state;
- deferred and unresolved findings;
- when coordinator-backed, publication acknowledgement for each covered remote
  publication or explicit null when none occurred, immutable root-invocation
  digest, effective-invocation revision/digest, and the exact pre-handoff
  authority-ledger prefix; the coordinator's revision-derived base history must
  exactly match the body's `base_revision_history`; and
- one next action, non-convergence reason, or structured blocker.

`handoff_authorization_v1`, when non-null, contains only the exact handoff
action and its resulting coordinator sequence, continuation token, and authority
entry and the deterministic handoff ID. `ownership_transfer_v1` is the transfer
receipt and contains only body and optional authorization digests, the same
handoff ID or explicit null for local return, returned owner/epoch/token,
applicable local or provider lease identity, operation ID, final ownership
disposition, and resulting state. It may additionally contain the named
`asserted_*` candidate, base, and previous-owner CAS bindings defined by the
envelope contract; they must equal the body's authoritative values.
`ownership_release_v1` is similarly the release receipt and omits handoff and
returned-owner fields. `ownership_loss_evidence_v1` contains only the
deterministic ownership-loss record ID, authenticated observation, and immutable
operation evidence defined above. Final `authority_used` is derived only as
defined by the envelope projection. Each wrapper contains only its schema
identifier, applicable component objects, and wrapper digest; it does not repeat
body, authorization, ownership, sequence, token, or receipt fields.

Terminal states are:

- `converged`: the complete aggregate review has no gating findings for the
  exact final head and base, required validation passes, candidate integrity is
  verified, and the selected publication policy completed.
- `changes_remaining`: bounded non-convergence left actionable findings after
  cycle exhaustion, a repeated finding, oscillation, expanding findings, or
  repeated failed attempts, including a demonstrated current-candidate
  validation failure with no tractable correction.
- `blocked`: the loop cannot continue safely because of evidence, authority,
  ownership, integrity, validation, publication, dependency, capability, scope,
  or decision failure.

For `converged`, include:

```text
publication_state: local | published
review_independence: fresh_subagent | in_agent_override
write_isolation: enforced
```

`clean` remains the underlying aggregate review verdict; it is not a workflow
terminal state. `converged` requires:

- a valid current-head and current-base aggregate `clean`;
- all required validation passing;
- `write_isolation: enforced`; and
- the caller's required independence policy, with any `in_agent_override`
  explicitly authorized and reported.

For `changes_remaining`, use one non-convergence reason:

- `cycle_budget_exhausted`;
- `repeated_finding`;
- `oscillation`;
- `expanding_findings`;
- `repeated_failed_attempt`; or
- `current_candidate_validation_failure`.

`repeated_failed_attempt` and `cycle_budget_exhausted` cover demonstrated
candidate- or fix-attempt-caused validation failures after bounded attempts.
`current_candidate_validation_failure` covers a deterministic failure already
present on the committed candidate when no safe ticket-scoped correction can be
attempted. Once a correction is attempted, ordinary attempt and budget reasons
control instead.

For `blocked`, use a structured `blocker_kind`, including:

- `redesign_required`;
- `scope_exceeded`;
- `ownership_lost`;
- `missing_authority`;
- `missing_capability`;
- `missing_decision`;
- `validation_failed`;
- `reviewer_integrity_failure`;
- `candidate_integrity_failure`;
- `base_drift`;
- `publication_failed`;
- `ambiguous_candidate`; or
- `checkpoint_mismatch`.

`blocker_kind: validation_failed` is reserved for unavailable, malformed, or
unattributable required validation evidence, not demonstrated candidate-caused
failures.

Every non-converged or blocked result preserves and identifies the last clean
committed candidate, unresolved findings, failed-attempt artifacts, unpushed
commits, and the exact local/remote relationship.

The caller must validate the result against live state before consuming it.

## Effects on existing skills

### `review-code-change`

Its review semantics and public result contract do not change.

Documentation should clarify that `review-fix-loop` is the preferred mutating
caller when iterative remediation is needed. The existing “Handle fixes and
cycles” section should continue to describe what a caller must do after a head
change, but it may point to `review-fix-loop` as the repository-owned
implementation of that caller responsibility.

The installed review contract should strengthen its execution guidance so
callers do not treat a “read-only” prompt as sufficient enforcement. It should
prefer mutation-tool exclusion and deny-write execution, prohibit rerunning
write-capable validation commands, and require before/after integrity evidence.
These are execution safeguards around the existing result contract, not a change
to lens semantics.

The default three-cycle statement should move to, or be explicitly subordinate
to, `review-fix-loop` for mutating workflows. `review-code-change` may still
report the next required action and must continue to reject old-head evidence.

No partial-lens option is added to `review-code-change`.

### Individual review-lens skills

Their rubrics, schemas, verdicts, and read-only guarantees do not change. They
remain dependencies of `review-code-change`, not direct dependencies or
user-selectable modes of the initial `review-fix-loop`.

### `implement-ticket`

`implement-ticket` should delegate its initial bounded repository review loop to
`review-fix-loop` after:

- the ticket candidate is complete;
- intended changes are committed;
- the worktree is clean;
- required validation has run; and
- exclusive mutation ownership can be transferred.

For the ordinary same-host `local_commit` path, it transfers and receives the
local lease through `terminal_envelope_v1`; no shared provider or coordinator is
required. It can recover a lost loop response from the invocation-state
directory and local transfer receipt before resuming mutation.

It invokes:

- the default fresh-subagent review mode, unless a current-user override that
  `implement-ticket` is authorized to pass through explicitly selects
  `in_agent`;
- the remaining configured fix-cycle budget, defaulting to three;
- publication policy `local_commit`; and
- the resolved ticket contract, candidate identity, validation commands,
  acceptance-evidence identity metadata, and applicable authority.

When `implement-ticket` itself is delegated, it also passes the outer checkpoint
command, sequence, continuation token, covered action vocabulary, and
authority-ledger tail. It validates the loop's returned sequence, token,
consumed-authority ledger, and the explicit null publication acknowledgement
before using a local-only handoff. It requires and validates a
candidate-publication acknowledgement only when terminal publication history
records a covered remote publication.

That delegation is gated on a successor to delegated-execution v2 that provides
stable checkpoint request IDs, idempotent response recovery or authenticated
ledger-tail recovery, constrained candidate-base revisions, the shared
ownership-provider operations, and atomic `transfer_with_handoff`.
`implement-ticket` supplies provider discovery/authentication metadata, its
return-owner identity, and expected fencing token. It accepts a handoff only
when authenticated `read_handoff` returns matching coordinator and provider
receipts, the effective invocation projection validates, and the caller-owned
epoch matches live lease state. Under v2 it retains its current in-skill
review/fix loop.

`implement-ticket` continues to own ticket readiness, initial implementation,
acceptance evidence, publication-size classification, PR creation, delegated PR
lifecycle, tracker transition, mainline verification, and cleanup.

It accepts only `converged` with `publication_state: local`, a current-head and
current-base aggregate `clean`, the exact current head and base, required
validation, a globally clean candidate worktree, and a valid local or provider
transfer receipt.

Missing required acceptance evidence does not change the loop's `converged`
review result. When `acceptance_reconciliation_required` is true,
`implement-ticket` applies its existing ledger rules to the returned candidate
and base, rebuilds caller-owned evidence as authorized, and cannot claim ticket
or publication readiness until every required pre-publication criterion passes.
If that work changes code, the new head requires a new bounded review-fix
invocation rather than reusing the prior review result.

By default it also requires `review_independence: fresh_subagent`. A
current-user `in_agent` override may be passed through only when
`implement-ticket`'s own contract explicitly permits and records that override;
`write_isolation: enforced` remains mandatory. Its runtime-capability section
should therefore change from an unconditional fresh-worker requirement to
fresh-by-default plus this explicit, recorded override path.

`changes_remaining` and `blocked` map to `implement-ticket`'s blocked handoff
with the last clean candidate, failed-attempt artifacts, unpushed commits,
remaining findings, invocation budget, and structured reason preserved.
`blocked/ownership_lost` is accepted only through a valid
`ownership_loss_terminal_v1`; the caller reconciles the authenticated successor
epoch and does not resume mutation from the former token.

Once migration is proven, duplicated fix, validation, commit, cycle-counting,
and re-review mechanics should be removed from `implement-ticket`; its reference
should retain the handoff prerequisites and result validation rules.

### `babysit-pr`

`babysit-pr` continues to own GitHub monitoring, CI diagnosis and retries, human
and connector feedback, review communication, thread disposition, mergeability,
and optional merge.

It uses `review-fix-loop` in two situations:

1. A standalone readiness invocation lacks valid repository-owned review
   evidence for the current candidate.
2. A CI, human, connector, or other accepted fix has created a new head and the
   repository-owned review gate must be re-established.

Before delegation, `babysit-pr` finishes the external-feedback or CI correction
that it owns, commits and publishes that correction as required by its workflow,
then transfers exclusive mutation ownership of the current PR branch through the
configured shared provider. `review-fix-loop` uses publication policy
`update_pr` so any new repository-review findings can be fixed in local commits
without exposing each intermediate candidate. After the complete review
converges, `review-fix-loop` pushes the complete fast-forward range once and
verifies the final remote head. It uses the default fresh-subagent mode.
`babysit-pr` must not silently request `in_agent`. It may pass through a
current-user `in_agent` override only when its own operating contract records
that authority and still enforces write isolation.

When `babysit-pr` operates beneath a delegated `implement-ticket` contract, its
handoff to `review-fix-loop` carries the same coordinator adapter. The loop, not
a competing caller action, obtains the one-shot allowance immediately before
each covered publication and performs the required post-publication
acknowledgement.

This composed path likewise requires the successor coordinator protocol. A base
advance must be approved and persisted as a constrained `invocation_revision`
through `candidate_base_rebind` before review can continue; when rebinding is
unsupported or denied, the loop returns `blocked/base_drift` and `babysit-pr`
requests a fresh outer invocation. On return, `babysit-pr` retrieves and
validates the terminal envelope, effective invocation projection, provider
receipts, and caller-owned lease epoch before resuming any mutation.

`babysit-pr` accepts only `converged` with `publication_state: published`, a
current-head and current-base aggregate `clean`, and the exact final head and
base verified remotely. It then consumes the already-transferred caller-owned
mutation epoch, invalidates every affected remote gate, restarts the watcher,
and resumes its lifecycle. It never releases and races to reacquire the
candidate lease.

When `acceptance_reconciliation_required` is true, `babysit-pr` tells the
enclosing caller to reconcile its acceptance ledger against the published head.
It may continue read-only monitoring but must not claim readiness or merge when
the enclosing contract requires evidence that has not been re-established.

If the loop does not converge, the pull request ordinarily remains at its last
published head while the remediation worktree contains additional local commits.
`babysit-pr` must surface the exact unpushed commit list and required operator
input. It must not describe those commits as published PR fixes, resume the
lifecycle as though the remote contained them, or discard them. It may continue
read-only observation of the actual published head only when that does not
obscure the blocked local candidate.

`changes_remaining` stops mutation and surfaces the invocation's remaining
findings and unpushed commits. `blocked` does the same and dispatches by
`blocker_kind`; `ownership_lost` requires immediate live-state reconciliation,
acceptance only through a valid `ownership_loss_terminal_v1`, and abandonment of
the former fencing token, while `publication_failed` preserves the converged
local head without claiming it reached the pull request.

If a repository-required reviewer or check can run only against the PR head,
`babysit-pr` may pass invocation-fixed, mechanism-specific
`remote_iteration_grants` and demonstrated dependency evidence for the exact PR
repository and head ref. Each exceptional intermediate push then becomes the
live PR candidate, invalidates remote gates, and is reported as non-converged
until a later full review passes.

There must be one repository-review fix-cycle budget. `babysit-pr` passes the
configured budget to `review-fix-loop` and consumes its reported usage rather
than maintaining a competing nested counter. CI retry and external-feedback
budgets remain caller-owned and distinct.

Once migration is proven, the detailed repository-owned fix/re-review mechanics
should leave `babysit-pr`; it retains ownership transfer, handoff validation,
gate invalidation, and watcher restart.

### `carve-changesets`

`carve-changesets` has additional invariants that the generic skill must not
absorb: immutable source identities, changeset ordering, whole-chain
equivalence, published stack topology, and successor-source recovery.

For local per-changeset review, it may eventually delegate candidate remediation
to `review-fix-loop` with:

- the default fresh-subagent review mode, with no implicit in-agent fallback;
- publication policy `local_commit`;
- per-changeset goal and preserved intermediate-state constraints; and
- approved validation commands that include caller-required chain checks.

`carve-changesets` may consume only locally converged aggregate evidence for a
changeset. It remains responsible for rebuilding and verifying chain-wide
equivalence; `converged` does not prove stack equivalence.

For published changesets, `babysit-pr` remains the lifecycle owner and reaches
`review-fix-loop` through its own handoff. `carve-changesets` must not start a
competing loop.

Because source-lineage correction is materially more specialized than ordinary
candidate remediation, `carve-changesets` should not be the first integration.
Its existing loop should remain until local-chain and successor-source fixtures
prove that delegation preserves every invariant.

### Standalone invocation

A standalone invocation follows the same complete-review requirements as a
composed caller. An explicitly requested `in_agent` review records
`review_independence: in_agent_override`; it remains eligible for certification
only when write isolation is enforced and no stricter repository policy requires
a fresh reviewer.

A standalone `local_commit` invocation uses local-candidate ownership and does
not require a shared provider. A standalone `update_pr` invocation requires an
explicitly configured and authorized provider with the same cross-clone lease
semantics; without it, startup returns `blocked/missing_capability` before
candidate mutation.

### `implement-epic`

No direct dependency is added. It continues to invoke `implement-ticket` for one
ready child at a time and observes the new skill only through `implement-ticket`
terminal evidence.

The dependency graph remains acyclic, and epic orchestration must not copy
review-fix mechanics.

### Repository packaging and documentation

Adding the skill increases the plugin's stable-name dependency set. The
repository will need to update:

- plugin and marketplace manifests;
- README skill inventory and dependency diagrams;
- runtime discovery metadata;
- installation and missing-dependency tests;
- `justfile` skill-specific test and evaluation commands; and
- any composed-skill dependency-closure fixtures.

Standalone installation must include `review-code-change` and its transitive
repository-owned lens dependencies, or the skill must fail closed with every
missing dependency named.

## Compatibility and migration strategy

The skill should be introduced without immediately changing caller behavior.
This avoids combining a new contract with several workflow migrations in one
unverifiable change.

The intended order is:

1. Define and test the standalone skill, layered terminal envelope, and
   same-host local handoff contract.
2. Exercise local-only workflows and fail-closed existing-PR startup without a
   provider, including interruption recovery, complete review, stale heads,
   dirty worktrees, missing authority, cycle exhaustion, oscillation, and
   reviewer mutation.
3. Define and validate the authoritative provider-binding registry and shared
   ownership provider, then exercise standalone existing-PR publication,
   cross-clone contention, takeover, and handoff recovery.
4. Define, version, and validate a successor delegated-execution protocol with
   stable request IDs, coordinator response recovery, constrained base
   revisions, authorized provider operations, and atomic terminal handoff.
5. Integrate `implement-ticket` and prove behavior equivalence for the initial
   local loop and composed recovery. Do not route delegated v2 invocations
   through `review-fix-loop`.
6. Integrate `babysit-pr` and prove ownership transfer, pushed-head
   reconciliation, watcher restart, and nonduplicated budget accounting.
7. Evaluate `carve-changesets` integration against its stronger chain
   invariants; migrate only when equivalence is demonstrated.
8. Remove duplicated caller prose and fixtures only after each caller consumes
   the new contract successfully.

During migration, a caller uses either its existing loop or `review-fix-loop`
for a candidate, never both.

## Validation strategy

Deterministic contract tests should cover:

- rejection of a zero or negative fix-cycle budget;
- rejection of a read-only invocation;
- default selection of a new reviewer subagent when the runtime supports it;
- a different reviewer identity for every pass and every new head;
- one fresh aggregate-review subagent whose nested lenses share its enforced
  deny-write boundary;
- prohibition of uncontained descendant review contexts, plus identity,
  inherited-capability, credential-removal, and tool-trace attestation for every
  permitted descendant;
- minimal raw-evidence handoff without implementation transcript leakage;
- an explicit `in_agent` override and its terminal disclosure;
- fail-closed `blocked/missing_capability` behavior when a fresh reviewer is
  unavailable and no explicit in-agent override was present at invocation;
- rejection of an inferred, solicited, or automatic in-agent fallback;
- rejection of `write_isolation: verification_only` for full certification and
  publication;
- reviewer tool surfaces that omit edit, patch, commit, push, and remote-write
  operations;
- deny-write filesystem enforcement where the fixture runtime supports it;
- rejection of a reviewer that attempts a prohibited mutation even when the
  runtime blocks the write;
- rejection and preservation of evidence when a reviewer changes worktree, Git,
  or remote state before returning an otherwise valid result;
- before/after detection across tracked, staged, unstaged, untracked, ignored,
  commit-history, and ref state;
- initial complete-review convergence without artificial commits;
- fixes followed by a complete fresh three-lens review;
- rejection of partial or stale lens evidence as a full `clean`;
- rejection of direct-lens or custom-subset invocation by the initial skill;
- preservation of `review-code-change` proposal dispositions and
  stop-on-first-gating behavior without a second aggregation algorithm;
- exact invocation-owned cycle accounting across successful, failed, and
  interrupted attempts;
- transactional failed validation that leaves the canonical candidate globally
  clean at its prior committed head and preserves the failed patch separately;
- budget exhaustion with findings preserved;
- no intermediate push during an ordinary multi-cycle run;
- one verified atomic expected-old fast-forward push after convergence;
- exact head-repository, authenticated-remote, and fully-qualified-ref targeting
  for fork pull requests;
- a non-converged PR run that reports all unpushed commits and leaves the remote
  at its last verified head;
- an explicitly authorized remote-only review that exposes and reports an
  intermediate head;
- rejection of remote iteration under `local_commit`, for an unlisted mechanism,
  or after a repository/ref mismatch;
- mechanism-specific grant reuse within one invocation without authority
  transfer to another mechanism or invocation;
- repeated-finding and oscillation stops;
- dirty dedicated-worktree and externally advanced candidate rejection;
- local-only enforcement;
- stale-base detection immediately before review, publication, and terminal
  return;
- canonical base-drift evidence retention and invalidation cases;
- an explicit transition from publication back to evidence and full review when
  publication-time base drift invalidates certifying evidence;
- existing-PR compare-and-swap rejection on expected-old mismatch;
- conversion of an initial deterministic candidate validation failure into a
  stable actionable finding;
- `changes_remaining/current_candidate_validation_failure` when that initial
  failure has no tractable ticket-scoped correction;
- failed and unavailable validation;
- stable finding dispositions and fix-commit linkage;
- interruption recovery from the durable invocation checkpoint reconciled
  against live state;
- rejection of a missing or mismatched checkpoint as a resume;
- explicit new-invocation authorization without automatic budget renewal; and
- provider discovery, version negotiation, authentication, explicit
  coordination-state authority, and fail-closed missing-provider behavior;
- one authoritative repository-to-provider-instance binding across clones and
  rejection of ambiguous, conflicting, or invocation-injected provider choices;
- same-service coordinator allowance verification for the first adapter and
  rejection of unsupported cross-service receipts;
- one provider-owned remote-candidate fence keyed by canonical repository and
  fully qualified remote ref across separate clones, plus a secondary same-clone
  common-directory lock;
- local-only ownership scope without a provider and rejection of `update_pr`
  before mutation when no provider is configured;
- linearizable provider read/CAS, immutable receipts, monotonic epochs, and
  explicit-authority takeover;
- atomic local and provider `candidate_effect_v1` reservation across file,
  commit, promotion, and remote-ref effects, with transfer/takeover rejection
  while active;
- crash reconciliation of reserved effects before any ownership change,
  including effect-did-not-occur, effect-completed, and ambiguous outcomes;
- rejection of the validation-to-effect race in which a stale worker attempts to
  mutate after another owner or worker epoch takes over;
- atomic ownership-epoch transfer and rejection of stale fencing tokens;
- same-host `local_start_v1` ingress, including crashes before and after
  caller-to-loop CAS, exact-invocation redispatch, and rejection of overlapping
  mutation;
- duplicate dispatch with one atomic active-worker winner, no mutation by the
  loser, and explicit worker-epoch takeover that invalidates the old token;
- same-host local body persistence and loop-to-caller lease transfer, including
  crashes before and after CAS and recovery without response delivery;
- remote-head reread before every fix attempt on an existing PR branch;
- write-ahead recovery for crashes before and after attempt reservation,
  canonical promotion, remote publication, and publication acknowledgement;
- idempotent observation of already-completed effects without duplicate pushes
  or budget consumption;
- atomic attempt-reservation accounting and provisional-commit recovery through
  an attempt-owned ref plus parent/tree/message/policy matching;
- coordinator checkpoint denial, replay, sequence/token mismatch, and
  unavailable-command handling;
- crash recovery after a coordinator durably consumes an allowance or
  acknowledgement but before the loop journals the returned token;
- rejection of composed execution when the coordinator offers neither idempotent
  identical-response replay nor authenticated ledger-tail recovery;
- coordinator-approved base rebinding and fail-closed behavior when rebinding is
  unavailable;
- deterministic effective-invocation projection from an immutable root and
  ordered revision-digest chain;
- rejection of base revisions that alter ticket, repository, base ref, goal,
  scope, non-goals, criteria, validation/review requirements, authority, desired
  outcome, checkpoint mechanism, or caller;
- evidence retention and invalidation against the effective base revision;
- deterministic `acceptance_reconciliation_required` signaling after candidate
  or base changes without importing the caller's acceptance ledger;
- ordered `head_history` and `base_revision_history` in every terminal variant,
  including endpoint consistency, coordinator-history equality, and rejection of
  missing or mismatched histories;
- exact post-publication acknowledgement and consumed-authority-ledger
  round-trip when publication occurred, plus explicit null acknowledgement for
  coordinator-backed `local_commit`; and
- atomic provider `transfer_with_handoff`, authenticated `read_handoff`, and
  recovery both before and after transfer without terminal-response delivery,
  with coordinator authorization and with an invocation-granted null
  authorization;
- RFC 8785 hashed-record golden vectors for root invocation, `local_start_v1`,
  revisions, checkpoints, journal records, every terminal component, and every
  terminal wrapper;
- collision-resistant invocation-ID generation, exact retry reuse, and rejection
  of reuse with a different root digest or identity tuple;
- deterministic caller-known handoff-ID derivation and recovery after
  terminal-response loss;
- authenticated `ownership_loss_terminal_v1` construction after local and
  provider takeover, standalone and composed record-ID recovery after response
  loss, and rejection when only the remote ref—not the lease—advanced; and
- deterministic local and provider `terminal_envelope_v1` projection, including
  field-source, null-authorization, copied-field rejection, matching and
  mismatched `asserted_*` CAS bindings, intended/returned/coordinator-authorized
  owner equality, and receipt-mismatch cases.

Result-blind forward evaluations should include:

- a clean initial candidate;
- a correctness defect requiring one fix;
- a fix that introduces a new solution-level issue and therefore requires a
  complete full-suite restart;
- an unsafe simplification proposal;
- a code-simplicity finding that converges;
- the same finding surviving its claimed fix;
- an apparently useful fix that exceeds ticket scope;
- a stale PR head;
- unrelated dirty worktree artifacts;
- an attempted direct-lens or custom-subset invocation rejected as unsupported;
- a one-fix candidate that sets `acceptance_reconciliation_required` without
  importing or rewriting the caller's acceptance ledger;
- an ordinary relevant base advance that rebuilds evidence without consuming a
  fix cycle;
- a delegated base advance that rebinds through the successor coordinator
  protocol;
- an attempted base revision that changes scope or acceptance definitions and
  therefore requires a fresh invocation;
- an attempted delegated v2 dispatch that is rejected before the composed loop
  acquires mutation ownership;
- an unreconstructable base advance that returns `blocked/base_drift`;
- a deterministic initial validation failure with and without a tractable
  correction;
- repeated candidate-caused validation failures that return `changes_remaining`;
  and
- unavailable or unattributable required validation that returns
  `blocked/validation_failed`.

Caller integration fixtures should prove that:

- `implement-ticket` cannot publish without a locally `converged` handoff backed
  by a current complete aggregate `clean`;
- ordinary non-delegated `implement-ticket` recovers local ownership and the
  terminal body after response loss without a shared provider;
- `implement-ticket` consumes the acceptance-reconciliation flag and blocks
  readiness until its own ledger has been reconciled;
- `babysit-pr` resumes monitoring and rebuilds every remote gate on the returned
  head only after a published `converged` handoff backed by a current complete
  aggregate `clean`;
- `babysit-pr` does not claim readiness or merge while required candidate-bound
  acceptance evidence is missing;
- `babysit-pr` prominently preserves and reports unpushed commits when
  convergence fails;
- delegated callers receive the updated coordinator sequence, token, publication
  acknowledgement, immutable root and effective-revision digests, revision
  history, exact consumed-authority ledger, provider receipts, handoff identity,
  and caller-owned return epoch;
- delegated v2 callers retain their existing loop and cannot enter the composed
  `review-fix-loop` path;
- caller recovery through `read_handoff` succeeds after ownership transfer even
  when terminal-response delivery is interrupted;
- neither caller runs a competing review-fix loop; and
- `carve-changesets`, if migrated, re-proves chain equivalence independently.

The repository-wide required checks remain:

```bash
just format
just lint
just test
```

## Trade-offs

### Benefits

- Makes interrupted and piecemeal implementation workflows first-class.
- Removes duplicated mutation and convergence rules from composed skills.
- Preserves a single read-only review authority.
- Separates the mutating fixer from a fresh reviewer by default, reducing
  solution anchoring and accidental implementation-context leakage.
- Treats reviewer immutability as an enforced and auditable invariant rather
  than trusting the reviewer to obey prose alone.
- Makes cycle accounting and non-convergence behavior explicit.
- Avoids exposing intermediate, knowingly non-converged candidates on remote
  branches when local review is sufficient.
- Produces a reusable candidate-bound handoff for local and published work.

### Costs

- Adds another stable-name dependency to composed workflows.
- Creates additional subagent startup, token, and latency cost for every review
  pass.
- Requires runtime-specific deny-write, tool-restriction, or integrity-audit
  adapters to make reviewer isolation trustworthy.
- Requires fenced ownership, append-only phase journaling, and idempotent crash
  reconciliation around local and remote effects.
- Requires composed callers to propagate coordinator checkpoint and authority
  state through another delegation boundary.
- Requires a versioned successor to delegated-execution v2 before delegated
  callers can adopt the loop.
- Requires an authenticated, linearizable shared ownership and handoff provider
  for remote-ref ownership; standalone `update_pr` is unavailable without one.
- Requires careful exclusive-ownership and terminal-envelope transfer around
  published branches.
- Delays remote CI or remote-only review feedback until convergence unless an
  `update_pr` invocation contains a matching mechanism-specific remote-iteration
  grant.
- Requires migration and evaluation across multiple existing skills.

### Rejected alternatives

**Keep the loop duplicated in callers.** This preserves the current state but
does not support standalone resumption and allows convergence behavior to drift
between callers.

**Add mutation to `review-code-change`.** This would collapse the reviewer and
implementation contexts, weaken read-only integrity, and make result-blind
review harder to enforce.

**Add a read-only mode or allow zero fix cycles.** Existing review skills
already serve that use case. Supporting it here would make the skill's name and
authority contract ambiguous.

**Include focused or arbitrary lens-subset remediation in the initial skill.**
No identified caller requires it, and it would duplicate orchestration already
owned by `review-code-change`. Direct read-only lenses remain available; a
future focused mutating mode requires a demonstrated consumer and separate
design revision.

**Fold CI and external feedback into this skill.** That would duplicate
`babysit-pr`, create competing PR lifecycle owners, and broaden the skill beyond
repository-owned review remediation.

**Teach the skill stack semantics.** That would duplicate `carve-changesets`
lineage and equivalence responsibilities and make the generic workflow unsafe
for ordinary candidates.
