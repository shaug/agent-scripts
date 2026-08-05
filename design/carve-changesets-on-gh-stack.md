# Carve Changesets on GitHub Stacks

Status: proposed\
Date: 2026-08-05

## Decision summary

Rebuild `carve-changesets` around GitHub native stacked pull requests and the
`gh stack` CLI.

`carve-changesets` will decide how to divide one large, coherent source branch.
It will identify reviewable seams, preserve indivisible work, construct safe
intermediate states, materialize the layers, and prove that the complete stack
reproduces the intended result.

GitHub and `gh stack` will own the mechanics of maintaining that breakdown. The
skill will no longer carry a parallel implementation for stack topology,
cascading rebases, remote publication, pull-request retargeting, or downstream
propagation.

This design replaces the current dual role in which `carve-changesets` owns both
semantic decomposition and stack management. Ticket planning follows approval of
this document.

## Context

The current skill solves two different problems:

1. It determines where a large candidate can be cut without making a layer
   incoherent, unsafe, or impossible to review.
2. It implements a stacked-pull-request manager with custom branch naming,
   topology metadata, publication, rebasing, force-pushing, pull-request
   retargeting, merge sequencing, and suffix propagation.

The first problem is the reason for the skill. It requires knowledge of product
intent, code structure, migration safety, review load, and final behavior.

GitHub native stacks and `gh stack` now cover most of the second problem. The
CLI can adopt existing branches, record stack order, expose machine-readable
state, perform cascading rebases, push each branch with explicit lease
protection, submit native stacked pull requests, and synchronize local and
remote state. GitHub owns the published stack object, trunk-relative
protections, direct prefix merges, and merge-queue admission. A stack push may
partly succeed, and a queue landing may automatically rebase the remaining
suffix. The design must preserve exact identity and recovery across both cases.

Keeping both stack engines would preserve duplicated state and conflicting
mutation paths. It would also force `carve-changesets` to understand every
change in GitHub's stack behavior. A single stack engine gives each component a
clearer purpose.

References:

