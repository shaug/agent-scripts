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
partly succeed, and a queued prefix may land in separate groups. The design must
preserve exact identity and recovery across both cases.

Keeping both stack engines would preserve duplicated state and conflicting
mutation paths. It would also force `carve-changesets` to understand every
change in GitHub's stack behavior. A single stack engine gives each component a
clearer purpose.

References:

- [GitHub stacked pull requests announcement](https://github.blog/changelog/2026-07-30-stacked-pull-requests-are-now-in-public-preview/)
- [`gh-stack` repository](https://github.com/github/gh-stack)
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
- queue processing that may land one authorized prefix in separate groups; and
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
prove that the represented result matches the active immutable source.

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

Proposal-only work requires git and Python. Materialization and every later
boundary require:

- an authenticated compatible GitHub CLI;
- a tested compatible `gh-stack` extension version;
- `gh stack view --json`;
- non-interactive `gh stack init` for explicit branches;
- `gh stack rebase`, `push`, `submit`, `sync`, and `merge`;
- GitHub native stacks enabled for the repository; and
- live read access to stack, pull-request, review, check, and merge state.

The skill checks capability before the affected mutation. Missing or
incompatible capability returns `blocked`. It does not download a substitute
tool or enter the retired custom stack path.

### Command effects and authority

The adapter treats dependency commands by their real effects:

| Command                | Material effects                                                                          | Required disclosure and authority                                                                                     |
| ---------------------- | ----------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `gh stack init`        | Enables `rerere`, writes stack state, may create branches, and checks out the top branch  | Preview config, branch, state, and checkout changes; require local materialization authority                          |
| `gh stack view --json` | Reads GitHub and may refresh saved stack state                                            | Declare the refresh; require scoped local-state authority and verify that the checkout is unchanged                   |
| `gh stack rebase`      | Rewrites local layer commits and records recovery state                                   | Preview the affected suffix; require stack mutation authority                                                         |
| `gh stack push`        | Updates active remote branches with per-branch leases and may partly succeed              | Preview old and proposed heads; require publish or stack mutation authority                                           |
| `gh stack submit`      | Pushes branches, creates or updates pull requests, and updates the native stack           | Preview remote, heads, pull requests, and draft or ready state; require publish and any ready-state authority         |
| `gh stack sync`        | May fetch, fast-forward trunk, rebase, push, relink, save state, and prune when requested | Preview every enabled phase; require authority for every resulting local or remote mutation                           |
| `gh stack merge`       | Directly merges an exact prefix or enqueues it                                            | Preview the boundary pull request, full prefix, method or queue behavior; require merge authority for the full prefix |

Status-only work must not hide the local refresh performed by
`gh stack view --json`. If the caller has not authorized that bounded state
write, the skill reports local stack state as unavailable and relies only on
side-effect-free git and GitHub reads. It does not silently widen authority.

## Workflow

### 1. Resolve

Resolve the repository, checkout, worktree, source, base, approved validation,
requested terminal boundary, and mutation authority.

When the requested boundary is `chain_ready` or later, verify `gh stack`
capability before materialization.

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

Require publish authority. Produce a dry-run manifest containing the exact
repository, remote, trunk, ordered branches, branch heads, proposed pull
requests, expected native stack, and the proposed draft or ready state of every
pull request.

Execution invokes `gh stack submit --auto --remote <remote>` through the skill's
single command surface. New pull requests are drafts in this mode. The wrapper
adds `--open` only when the manifest requests ready-for-review pull requests and
the caller has separately granted authority for that state transition. Since
`--open` also marks existing drafts ready, the preview lists every affected pull
request. Layer commit messages already contain the human-readable intent,
non-goals, and intentional incompleteness from which automatic pull-request text
is derived.

After submission:

1. Read the native GitHub stack.
2. Verify trunk and ordered pull-request membership.
3. Verify every remote head and pull-request base.
4. Verify every layer diff.

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
4. Runs `gh stack rebase` across the affected upstack.
5. Runs `gh stack push` or `gh stack sync` as appropriate.
6. Reads back local git, `gh stack`, remote refs, and GitHub pull requests.
7. Rebuilds invalidated validation, review, CI, and feedback evidence.
8. Returns each corrected pull request to its lifecycle owner.

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
- authority covering the complete affected prefix.

For a prefix merge, invoke
`gh stack merge <boundary-pr-number> --yes [--merge-method <method>]`. The
boundary pull request selects the contiguous prefix. A stack number may replace
it only when authority covers the whole stack. On merge-queue repositories, the
queue chooses the merge method, so the wrapper omits method flags and records
that they do not apply. The custom sequential merge and suffix propagation path
is retired.

A direct merge is one all-or-nothing service operation. Queue admission is an
asynchronous handoff, not merge completion. The selected pull requests may land
in separate groups. After every observed landing, the skill records the exact
merged set, rebuilds evidence for changed open candidates, and resumes only from
a fresh live prefix.

After completion:

1. Read the asynchronous merge result when applicable.
2. Run `gh stack sync`.
3. Verify every merged pull request on the trunk.
4. Verify the remaining suffix's new heads and bases.
5. Rebuild invalidated evidence.
6. Verify the resulting mainline tree and behavior against the active source.

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
mechanics to `gh stack rebase`, `push`, and `sync`. It does not manually
recreate propagation.

Recovery preserves merged positions and pull-request identities. It rebuilds all
evidence bound to changed candidates.

## Command-surface changes

The consolidated CLI remains the only `carve-changesets` command surface. It
wraps exact `gh stack` argv and performs preflight and readback.

Retire or replace:

| Current command   | Target behavior                                                                 |
| ----------------- | ------------------------------------------------------------------------------- |
| `create-chain`    | Materialize semantic layers, then adopt them with `gh stack init`               |
| `push-chain`      | Preview and invoke `gh stack push`                                              |
| `pr-create`       | Preview and invoke `gh stack submit`                                            |
| `propagate`       | Remove; use verified `gh stack sync` or `rebase` plus `push`                    |
| `merge-propagate` | Preview and invoke exact-prefix `gh stack merge`, then verified `gh stack sync` |
| `recover-suffix`  | Retain semantic recovery, delegate mechanics to `gh stack`                      |
| `status`          | Combine git, `gh stack view --json`, and live GitHub evidence                   |

The wrapper must never infer a mutation target from the checked-out branch
alone. It resolves the exact stack and branches before invoking the dependency.

## Mutation and readback contract

Every operation with local or remote side effects has two phases.

### Preview

The skill prints a bounded manifest of exact targets and intended effects. It
does not invoke the mutating `gh stack` command.

### Execute

The skill re-verifies the manifest, invokes the exact command, and reads back
all affected state.

A successful command followed by conflicting readback returns `blocked`.
Readback always classifies every declared target as changed as expected,
unchanged, or changed unexpectedly.

For `gh stack push`, capture the old and proposed head of every active branch.
After any result, read every remote ref and report which leases advanced, which
were rejected, and which heads are unexpected. A retry starts from that new
snapshot; it never replays the stale manifest.

For direct merge, verify that the complete selected prefix either merged or
remained open. For queue-backed merge, distinguish admission from landing and
track each landed group until the selected prefix reaches a terminal state.

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
- a partly landed queued prefix preserves each merged group and resumes from the
  remaining live prefix;
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
7. Submit or link the native GitHub stack.
8. Read back local and remote stack state.

Merged legacy commits and pull-request blocks remain unchanged historical
evidence. Adoption does not rewrite an open head merely to change its metadata
version. The native trailer version is added when a layer is newly materialized
or its head legitimately changes. Native GitHub state controls the adopted open
topology.

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

Requires every selected pull request verified merged, native synchronization
complete, final mainline equivalence proven, required validation passing, and
authorized cleanup complete or precisely limited.

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
- candidate-evidence invalidation after stack-wide changes.

### Unit tests

Cover:

- version and capability parsing;
- `gh stack view --json` decoding;
- dry-run manifests;
- exact argv construction;
- command-effect and authority classification;
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
- a lower-layer fix and cascading rebase;
- a rejected branch lease after earlier branches have updated;
- local and remote divergence;
- partial publication;
- an all-or-nothing direct prefix merge;
- a queued prefix that lands in separate groups;
- post-merge synchronization;
- successor-source recovery; and
- final source equivalence.

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