- [GitHub stacked pull requests announcement](https://github.blog/changelog/2026-07-30-stacked-pull-requests-are-now-in-public-preview/)
- [`gh-stack` repository](https://github.com/github/gh-stack)
- [Reviewed `gh-stack` revision](https://github.com/github/gh-stack/tree/14fc42ed9b6c376a53b2f999f138d3bd26dac546)
- [`gh stack` CLI reference](https://docs.github.com/en/pull-requests/reference/stacked-prs-cli-commands)

## Goals

The redesigned skill must:

01. Analyze one immutable, review-ready source branch and its complete diff.
02. Identify cohesive, independently reviewable changeset seams.
03. Preserve work that cannot be divided safely.
04. Order foundations, migrations, consumers, cutovers, and removals safely.
05. Document intentional incompleteness in every intermediate layer.
06. Materialize the approved layers without mutating the source branch.
07. Adopt the materialized branches into one verified local `gh stack`.
08. Use `gh stack` as the sole stack-management engine from materialization
    onward.
09. Publish every new chain as one native GitHub stack.
10. Preserve exact candidate review, validation, and authority boundaries.
11. Prove that the complete stack remains equivalent to the active immutable
    source.
12. Recover accepted post-publication corrections through successor-source
    provenance and native stack mechanics.
13. Resume from live git, `gh stack`, and GitHub state after interruption.
14. Fail closed when the required stack capability or exact identity cannot be
    verified.
15. Retire the custom stack manager instead of preserving it as a fallback.

## Non-goals

The redesign does not:

- ask `gh stack` to choose semantic seams;
- use `gh stack modify` to split the source candidate;
- weaken immutable-source or whole-chain equivalence requirements;
- weaken per-layer validation or repository-owned review;
- give a single pull-request watcher authority over the whole stack;
- preserve custom stack propagation as a compatibility mode;
- support pull-request hosts other than GitHub;
- migrate review remediation to `review-fix-loop`; or
- create or alter implementation tickets as part of this design.

## Architectural position

The target dependency structure is:

```text
carve-changesets
├── semantic decomposition and materialization
├── validation and whole-chain equivalence
├── review-code-change
├── babysit-pr
└── gh stack
    ├── local stack topology
    ├── cascading rebase and push
    ├── native stack submission and synchronization
    └── GitHub native stack APIs
```

`carve-changesets` remains the coordinator. It grants bounded authority, selects
the exact operation, and verifies the result. `gh stack` performs stack
mechanics. GitHub provides published topology and merge behavior.

## Responsibility boundary

### `carve-changesets`

`carve-changesets` owns:

- source and base identity;
- semantic seam selection;
- indivisibility decisions;
- safe intermediate-state design;
- extraction of source work into layer commits;
- layer descriptions, non-goals, and intentional incompleteness;
- per-layer validation and review packets;
- immutable-source and successor-source provenance;
- whole-chain tree, schema, and behavioral equivalence;
- mutation authority and exact target resolution;
- evidence invalidation after candidate changes;
- stack-level lifecycle coordination; and
- independent readback after every mutation.

### `gh stack`

`gh stack` owns:

- local stack membership and order;
- adoption of materialized branches;
- linear ancestry maintenance;
- cascading rebases;
- lease-protected per-branch stack pushes;
- native stacked-pull-request submission;
- local and remote stack synchronization;
- merged-layer reconciliation; and
- navigation between stack layers.

### GitHub

GitHub owns:

- the published native stack object;
- stack trunk and ordered pull-request membership;
- trunk-relative protection and check evaluation;
- merge-queue integration;
- all-or-nothing direct prefix merges;
- single-pull-request queue processing and automatic suffix rebases; and
- automatic rebase and retarget behavior after a partial merge.

### `review-code-change`

`review-code-change` remains read-only. It reviews one exact layer against its
exact predecessor and returns an evidence-bound verdict.

### `babysit-pr`

`babysit-pr` owns CI, published feedback, review threads, and readiness for one
exact pull request. Stack mutation and native stack merge authority are
withheld.

When a fix would change a stack member, `babysit-pr` returns a stack-fix
handback. It does not push the fix, cascade the upstack, or merge an implicit
prefix.

## Truth model

Truth advances through four phases:

```text
proposed
  plan and immutable source
    ↓
materialized
  git commits, branches, and verified gh stack state
    ↓
published
  native GitHub stack, pull requests, and remote git refs
    ↓
merged
  GitHub merge state and mainline representation
```

Each phase supersedes weaker topology records.

### Proposed truth

The plan is authoritative only before materialization. It records semantic
slugs, intent, order, selectors, intermediate-state constraints, and validation
requirements.

### Materialized truth

Live git commits and branches establish layer contents. `gh stack view --json`
establishes local stack membership and order. It also refreshes pull-request
state and may save `.git/gh-stack`, so it is a scoped local mutation rather than
a side-effect-free read. The skill cross-checks its output with git before
accepting the chain.

The `.git/gh-stack` file is operational state owned by the dependency. The skill
never parses that file directly. It consumes the documented CLI surface.

### Published truth

The native GitHub stack establishes trunk and ordered pull-request membership.
Remote refs establish branch heads. Pull requests establish candidate heads,
bases, checks, reviews, and mergeability. The exact pull-request head commit
carries the remaining machine-readable `carve-changesets` identity and
provenance.

Local `gh stack` state remains useful for execution. It cannot override live
GitHub state.

### Merged truth

GitHub merge state and live mainline establish merged truth. The skill must also
prove the merged prefix on that mainline and the live-chain equivalence
invariant below.

## Live-chain equivalence invariant

At every materialized or later phase, the exact current trunk must represent the
already merged prefix in order, and applying every open suffix layer in native
stack order to that trunk must reproduce the active immutable source. Before any
merge, the prefix is empty. When the suffix is empty, the invariant reduces to
current trunk equaling the active source.

Any head, base, trunk, membership, or source-lineage change invalidates this
proof. The skill must re-establish it after repair, recovery, every native
landing, and synchronization, and before returning candidates to lifecycle
owners or claiming a terminal state.

A changed trunk is not merely a new comparison base for the same source. Before
accepting it, the skill constructs and verifies a distinct immutable successor
source: the exact new trunk plus the preserved intended effect of the prior
active source. With separate source-publication authority, it publishes that
source at an exact ref and SHA on the selected remote, appends it to the ordered
lineage, and proves that the transition adds only the approved trunk change
while preserving the intended effect. A conflict, missing authority, or
unprovable transition blocks before any candidate rewrite. The ensuing rebase or
synchronization invalidates candidate evidence and must re-establish the
invariant against the successor source.

## Layer identity and metadata

A semantic slug identifies a changeset. Position comes from live stack order.
Branch names and numeric positions do not establish durable semantic identity.

Machine-readable trailers on each exact layer head commit retain only
information that GitHub stacks do not provide:

- semantic slug;
- non-empty ordered source lineage; and
- recovery provenance when a suffix has been corrected.

The immutable root source and active source are derived from the first and last
lineage entries. They are not stored separately. Every published lineage
identity includes the selected remote plus an exact branch and stamped commit.
Local-only reachability cannot establish durable source provenance.

Before reading a trailer, the skill verifies that the native pull-request head
and remote branch head identify the same commit. GitHub's preserved pull-request
head identity remains the lookup key after branch deletion. A missing trailer or
an unexplained head mismatch blocks reconstruction.

Native stack number, position, predecessor, trunk, and size must not be copied
into durable `carve-changesets` metadata. Those values come from GitHub and
`gh stack` at read time.

The redesign introduces a trailer-only metadata version for native stacks.
Pull-request bodies remain human-readable and carry no new machine-readable
`carve-changesets` block. Existing v1 and v2 commit trailers and pull-request
blocks remain historical input for legacy adoption. They do not establish the
post-adoption topology. The native trailer version is written only for a newly
materialized layer or a layer whose head changes for a semantic or recovery
reason. Legacy trailer fields are normalized when read rather than rewritten
solely for adoption.

## Capability contract

Capabilities are checked at the boundary that first needs them. Proposal-only
work requires git and Python. Local materialization requires:

- a tested compatible `gh-stack` extension version;
- `gh stack view --json`; and
- non-interactive `gh stack init` for explicit branches.

Publication, remote repair, recovery, and merge additionally require, as
applicable:

- an authenticated compatible GitHub CLI;
- `gh stack rebase`, `push`, `submit`, `sync`, and `merge`;
- every remote-mutating command accepting its operation mutation precondition as
  defined below and rejecting before any effect when it differs;
- queue operations that keep their operation mutation precondition fenced from
  admission through landing;
- rebase and sync operations that either skip trunk with `--no-trunk` or bind
  any fetched trunk/base state before rewriting candidates;
- a non-interactive submit mode that accepts and preserves every explicit
  per-layer pull-request title and body, even when the repository has a pull
  request template;
- GitHub native stacks enabled for the repository; and
- live read access to stack, pull-request, review, check, and merge state.

The skill checks capability before the affected mutation. Missing or
incompatible capability returns `blocked`. It does not download a substitute
tool or enter the retired custom stack path.

At the reviewed public-preview revision, the CLI does not expose the required
operation mutation preconditions or durable fencing for merges. Its automatic
submit path also cannot be relied on to preserve explicit per-layer bodies in a
repository with a pull-request template, and its default rebase cannot pause
after fetch for approval of a changed trunk. Capabilities are assessed per
operation: a future command may be usable without making every remote phase
usable. Until a tested version closes a phase's relevant gaps, that phase is
blocked. Post-command readback cannot substitute for a precondition because it
observes an unauthorized write only after it has occurred.

### Command effects and authority

The adapter treats dependency commands by their real effects:

| Command                | Material effects                                                                                     | Required disclosure and authority                                                                                      |
| ---------------------- | ---------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `gh stack init`        | Enables `rerere`, writes stack state, may create branches, and checks out the top branch             | Preview config, branch, state, and checkout changes; require local materialization authority                           |
| `gh stack view --json` | Reads GitHub and may refresh saved stack state                                                       | Declare the refresh; require scoped local-state authority and verify that the checkout is unchanged                    |
| `gh stack rebase`      | By default fetches, may move trunk, rewrites layer commits, and records recovery state               | Use `--no-trunk` for a bounded suffix fix; otherwise preview the new base and complete affected set; require authority |
| `gh stack push`        | Updates active remote branches and may partly succeed                                                | Fence selected refs plus the topology and PR state that select them; require publish or stack mutation authority       |
| `gh stack submit`      | Pushes branches, creates or updates pull requests, disables auto-merge, and updates the native stack | Fence refs, expected PR identity or absence, PR state, and topology; require separate authority for every transition   |
| `gh stack sync`        | May fetch, fast-forward trunk, rebase, push, relink, save state, and prune when requested            | Fence every enabled phase's writes and all state that selects or authorizes them; require authority for every mutation |
| `gh stack merge`       | Directly merges an exact prefix or enqueues one exact bottom pull request                            | Fence the prefix and every automatically affected suffix resource; require authority for the complete affected set     |

Status-only work must not hide the local refresh performed by
`gh stack view --json`. If the caller has not authorized that bounded state
write, the skill reports local stack state as unavailable and relies only on
side-effect-free git and GitHub reads. It does not silently widen authority.

A bounded repair or recovery always uses `rebase --no-trunk` so the dependency
does not fetch or move the comparison base. A deliberate trunk refresh is a
separate operation: the dependency must expose a fetch/read phase, successor-
source construction and remote verification, a new manifest, and an expected-
base-bound rewrite phase. If it cannot pause before rewriting candidates against
the newly observed trunk, that operation is blocked.

## Workflow

### 1. Resolve

Resolve the repository, checkout, worktree, source, base, approved validation,
requested terminal boundary, and mutation authority.

Before each phase, verify every `gh stack` capability needed to reach the
requested boundary. Missing later-phase capability does not block a verified
local `chain_ready` result.

### 2. Propose

Analyze the complete source diff. Produce ordered semantic layers with explicit
intent, inclusions, exclusions, selectors, intermediate-state constraints, and
validation.

The proposal must explain why each seam is valid and why identified indivisible
work remains together.

### 3. Materialize

Create the ordered layer commits and branches without mutating the immutable
source.

`gh stack modify` cannot split one source branch into semantic layers, so the
existing extraction machinery remains responsible for this step.

After creating the branches:

1. Verify each branch tree and predecessor diff.
2. Verify the reconstructed full chain against the immutable source.
3. Run `gh stack init --base <base> <branch-1> ... <branch-n>`.
4. Read `gh stack view --json`.
5. Cross-check trunk, ordered branches, heads, and git ancestry.
6. Run the required per-layer validation and review.

`chain_ready` requires agreement among semantic plan, live git, and `gh stack`.
The plan no longer controls materialized topology.

### 4. Publish

Require publish authority. Before initial publication, verify that every entry
in the ordered source lineage resolves at its stamped SHA on the selected
remote. A source branch is never pushed implicitly; a missing remote source
blocks with the exact prerequisite and authority needed to publish it.

Produce a dry-run manifest containing the submit operation mutation
precondition; the proposed repository, remote, trunk, ordered branches, branch
heads, pull requests, native stack, and draft or ready state of every pull
request; every lineage ref and SHA; and the exact title and human-readable body
for every layer. Each body retains the layer's intent, non-goals, intentional
incompleteness, and the later layer that resolves it.

Execution invokes a tested non-interactive `gh stack submit` mode through the
skill's single command surface. It is available only when the dependency accepts
and preserves the manifest's exact per-layer titles and bodies despite
repository templates, and binds every ref, pull-request, and native-stack effect
to the submit operation precondition. New pull requests are drafts unless the
manifest requests ready-for-review pull requests and the caller separately
authorizes that transition. The preview includes every existing draft that would
be opened and every existing pull request whose auto-merge setting would be
disabled; those are separate authorities. A dependency that derives bodies from
templates, requires an unfenced post-submit metadata edit, or refreshes an
expectation after manifest approval does not satisfy this contract.

After submission:

1. Read the native GitHub stack.
2. Verify trunk and ordered pull-request membership.
3. Verify every remote head and pull-request base.
4. Verify every exact pull-request title and body and every intended state
   transition.
5. Verify every lineage ref and stamped SHA.
6. Verify every layer diff.

No post-submit pull-request metadata edit is required. Commit trailers are the
sole new machine-readable semantic and provenance record.

An exit code alone never proves publication.

### 5. Monitor

Delegate each exact pull request to `babysit-pr` with stack mutation and merge
authority withheld.

Independent pull requests may be monitored in parallel. Their lifecycle owners
must not run competing branch updates.

Readiness remains candidate-bound. A stack-wide mutation invalidates every
affected candidate and returns it to the required validation and review gates.

### 6. Repair

When feedback requires a head-changing fix, `babysit-pr` returns a stack-fix
handback containing the exact pull request, old head, finding, accepted scope,
and current stack identity.

`carve-changesets` then:

1. Reclaims exclusive stack mutation ownership.
2. Applies the fix to the layer that owns it.
3. Creates or verifies a successor source when the accepted result has changed.
4. Runs `gh stack rebase --no-trunk --upstack <owning-layer>` across only the
   affected upstack.
5. Runs a compare-and-swap-capable `gh stack push`.
6. Reads back local git, `gh stack`, remote refs, and GitHub pull requests.
7. Re-proves the live-chain equivalence invariant.
8. Rebuilds invalidated validation, review, CI, and feedback evidence.
9. Returns each corrected pull request to its lifecycle owner.

`gh stack` owns propagation. `carve-changesets` owns the fix placement,
provenance, authority, and proof.

### 7. Merge

Collect verified readiness for the exact contiguous prefix selected for merge.

Before mutation, resolve and report:

- every pull request affected by the native merge;
- exact candidate heads;
- current stack and trunk identity;
- applicable checks, reviews, and protection gates;
- merge method and merge-queue behavior; and
- authority covering the complete mutation set: the direct prefix plus every
  suffix branch and pull request the direct landing may rebase or retarget, or
  the queued bottom pull request plus that same affected suffix.

For a direct prefix merge, invoke
`gh stack merge <boundary-pr-number> --yes [--merge-method <method>]`. The
boundary pull request selects the contiguous prefix. A stack number may replace
it only when authority covers the whole stack. The dependency must atomically
reject the request unless the direct-merge operation precondition still holds,
including exact trunk, native membership, and every prefix and automatically
affected suffix pull request's identity, head, base, and state. Partial direct
merge is blocked when the dependency cannot durably fence and authorize that
complete affected set; whole-stack direct merge remains possible when its own
precondition is supported. A direct merge is one all-or-nothing service
operation.

On merge-queue repositories, admit only the current bottom pull request with
`gh stack merge <bottom-pr-number> --yes`. The queue chooses the merge method,
so the wrapper omits method flags and records that they do not apply. The
manifest includes the queue-merge operation precondition. The dependency must
fence it at admission and keep it effective until landing, rejecting or
canceling the operation before native suffix mutation if any ref, pull request,
trunk, or membership field changes.

Queue admission is an asynchronous handoff, not merge completion. Its authority
covers the native heads and bases produced by landing the exact bottom candidate
against the exact fenced suffix; it does not cover arbitrary replacement heads.
After landing, the skill synchronizes, reads every new head, and rebuilds all
candidate-bound validation, review, CI, and feedback evidence before separately
authorizing and admitting the next bottom pull request. It never admits a prefix
that GitHub may process in multiple autonomous groups. If the dependency cannot
maintain the operation fence through landing, queue admission is blocked.

This one-at-a-time queue admission is lifecycle coordination through the native
stack engine, not a return to custom propagation: GitHub and `gh stack` still
own merge, rebase, retargeting, and synchronization mechanics.

After completion:

1. Read the asynchronous merge result when applicable.
2. Run `gh stack sync`.
3. Verify every merged pull request on the trunk.
4. Verify the remaining suffix's new heads and bases.
5. Rebuild invalidated evidence.
6. Prove that the merged prefix is represented on the exact current trunk and
   that current trunk plus every open suffix layer reproduces the active source.
7. When the suffix is empty, additionally prove current trunk alone equals the
   active source.

### 8. Recover

An accepted fix after a prefix merge may change the intended final result.
`carve-changesets` still creates or verifies a distinct immutable successor
source and continuous lineage.

Before any remote push, submit, or sync for a recovered suffix, every root and
successor identity in that lineage must resolve at its exact stamped SHA on the
selected remote. The preview includes those remote identities. Post-mutation
readback verifies them again. A local-only source blocks recovery because a
fresh clone could not reconstruct the published lineage.

The skill applies the fix at the correct open layer and delegates suffix
mechanics to `gh stack rebase --no-trunk --upstack <owning-layer>` and `push`.
It does not manually recreate propagation.

Recovery preserves merged positions and pull-request identities. It rebuilds all
evidence bound to changed candidates and re-proves the live-chain equivalence
invariant before returning them to lifecycle owners.

## Command-surface changes

The consolidated CLI remains the only `carve-changesets` command surface. It
wraps exact `gh stack` argv and performs preflight and readback.

Retire or replace:

| Current command   | Target behavior                                                             |
| ----------------- | --------------------------------------------------------------------------- |
| `create-chain`    | Materialize semantic layers, then adopt them with `gh stack init`           |
| `push-chain`      | Preview and invoke `gh stack push`                                          |
| `pr-create`       | Preview and invoke `gh stack submit`                                        |
| `propagate`       | Remove; use `gh stack rebase --no-trunk` plus fenced `push`                 |
| `merge-propagate` | Invoke a direct exact-prefix or one queued-bottom merge, then verified sync |
| `recover-suffix`  | Retain semantic recovery, delegate mechanics to `gh stack`                  |
| `status`          | Combine git, `gh stack view --json`, and live GitHub evidence               |

The wrapper must never infer a mutation target from the checked-out branch
alone. It resolves the exact stack and branches before invoking the dependency.

## Mutation and readback contract

Every operation with local or remote side effects has two phases.

Each operation mutation precondition contains the exact repository and selected
remote, plus:

- every direct and automatic write the operation may perform;
- every resource state that selects mutation targets or bounds authority, even
  when the operation does not write that resource; and
- expected absence for every ref, pull request, or native stack the operation
  may create.

The concrete fence is operation-scoped:

- push binds active native membership and order, the pull-request merged or
  queued state that selects active branches, and every selected branch ref's
  exact SHA or expected absence;
- submit and legacy adoption bind every ref SHA or absence, per-branch expected
  pull-request identity or absence, existing pull-request head, base, open or
  closed, draft or ready, queue, and auto-merge state, exact native-stack
  identity or absence, trunk and order, and every explicitly authorized
  transition;
- sync binds the exact enabled phases and every trunk, ref, pull request, and
  topology field those phases read to select targets or may write;
- direct merge binds the exact trunk and base, native membership and order, and
  every prefix and automatically affected suffix ref and pull-request identity,
  head, base, and state; and
- queue merge binds the admitted bottom pull request plus the entire affected
  suffix and keeps that fence effective through landing.

The dependency must evaluate the applicable precondition atomically with every
ref, pull-request, topology, queue, or merge mutation. A preliminary read
followed by an unfenced service request does not satisfy it. An operation is
blocked if the tested dependency cannot express its complete scoped fence;
support for a different operation does not widen that capability.

### Preview

The skill prints a bounded manifest of exact targets and intended effects. It
does not invoke the mutating `gh stack` command.

### Execute

The skill re-verifies the manifest, invokes the exact command, and reads back
all affected state.

A successful command followed by conflicting readback returns `blocked`.
Readback always classifies every declared target as changed as expected,
unchanged, or changed unexpectedly.

For every push-capable `gh stack` operation, include the proposed head of every
active branch and enforce the applicable operation precondition. If any ref
precondition fails, classify all declared targets before retry; never create or
overwrite the unexpected ref. After any result, read every remote ref and report
which leases advanced, which were rejected, and which heads are unexpected. A
retry starts from that new snapshot; it never replays the stale manifest.

For direct merge, enforce its operation precondition and verify that the
complete prefix either merged or remained open. For queue-backed merge, durably
fence its operation precondition through landing. Distinguish admission from
landing, and do not admit another pull request until the rebased suffix has
passed fresh candidate-bound gates.

## Interruption and divergence

The skill must account for `gh stack` rebase state, stack locks, merge queues,
and local or remote divergence.

In unattended execution:

- any prompt requirement returns `blocked`;
- a rebase conflict preserves the dependency's recovery state and reports the
  exact continuation command;
- a diverged local and remote stack performs no write;
- a partly successful push preserves the advanced refs and requires a fresh
  manifest for the rejected remainder;
- a landed queued pull request preserves the remaining native suffix and blocks
  its next admission until synchronization and fresh exact-head gates complete;
- an interrupted modify or rebase is never discarded automatically;
- a stack lock identifies the owning process or last trustworthy state when
  available; and
- readback distinguishes no-op success from completed mutation.

The skill never parses undocumented dependency files to manufacture recovery. It
uses documented continuation, abort, checkout, view, and sync commands.

## Legacy adoption

The redesigned skill has one stack engine.

An existing unlinked v1 or v2 chain must be adopted before further publication,
repair, propagation, or merge work. Adoption must:

1. Resolve every exact branch, head, pull request, and predecessor base.
2. Verify same-repository ownership and linear ancestry.
3. Verify semantic slugs and source provenance from v1 and v2 commit trailers,
   using legacy pull-request blocks only as adoption evidence.
4. Normalize legacy metadata in memory to a semantic slug, non-empty source
   lineage, and recovery provenance. Ignore legacy index, predecessor, and
   topology fields after native adoption.
5. Prove the complete chain against the active source.
6. Run non-interactive `gh stack init` over the unchanged open branches.
7. Use the fenced non-interactive submit path to adopt the existing pull
   requests into the native GitHub stack.
8. Read back local and remote stack state.

Merged legacy commits and pull-request blocks remain unchanged historical
evidence. Adoption does not rewrite an open head merely to change its metadata
version. The native trailer version is added when a layer is newly materialized
or its head legitimately changes. Native GitHub state controls the adopted open
topology.

The adoption path does not invoke `gh stack link`. That command can push branch
arguments, create pull requests, retarget existing pull-request bases, and
change native stack membership, but it is not covered by the required operation
mutation precondition. If the tested `gh stack submit` version cannot adopt the
existing pull requests non-interactively through the fenced submit path,
adoption returns `blocked` rather than widening to `link`.

If adoption cannot be proved safe, return `blocked` with one concrete action.
The skill does not resume the retired custom stack manager.

## Terminal states

### `plan_ready`

Requires a complete validated semantic plan and no materialized stack.

### `chain_ready`

Requires exact layer commits and branches, a verified local `gh stack`, current
per-layer validation and review, and whole-chain equivalence.

### `prs_open`

Requires `chain_ready` evidence, one verified native GitHub stack, exact remote
heads and pull-request bases, current semantic metadata, and every applicable
non-merge gate.

### `all_merged`

Requires every changeset pull request in the chain verified merged, an empty
open suffix, native synchronization complete, current trunk equivalence to the
active source proven, required validation passing, and authorized cleanup
complete or precisely limited.

### `blocked`

Requires one concrete blocker, exact phase and identities reached, preserved
partial artifacts, last trustworthy evidence, and one action needed to resume.

## Validation strategy

### Contract tests

Verify:

- responsibility and authority boundaries;
- required `gh stack` capability;
- semantic identity independent of stack position;
- root and active source identity derived from ordered lineage;
- topology read through documented surfaces;
- one machine-readable semantic and provenance record for new native layers;
- in-place legacy adoption without a metadata-only head rewrite;
- no legacy stack-manager fallback;
- no single-PR implicit stack mutation; and
- candidate-evidence invalidation after stack-wide changes;
- current trunk plus the open suffix reproducing the active source; and
- `all_merged` requiring an empty suffix and every chain pull request merged.

### Unit tests

Cover:

- version and capability parsing;
- `gh stack view --json` decoding;
- dry-run manifests;
- exact argv construction;
- command-effect and authority classification;
- default-rebase fetch and trunk/base effect classification;
- fix-only `rebase --no-trunk --upstack <branch>` construction;
- phased trunk-refresh manifests and expected-base enforcement;
- operation-scoped ref, pull-request, trunk, and native-membership
  preconditions, including their target-selection and authority inputs;
- expected pull-request absence and auto-merge-state fencing for submit;
- durable affected-suffix fencing for direct and queue merge;
- initial-publication source-lineage remote verification;
- explicit per-layer body preservation with a repository pull-request template;
- successor-source construction and equivalence proof after trunk drift;
- post-command readback;
- partial push and queued-merge state classification;
- interrupted and divergent states;
- native commit-trailer decoding;
- legacy pull-request blocks accepted only as adoption evidence;
- v1 and v2 trailer normalization with native topology superseding positional
  fields;
- in-place legacy adoption checks; and
- terminal-state rendering.

### Integration tests

Use disposable repositories and controlled `gh stack` fixtures to cover:

- materialization and adoption;
- native submission;
- legacy pull-request adoption through fenced submit, including a blocked case
  when only unfenced link can represent the chain;
- a lower-layer fix and cascading rebase;
- base movement before a default rebase, requiring a new manifest before any
  rewrite and a remotely stamped successor source before accepting the base;
- a rejected branch lease after earlier branches have updated;
- a remote advance after manifest approval that rejects without overwriting it;
- a same-named remote branch created after manifest approval that rejects
  without mutation;
- a pull request created after expected absence was approved that rejects submit
  without mutation;
- an auto-merge-state change after approval that rejects submit without
  mutation;
- initial publication blocked by a missing remote source-lineage ref;
- explicit per-layer bodies preserved despite a repository pull-request
  template;
- pull-request base, draft state, or native membership changing after approval
  and rejecting before submit or sync mutation;
- local and remote divergence;
- partial publication;
- an all-or-nothing direct prefix merge;
- a partial direct merge blocked without authority and a fence for every
  automatically affected suffix resource;
- a selected pull-request head advance that rejects direct merge and queue
  admission;
- trunk movement or native stack reordering that rejects direct merge before
  landing;
- a queue whose group limit is smaller than the desired prefix, proving that
  only one bottom pull request is admitted before suffix revalidation;
- an upstack head advance during queue residence that cancels or rejects the
  landing before suffix mutation;
- native membership or trunk movement during queue residence that cancels or
  rejects the landing before mutation;
- post-merge synchronization followed by live-chain equivalence;
- partial direct-prefix and one-bottom queue landings whose trunk plus open
  suffix reproduces the active source;
- successor-source recovery followed by live-chain equivalence; and
- full-chain mainline equivalence only after the suffix is empty.

### Evaluations

Representative evaluations must distinguish:

- a valid semantic carve from a merely even-sized split;
- indivisible work from convenient but unsafe separation;
- dependency failure from semantic decomposition failure;
- stack command success from verified state transition;
- single-PR authority from stack-prefix authority; and
- native adoption from permanent dual-mode behavior.

## Delivery strategy

This design is too broad for one implementation changeset. After approval, the
work should be decomposed into an epic with independently reviewable children:

1. Revise the normative contract and add the `gh stack` capability adapter.
2. Materialize semantic layers and adopt them into local stack tracking.
3. Replace publication and status with native submission and readback.
4. Add stack-fix handbacks and candidate-evidence rebuilding.
5. Replace merge and recovery mechanics with native operations.
6. Add legacy adoption and remove the custom stack manager.

Caller migrations and ticket-graph changes follow proven capability. They are
not part of the design-document changeset.

## Trade-offs

### Benefits

- One stack engine controls topology and mutation.
- The skill's purpose narrows to semantic decomposition and proof.
- GitHub behavior is available without duplicating it locally.
- Native stack UI, checks, queues, and merges become first-class.
- Custom force-push and retarget code disappears.
- Ownership boundaries become easier to audit.

### Costs and accepted limitations

- `carve-changesets` gains a hard dependency on a preview tool and API.
- Compatible versions must be tested and bounded.
- Publication and merge remain unavailable until `gh stack` exposes the complete
  native mutation precondition and durable queue fencing.
- Dependency commands may require interactive recovery.
- Native stack behavior may change during public preview.
- Existing chains require adoption before continued operation.
- Stack-wide rebases may invalidate evidence for several layers at once.

These costs are accepted because duplicating the stack engine would preserve
more code, more state, and more ways to corrupt a published chain.

## Rejected alternatives

### Native-aware dual mode

Keep the custom stack manager and add native-stack detection and API support.

Rejected because two engines would own the same branches, pull-request bases,
and propagation behavior. Capability drift would multiply rather than shrink.

### Publication-only integration

Keep custom local topology and use `gh stack link` only when opening pull
requests.

Rejected because the skill would retain cascading rebase, push, synchronization,
and post-merge propagation machinery. Most duplicated responsibility would
remain.

### Delegate semantic carving to `gh stack modify`

Create one stack and use the interactive modifier to derive the layers.

Rejected because `gh stack modify` cannot split one branch into semantic
changesets. It also lacks the source-equivalence, migration-safety, and review
reasoning required by this skill.

### Trust dependency state without independent proof

Treat successful `gh stack` commands as sufficient evidence.

Rejected because command success does not prove the intended branches, pull
requests, or mainline result. `carve-changesets` remains accountable for exact
identity, authority, and equivalence.
