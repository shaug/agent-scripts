# Carve Changesets on GitHub Stacks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild `carve-changesets` so it owns semantic decomposition and proof
while GitHub's native `gh stack` extension is the sole engine for stack
topology, publication, synchronization, and merge mechanics.

**Architecture:** Preserve the existing planning and changeset-materialization
core, then place a narrow `gh stack` adapter beneath a native topology model and
operation-scoped transition planner. Local operations become native immediately.
Every remote transition is derived from fresh Git, GitHub, and
`gh stack view --json` evidence and fails with a structured `blocked` result
unless the installed extension exposes every required fence. The initially
supported preview profile therefore stops at `chain_ready`; it does not silently
fall back to the existing custom stack manager.

**Tech Stack:** Python 3.11 standard library, `unittest`, Git CLI, GitHub CLI,
`github/gh-stack` extension, JSON fixtures, existing `just` quality and eval
targets.

## Global Constraints

- Work on `scott/carve-changesets-gh-stack`; do not implement this multi-commit
  change on detached HEAD or directly on `main`.
- Treat [the proposal](../../../design/carve-changesets-on-gh-stack.md) as the
  product contract. When implementation pressure exposes ambiguity, amend the
  proposal in a dedicated design commit before changing behavior.
- `gh_stack.py` is the only module permitted to invoke `gh stack`. `github.py`
  remains the only module permitted to invoke other `gh` commands, and only for
  read-only GitHub evidence after the cutover.
- Do not infer a capability from a command name. Probe the installed extension,
  match its machine-readable and help surface to a tested profile, and require
  the operation's complete capability set before any automatic or direct
  mutation begins.
- Do not retain the custom publication, propagation, recovery, or merge path as
  a fallback. An unsupported remote transition returns `blocked` before local or
  remote mutation.
- Preserve one immutable source identity as `remote + branch + full SHA`. A
  trunk-drift recovery creates a new remotely stamped successor identity and
  appends it to lineage.
- Treat `gh stack view --json` as topology evidence, not as complete safety
  proof. Cross-check its branch heads, bases, PRs, trunk, remote refs, commit
  trailers, and GitHub PR state.
- Preserve dry-run-by-default behavior and require operation-specific authority
  for every remote effect, including effects performed indirectly by `gh stack`.
- Keep `babysit-pr` scoped to one exact PR. Its only stack-aware output is a
  typed handback naming the invalidated suffix and the required carve repair
  phase.
- Use `unittest`; do not add a new test framework or runtime dependency.
- Before each commit, update the newest `CHANGELOG.md` day section, backfill the
  previous entry with its full SHA, and leave the new entry without a SHA. Write
  the full Conventional Commit message to a temporary file with `apply_patch`,
  then commit with `git commit -F <file>`.
- Before each commit, run `just format`, `just lint`, and `just test`. Run the
  focused red/green commands in each task before the full gates.
- Record `carve-changesets` deterministic eval evidence from committed clean
  trees: one `before` record before behavior changes and one `after` record
  after the normative prose commit. Commit both result files.

## Verified Dependency Facts

The implementation is pinned to the command surface documented in
[GitHub's stacked PR CLI reference](https://docs.github.com/en/pull-requests/reference/stacked-prs-cli-commands)
and independently represented by a checked-in contract fixture.

- `gh stack init --base <trunk> <branches...>` adopts an explicit ordered branch
  chain and enables rerere.
- `gh stack view --json` emits `trunk`, `currentBranch`, and ordered `branches`;
  each branch contains `name`, `head`, `base`, `isCurrent`, `isMerged`,
  `isQueued`, `needsRebase`, and optional PR data.
- `gh stack rebase --no-trunk --upstack <branch>` can cascade a local suffix
  without refreshing trunk.
- `gh stack push` uses per-ref force-with-lease but can partially succeed.
- `gh stack submit` controls PR creation and native stack registration, but the
  reviewed preview has no explicit per-PR body input and does not accept the
  complete expected-old manifest required by this design.
- `gh stack merge` performs a direct prefix merge, or queues selected PRs when
  merge queues apply, but the reviewed preview does not expose the durable merge
  fence required by this design.
- `gh stack sync` combines fetch, trunk refresh, rebase, push, PR
  synchronization, and optional pruning; it is not a substitute for
  phase-separated recovery because its noninteractive divergence behavior and
  target set are insufficiently fenced.

The first supported profile intentionally grants only `LOCAL_INIT`, `VIEW_JSON`,
and `LOCAL_REBASE_NO_TRUNK`. Remote capabilities remain absent until an exact
extension version passes repository contract tests for those semantics.

## File and Responsibility Map

| Path                                                     | Responsibility after cutover                                                                                                       |
| -------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `skills/carve-changesets/scripts/gh_stack.py`            | Sole subprocess adapter for `gh stack`; profile probing; exact argv construction; JSON decoding boundary.                          |
| `skills/carve-changesets/scripts/native_stack.py`        | Typed native topology, cross-source reconciliation, materialized/published truth, live-equivalence checks.                         |
| `skills/carve-changesets/scripts/transitions.py`         | Operation manifests, authority inputs, required capabilities, dry-run preview, terminal results, pre/post-readback classification. |
| `skills/carve-changesets/scripts/metadata.py`            | Trailer-only v3 identity and lineage; legacy v1/v2 PR-block normalization for adoption evidence.                                   |
| `skills/carve-changesets/scripts/chain.py`               | Semantic changeset materialization, followed by native `gh stack init` adoption and exact topology readback.                       |
| `skills/carve-changesets/scripts/rehydrate.py`           | Reconstruct active stack truth from native topology, GitHub PR reads, remote refs, and commit trailers.                            |
| `skills/carve-changesets/scripts/validate.py`            | Step validation and current-trunk plus open-suffix equivalence proof.                                                              |
| `skills/carve-changesets/scripts/cli.py`                 | Consolidated user surface and structured terminal-state rendering.                                                                 |
| `skills/carve-changesets/scripts/github.py`              | Read-only repository and PR evidence; no PR create/edit/merge operations.                                                          |
| `skills/carve-changesets/scripts/propagate.py`           | Deleted after native transition cutover.                                                                                           |
| `skills/carve-changesets/scripts/recovery.py`            | Deleted after successor-lineage planning moves to `transitions.py`.                                                                |
| `skills/carve-changesets/references/*.md` and `SKILL.md` | Normative native-stack workflow, authority, terminal states, handbacks, and schema.                                                |

## Public Interfaces to Stabilize

The tasks below may add private helpers, but these types and functions are the
cross-module contract:

```python
class StackCapability(str, Enum):
    LOCAL_INIT = "local_init"
    VIEW_JSON = "view_json"
    LOCAL_REBASE_NO_TRUNK = "local_rebase_no_trunk"
    FENCED_PUSH = "fenced_push"
    FENCED_SUBMIT = "fenced_submit"
    FENCED_SYNC = "fenced_sync"
    FENCED_MERGE = "fenced_merge"
    EXPLICIT_PULL_REQUEST_BODIES = "explicit_pull_request_bodies"
    DURABLE_QUEUE_FENCE = "durable_queue_fence"
    PHASED_TRUNK_REFRESH = "phased_trunk_refresh"


@dataclass(frozen=True)
class GhStackProfile:
    version: str
    capabilities: frozenset[StackCapability]


@dataclass(frozen=True)
class NativePullRequest:
    number: int
    url: str
    state: str


@dataclass(frozen=True)
class NativeLayer:
    branch: str
    head: str
    base: str
    merged: bool
    queued: bool
    needs_rebase: bool
    pull_request: NativePullRequest | None


@dataclass(frozen=True)
class NativeStackSnapshot:
    trunk_branch: str
    trunk_head: str
    current_branch: str
    layers: tuple[NativeLayer, ...]


class TerminalState(str, Enum):
    PLAN_READY = "plan_ready"
    CHAIN_READY = "chain_ready"
    PRS_OPEN = "prs_open"
    ALL_MERGED = "all_merged"
    BLOCKED = "blocked"


class TruthPhase(str, Enum):
    PROPOSED = "proposed"
    MATERIALIZED = "materialized"
    PUBLISHED = "published"
    MERGED = "merged"


@dataclass(frozen=True)
class TransitionResult:
    state: TerminalState
    phase: str
    identities: tuple[str, ...]
    evidence: tuple[str, ...]
    blocker: str | None
    next_action: str | None


def materialize_native_stack(plan: dict, *, remote: str) -> NativeStackSnapshot:
    """Create semantic layers, register native topology, and prove materialized truth."""


def assess_chain_ready(
    snapshot: NativeStackSnapshot,
    *,
    validation: ValidationEvidence,
    review: ReviewEvidence,
    equivalence: LiveEquivalence,
) -> TransitionResult:
    """Return chain_ready only when every candidate-bound local gate is current."""


def preview_transition(
    operation: StackOperation,
    snapshot: NativeStackSnapshot,
    authority: AuthorityGrant,
) -> MutationManifest:
    """Return the complete direct and automatic effect set without mutation."""


def execute_transition(
    manifest: MutationManifest,
    *,
    profile: GhStackProfile,
) -> TransitionResult:
    """Fail before mutation unless every required capability and expected-old input exists."""
```

## Task 1: Establish Baseline Evidence and the Native Adapter

**Files:**

- Create: `skills/carve-changesets/scripts/gh_stack.py`

- Create:
  `skills/carve-changesets/scripts/tests/fixtures/gh-stack/profile-reviewed.json`

- Create:
  `skills/carve-changesets/scripts/tests/fixtures/gh-stack/view-open.json`

- Create: `skills/carve-changesets/scripts/tests/test_gh_stack.py`

- Modify: `skills/carve-changesets/scripts/tests/test_cli_safety.py`

- Create: `skills/carve-changesets/evals/results/<recorded-before-summary>.json`

- Modify: `CHANGELOG.md`

- [ ] Create the work branch and record the clean-tree baseline before changing
  behavior.

```bash
git switch -c scott/carve-changesets-gh-stack
just eval-record carve-changesets --stage before
```

Expected: the recorder writes one `before` summary whose `candidate.sha` equals
the pre-change HEAD. If the deterministic runner cannot start, the summary must
have status `attempted` and record the observed limitation.

- [ ] Add the baseline result and changelog entry, run all required checks, then
  commit it as `test: record carve changesets gh stack baseline` using a
  file-backed commit message.

```markdown
test: record carve changesets gh stack baseline

## Summary
- Record the deterministic carve-changesets behavior baseline
- Bind the evidence to the pre-native-stack candidate SHA

## Why
- Preserve comparable evidence before the normative workflow changes
```

- [ ] Add a failing adapter test that proves argv is a list, JSON mode is
  noninteractive, and the reviewed preview profile grants no remote capability.

```python
class GhStackClientTest(unittest.TestCase):
    def test_view_uses_machine_readable_noninteractive_command(self) -> None:
        runner = mock.Mock(return_value=VIEW_OPEN_JSON)
        client = GhStackClient(runner=runner)

        payload = client.view_json(allow_state_refresh=True)

        self.assertEqual(payload["trunk"], "main")
        runner.assert_called_once_with(
            ["gh", "stack", "view", "--json"],
            env={"GH_PAGER": "cat", "GH_PROMPT_DISABLED": "1"},
        )

    def test_view_requires_local_state_refresh_authority(self) -> None:
        runner = mock.Mock()
        client = GhStackClient(runner=runner)

        with self.assertRaisesRegex(GhStackError, "local-state authority"):
            client.view_json(allow_state_refresh=False)

        runner.assert_not_called()

    def test_reviewed_preview_profile_is_local_only(self) -> None:
        profile = reviewed_preview_profile("14fc42ed9b6c376a53b2f999f138d3bd26dac546")

        self.assertEqual(
            profile.capabilities,
            frozenset(
                {
                    StackCapability.LOCAL_INIT,
                    StackCapability.VIEW_JSON,
                    StackCapability.LOCAL_REBASE_NO_TRUNK,
                }
            ),
        )
```

- [ ] Capture `gh stack --version` and the `--help` surfaces for `init`, `view`,
  `rebase`, `push`, `submit`, `sync`, and `merge` from the reviewed revision.
  Store the normalized version string, source revision
  `14fc42ed9b6c376a53b2f999f138d3bd26dac546`, command flags, and SHA-256 of each
  normalized help output in `profile-reviewed.json`. Add `probe_profile()` tests
  that grant capabilities only when the live probe matches this fixture; an
  unknown or mismatched profile returns `blocked` with its observed version and
  differing command surface.

- [ ] Run the focused test and confirm it fails because `gh_stack.py` does not
  exist.

```bash
python3 -m unittest skills/carve-changesets/scripts/tests/test_gh_stack.py -v
```

- [ ] Implement the adapter and capability profile. Keep command execution
  injectable and reject shell strings.

```python
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Mapping, Sequence


class GhStackError(RuntimeError):
    pass


class StackCapability(str, Enum):
    LOCAL_INIT = "local_init"
    VIEW_JSON = "view_json"
    LOCAL_REBASE_NO_TRUNK = "local_rebase_no_trunk"
    FENCED_PUSH = "fenced_push"
    FENCED_SUBMIT = "fenced_submit"
    FENCED_SYNC = "fenced_sync"
    FENCED_MERGE = "fenced_merge"
    EXPLICIT_PULL_REQUEST_BODIES = "explicit_pull_request_bodies"
    DURABLE_QUEUE_FENCE = "durable_queue_fence"
    PHASED_TRUNK_REFRESH = "phased_trunk_refresh"


@dataclass(frozen=True)
class GhStackProfile:
    version: str
    capabilities: frozenset[StackCapability]


Runner = Callable[[Sequence[str], Mapping[str, str]], str]


def _run(argv: Sequence[str], env: Mapping[str, str]) -> str:
    completed = subprocess.run(
        list(argv),
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, **env},
    )
    return completed.stdout


def reviewed_preview_profile(version: str) -> GhStackProfile:
    return GhStackProfile(
        version=version,
        capabilities=frozenset(
            {
                StackCapability.LOCAL_INIT,
                StackCapability.VIEW_JSON,
                StackCapability.LOCAL_REBASE_NO_TRUNK,
            }
        ),
    )


class GhStackClient:
    def __init__(self, runner: Runner = _run) -> None:
        self._runner = runner

    def _capture(self, args: Sequence[str]) -> str:
        if isinstance(args, (str, bytes)):
            raise TypeError("gh stack arguments must be a sequence of tokens")
        return self._runner(
            ["gh", "stack", *args],
            env={"GH_PAGER": "cat", "GH_PROMPT_DISABLED": "1"},
        )

    def view_json(self, *, allow_state_refresh: bool) -> dict[str, object]:
        if not allow_state_refresh:
            raise GhStackError(
                "gh stack view --json may refresh saved stack state; "
                "local-state authority is required"
            )
        payload = json.loads(self._capture(["view", "--json"]))
        if not isinstance(payload, dict):
            raise GhStackError("gh stack view --json must return an object")
        return payload

    def init(self, *, base: str, branches: Sequence[str]) -> None:
        self._capture(["init", "--base", base, *branches])

    def rebase_no_trunk_upstack(self, branch: str) -> None:
        self._capture(["rebase", "--no-trunk", "--upstack", branch])
```

- [ ] Update the subprocess safety test so only `gh_stack.py` may contain the
  literal `gh stack` invocation and only `github.py` may invoke non-stack `gh`
  commands.

- [ ] Run the focused adapter and safety tests, then the full gates.

```bash
python3 -m unittest \
  skills/carve-changesets/scripts/tests/test_gh_stack.py \
  skills/carve-changesets/scripts/tests/test_cli_safety.py -v
just format
just lint
just test
```

- [ ] Update `CHANGELOG.md` and commit as `feat: add native gh stack adapter`
  with a file-backed message that names the local-only capability boundary.

## Task 2: Model and Reconcile Native Topology

**Files:**

- Create: `skills/carve-changesets/scripts/native_stack.py`

- Create: `skills/carve-changesets/scripts/tests/test_native_stack.py`

- Modify:
  `skills/carve-changesets/scripts/tests/fixtures/gh-stack/view-open.json`

- Modify: `skills/carve-changesets/scripts/rehydrate.py`

- Modify: `skills/carve-changesets/scripts/tests/test_rehydrate.py`

- Modify: `CHANGELOG.md`

- [ ] Populate the checked-in fixture with the exact reviewed JSON schema.

```json
{
  "trunk": "main",
  "currentBranch": "feature-2",
  "branches": [
    {
      "name": "feature-1",
      "head": "1111111111111111111111111111111111111111",
      "base": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "isCurrent": false,
      "isMerged": false,
      "isQueued": false,
      "needsRebase": false,
      "pr": {
        "number": 101,
        "url": "https://github.com/acme/widgets/pull/101",
        "state": "OPEN"
      }
    },
    {
      "name": "feature-2",
      "head": "2222222222222222222222222222222222222222",
      "base": "1111111111111111111111111111111111111111",
      "isCurrent": true,
      "isMerged": false,
      "isQueued": false,
      "needsRebase": false,
      "pr": {
        "number": 102,
        "url": "https://github.com/acme/widgets/pull/102",
        "state": "OPEN"
      }
    }
  ]
}
```

- [ ] Write failing tests for exact JSON parsing, contiguous base/head linkage,
  unique current branch, and remote/GitHub disagreement.

- [ ] Add truth-phase tests: a validated plan with no layers is `proposed`;
  native layers without PRs are `materialized`; a reconciled native GitHub stack
  with an open suffix is `published`; and an empty suffix with every chain PR
  verified merged is `merged`. Keep these phases distinct from terminal
  readiness states.

```python
class NativeStackSnapshotTest(unittest.TestCase):
    def test_parses_ordered_native_layers(self) -> None:
        snapshot = parse_native_stack(VIEW_OPEN, trunk_head=A_SHA)

        self.assertEqual(snapshot.trunk_branch, "main")
        self.assertEqual(snapshot.current_branch, "feature-2")
        self.assertEqual(
            tuple(layer.branch for layer in snapshot.layers),
            ("feature-1", "feature-2"),
        )

    def test_rejects_noncontiguous_native_bases(self) -> None:
        payload = copy.deepcopy(VIEW_OPEN)
        payload["branches"][1]["base"] = B_SHA

        with self.assertRaisesRegex(NativeStackError, "expected predecessor head"):
            parse_native_stack(payload, trunk_head=A_SHA)

    def test_reconcile_rejects_remote_head_disagreement(self) -> None:
        snapshot = parse_native_stack(VIEW_OPEN, trunk_head=A_SHA)

        with self.assertRaisesRegex(NativeStackError, "remote head mismatch"):
            reconcile_native_stack(
                snapshot,
                remote_heads={"feature-1": B_SHA, "feature-2": C_SHA},
                pull_requests={101: OPEN_PR_101, 102: OPEN_PR_102},
            )
```

- [ ] Run the focused tests and confirm failure at the missing parser.

```bash
python3 -m unittest skills/carve-changesets/scripts/tests/test_native_stack.py -v
```

- [ ] Implement strict typed parsing and reconciliation. The parser must reject
  unknown PR states, missing full SHAs, duplicate branches, multiple current
  branches, and noncontiguous bases.

```python
@dataclass(frozen=True)
class NativePullRequest:
    number: int
    url: str
    state: str


@dataclass(frozen=True)
class NativeLayer:
    branch: str
    head: str
    base: str
    merged: bool
    queued: bool
    needs_rebase: bool
    pull_request: NativePullRequest | None


@dataclass(frozen=True)
class NativeStackSnapshot:
    trunk_branch: str
    trunk_head: str
    current_branch: str
    layers: tuple[NativeLayer, ...]

    @property
    def open_suffix(self) -> tuple[NativeLayer, ...]:
        return tuple(layer for layer in self.layers if not layer.merged)


def reconcile_native_stack(
    snapshot: NativeStackSnapshot,
    *,
    remote_heads: Mapping[str, str],
    pull_requests: Mapping[int, PullRequestRecord],
) -> NativeStackSnapshot:
    for layer in snapshot.layers:
        if not layer.merged and remote_heads.get(layer.branch) != layer.head:
            raise NativeStackError(f"remote head mismatch for {layer.branch}")
        if layer.pull_request is None:
            continue
        live = pull_requests.get(layer.pull_request.number)
        if live is None:
            raise NativeStackError(
                f"missing GitHub PR #{layer.pull_request.number} for {layer.branch}"
            )
        if live.head_branch != layer.branch or live.head_sha != layer.head:
            raise NativeStackError(
                f"GitHub PR #{live.number} does not match native layer {layer.branch}"
            )
    return snapshot
```

- [ ] Replace index/suffix-derived ordering in `rehydrate.py` with native layer
  order. Keep legacy branch discovery only in an explicit `adopt_legacy_chain()`
  path; ordinary rehydration must require a native snapshot.

- [ ] Make status acquisition authority-aware. With
  `--allow-stack-state-refresh`, call `gh stack view --json`, verify the
  checkout did not move, and reconcile native state. Without that flag, do not
  call `gh stack`; render side-effect-free Git and GitHub evidence with native
  local topology marked unavailable.

- [ ] Run native topology and rehydration tests, then all required checks.

```bash
python3 -m unittest \
  skills/carve-changesets/scripts/tests/test_native_stack.py \
  skills/carve-changesets/scripts/tests/test_rehydrate.py -v
just format
just lint
just test
```

- [ ] Update `CHANGELOG.md` and commit as
  `feat: make native stack topology authoritative`.

## Task 3: Replace Positional Metadata with Trailer-Only Source Lineage

**Files:**

- Modify: `skills/carve-changesets/scripts/metadata.py`

- Modify: `skills/carve-changesets/scripts/tests/test_metadata.py`

- Modify: `skills/carve-changesets/scripts/chain.py`

- Modify: `skills/carve-changesets/scripts/tests/test_chain.py`

- Modify: `CHANGELOG.md`

- [ ] Add failing tests for remote-aware identity, trailer-only v3
  serialization, successor lineage, and read-only normalization of v1/v2 PR
  metadata.

```python
class MetadataV3Test(unittest.TestCase):
    def test_v3_omits_position_and_pr_metadata_block(self) -> None:
        metadata = ChangesetMetadata(
            slug="payments",
            source_lineage=(
                SourceIdentity(
                    remote="origin",
                    branch="feature",
                    sha=A_SHA,
                ),
            ),
        )

        message = stamp_commit_message("Extract payment model", metadata)

        self.assertIn("Changeset-Slug: payments", message)
        self.assertIn(f"Changeset-Source: origin feature @ {A_SHA}", message)
        self.assertNotIn("Changeset-Index", message)
        self.assertNotIn("carve-changesets:metadata", message)

    def test_legacy_pr_block_normalizes_without_rewrite(self) -> None:
        normalized = normalize_legacy_pr_metadata(LEGACY_V2_BODY, remote="origin")

        self.assertEqual(normalized.slug, "payments")
        self.assertEqual(normalized.active_source.remote, "origin")
        self.assertEqual(normalized.legacy_position, 2)
```

- [ ] Run metadata tests and confirm they fail against the positional v2 model.

```bash
python3 -m unittest skills/carve-changesets/scripts/tests/test_metadata.py -v
```

- [ ] Implement the v3 identity model and parser. Use JSON only inside the
  lineage trailer value; do not render a PR-body metadata block.

```python
TRAILER_SLUG = "Changeset-Slug"
TRAILER_SOURCE = "Changeset-Source"
TRAILER_LINEAGE = "Changeset-Lineage"
TRAILER_RECOVERY_FROM = "Changeset-Recovery-From"


@dataclass(frozen=True)
class SourceIdentity:
    remote: str
    branch: str
    sha: str

    @property
    def trailer(self) -> str:
        return f"{self.remote} {self.branch} @ {self.sha}"


@dataclass(frozen=True)
class ChangesetMetadata:
    slug: str
    source_lineage: tuple[SourceIdentity, ...]
    recovery_from_head: str | None = None

    @property
    def root_source(self) -> SourceIdentity:
        return self.source_lineage[0]

    @property
    def active_source(self) -> SourceIdentity:
        return self.source_lineage[-1]


@dataclass(frozen=True)
class LegacyMetadataEvidence:
    metadata: ChangesetMetadata
    legacy_position: int
    marker_version: int
```

- [ ] Update chain materialization to stamp `remote`, `branch`, and immutable
  source SHA on every changeset commit. Derive order exclusively from the plan
  during creation and from native topology after creation.

- [ ] Run metadata and chain tests, then all required checks.

```bash
python3 -m unittest \
  skills/carve-changesets/scripts/tests/test_metadata.py \
  skills/carve-changesets/scripts/tests/test_chain.py -v
just format
just lint
just test
```

- [ ] Update `CHANGELOG.md` and commit as
  `feat: adopt trailer only changeset lineage`.

## Task 4: Materialize and Adopt a Native Local Stack

**Files:**

- Modify: `skills/carve-changesets/scripts/chain.py`

- Modify: `skills/carve-changesets/scripts/cli.py`

- Create: `skills/carve-changesets/scripts/tests/test_native_materialize.py`

- Modify: `skills/carve-changesets/scripts/tests/test_scripts_integration.py`

- Modify: `CHANGELOG.md`

- [ ] Add a failing integration-style unit test proving semantic commits are
  created before one explicit native adoption, and that topology readback must
  match exactly.

```python
class NativeMaterializationTest(unittest.TestCase):
    @mock.patch("chain.create_chain", return_value=["feature-1", "feature-2"])
    def test_materialize_registers_exact_order_and_returns_snapshot(
        self,
        create_chain: mock.Mock,
    ) -> None:
        client = mock.Mock()
        client.view_json.return_value = VIEW_OPEN_WITHOUT_PRS

        snapshot = materialize_native_stack(
            PLAN,
            remote="origin",
            client=client,
            trunk_head=A_SHA,
        )

        create_chain.assert_called_once_with(PLAN)
        client.init.assert_called_once_with(
            base="main",
            branches=["feature-1", "feature-2"],
        )
        self.assertEqual(
            tuple(layer.branch for layer in snapshot.layers),
            ("feature-1", "feature-2"),
        )

    def test_materialize_rejects_native_order_disagreement(self) -> None:
        client = mock.Mock()
        client.view_json.return_value = VIEW_REVERSED

        with self.assertRaisesRegex(NativeStackError, "native order"):
            materialize_native_stack(
                PLAN,
                remote="origin",
                client=client,
                trunk_head=A_SHA,
            )
```

- [ ] Run the focused test and confirm the coordinator is missing.

```bash
python3 -m unittest skills/carve-changesets/scripts/tests/test_native_materialize.py -v
```

- [ ] Implement `materialize_native_stack()` in `chain.py`. Check out the top
  layer only for the `init`/`view` boundary, restore the caller's original
  branch, and include the active source identity plus every layer head in the
  result evidence.

```python
def materialize_native_stack(
    plan: dict,
    *,
    remote: str,
    client: GhStackClient | None = None,
    trunk_head: str | None = None,
) -> NativeStackSnapshot:
    native = client or GhStackClient()
    branches = create_chain(plan)
    resolved_trunk = trunk_head or git(
        "rev-parse", f"refs/remotes/{remote}/{plan['base_branch']}"
    ).stdout.strip()
    with checkout_restore():
        git("checkout", branches[-1])
        native.init(base=plan["base_branch"], branches=branches)
        snapshot = parse_native_stack(
            native.view_json(allow_state_refresh=True),
            trunk_head=resolved_trunk,
        )
    if tuple(layer.branch for layer in snapshot.layers) != tuple(branches):
        raise NativeStackError("native order does not match the materialized plan")
    return snapshot
```

- [ ] Change `create-chain` to require `--ack-local-stack-state`, call the
  native coordinator, and report materialized truth plus the exact
  validation/review command needed to reach `chain_ready`. It must not claim
  `chain_ready` until Task 6 supplies current validation, read-only review, and
  equivalence evidence. Add an error for invoking materialization without an
  installed compatible local profile; never create a non-native chain.

- [ ] Add a temporary-repository test that runs the CLI with a fake `gh`
  executable and asserts `.git/gh-stack` topology is represented by the fixture
  readback. Assert interruption before `init` leaves semantic commits but
  returns `blocked` with the exact recovery command.

- [ ] Run materialization and integration tests, then all required checks.

```bash
python3 -m unittest \
  skills/carve-changesets/scripts/tests/test_native_materialize.py \
  skills/carve-changesets/scripts/tests/test_scripts_integration.py -v
just format
just lint
just test
```

- [ ] Update `CHANGELOG.md` and commit as
  `feat: materialize changesets as a native stack`.

## Task 5: Add Operation-Scoped Manifests and Fail-Closed Remote Transitions

**Files:**

- Create: `skills/carve-changesets/scripts/transitions.py`

- Create: `skills/carve-changesets/scripts/tests/test_transitions.py`

- Modify: `skills/carve-changesets/scripts/cli.py`

- Modify: `skills/carve-changesets/scripts/tests/test_cli_safety.py`

- Modify: `CHANGELOG.md`

- [ ] Write failing tests that enumerate direct and automatic effects, require
  expected-old refs and PR states, and prove capability rejection happens before
  the injected executor is called.

```python
class TransitionManifestTest(unittest.TestCase):
    def test_publish_preview_lists_every_effect(self) -> None:
        manifest = preview_transition(
            StackOperation.PUBLISH,
            OPEN_SNAPSHOT,
            AuthorityGrant.publish(branches=("feature-1", "feature-2")),
        )

        self.assertEqual(
            tuple(effect.kind for effect in manifest.effects),
            (
                EffectKind.PUSH_REF,
                EffectKind.PUSH_REF,
                EffectKind.CREATE_PR,
                EffectKind.CREATE_PR,
                EffectKind.DISABLE_AUTO_MERGE,
                EffectKind.DISABLE_AUTO_MERGE,
                EffectKind.REGISTER_STACK,
            ),
        )
        self.assertEqual(manifest.expected_refs[0].old_sha, ZERO_SHA)
        self.assertEqual(manifest.expected_pull_requests[0].state, "absent")
        self.assertEqual(manifest.expected_native_stack.order, ("feature-1", "feature-2"))

    def test_reviewed_preview_blocks_publish_before_execution(self) -> None:
        executor = mock.Mock()
        result = execute_transition(
            PUBLISH_MANIFEST,
            profile=reviewed_preview_profile(REVIEWED_SHA),
            executor=executor,
        )

        self.assertEqual(result.state, TerminalState.BLOCKED)
        self.assertIn("explicit_pull_request_bodies", result.blocker)
        executor.assert_not_called()
```

- [ ] Run the focused test and confirm the transition model is absent.

```bash
python3 -m unittest skills/carve-changesets/scripts/tests/test_transitions.py -v
```

- [ ] Implement typed effects, expected-old inputs, authority grants,
  required-capability maps, and terminal results.

```python
class StackOperation(str, Enum):
    PUBLISH = "publish"
    REPAIR = "repair"
    MERGE = "merge"
    RECOVER = "recover"


REQUIRED_CAPABILITIES = {
    StackOperation.PUBLISH: frozenset(
        {
            StackCapability.FENCED_SUBMIT,
            StackCapability.EXPLICIT_PULL_REQUEST_BODIES,
        }
    ),
    StackOperation.REPAIR: frozenset(
        {
            StackCapability.LOCAL_REBASE_NO_TRUNK,
            StackCapability.FENCED_PUSH,
        }
    ),
    StackOperation.MERGE: frozenset(
        {
            StackCapability.FENCED_MERGE,
        }
    ),
    StackOperation.RECOVER: frozenset(
        {
            StackCapability.FENCED_PUSH,
            StackCapability.PHASED_TRUNK_REFRESH,
        }
    ),
}


def execute_transition(
    manifest: MutationManifest,
    *,
    profile: GhStackProfile,
    executor: Callable[[MutationManifest], None],
) -> TransitionResult:
    missing = REQUIRED_CAPABILITIES[manifest.operation] - profile.capabilities
    if missing:
        names = ", ".join(sorted(capability.value for capability in missing))
        return TransitionResult.blocked(
            phase=manifest.operation.value,
            identities=manifest.identities,
            evidence=manifest.evidence,
            blocker=f"gh stack profile {profile.version} lacks: {names}",
            next_action="install a repository-tested compatible gh-stack profile",
        )
    manifest.validate_complete()
    executor(manifest)
    return classify_readback(manifest)
```

- [ ] Define manifest records with exact repository and remote; every selected
  ref SHA or absence; every selected PR identity or absence, head, base, state,
  draft, queue, and auto-merge value; native stack identity or absence, trunk,
  membership, and order; enabled sync phases; exact titles and bodies; all
  direct and automatic effects; and the authority grant covering the complete
  effect set.

```python
@dataclass(frozen=True)
class ExpectedPullRequest:
    number: int | None
    branch: str
    head: str | None
    base: str | None
    state: str
    draft: bool | None
    queued: bool | None
    auto_merge: bool | None


@dataclass(frozen=True)
class ExpectedNativeStack:
    identity: str | None
    trunk: str
    order: tuple[str, ...]


@dataclass(frozen=True)
class MutationManifest:
    operation: StackOperation
    repository: str
    remote: str
    identities: tuple[str, ...]
    expected_refs: tuple[ExpectedRef, ...]
    expected_pull_requests: tuple[ExpectedPullRequest, ...]
    expected_native_stack: ExpectedNativeStack
    effects: tuple[MutationEffect, ...]
    evidence: tuple[str, ...]
    authority: AuthorityGrant
```

- [ ] Make `push-chain`, `pr-create`, `repair`, `merge-propagate`, and
  `recover-suffix` render their operation manifest by default. `--execute`
  requires the corresponding explicit authority acknowledgment, re-reads all
  inputs, then returns `blocked` under the reviewed preview without invoking
  `push`, `submit`, `sync`, or `merge`. A queue-backed `merge-propagate`
  additionally requires `DURABLE_QUEUE_FENCE`; a direct prefix merge does not.

- [ ] Add safety tests that inspect every mutation command and assert dry-run
  defaults, authority acknowledgment names, and executor non-invocation for an
  unsupported profile.

- [ ] Add pure readback-classification tests for complete success, no-op
  success, a rejected lease after earlier refs advanced, an unexpected remote
  ref creation, PR/base/draft/auto-merge drift, direct-prefix partial merge,
  queue admission without landing, and stack reordering. Each declared target
  must classify as `changed_as_expected`, `unchanged`, or
  `changed_unexpectedly`; any retry must require a newly generated manifest.

- [ ] Run transition and CLI safety tests, then all required checks.

```bash
python3 -m unittest \
  skills/carve-changesets/scripts/tests/test_transitions.py \
  skills/carve-changesets/scripts/tests/test_cli_safety.py -v
just format
just lint
just test
```

- [ ] Update `CHANGELOG.md` and commit as
  `feat: fence native stack transitions by capability`.

## Task 6: Prove Live Equivalence and Define Stack-Fix Handbacks

**Files:**

- Modify: `skills/carve-changesets/scripts/validate.py`

- Modify: `skills/carve-changesets/scripts/tests/test_validate.py`

- Modify: `skills/carve-changesets/scripts/rehydrate.py`

- Modify: `skills/carve-changesets/scripts/tests/test_rehydrate.py`

- Modify: `CHANGELOG.md`

- [ ] Add failing equivalence tests for an unmerged stack, a merged prefix,
  drifted trunk, rewritten suffix heads, and a valid successor source.

```python
class LiveEquivalenceTest(unittest.TestCase):
    def test_merged_prefix_plus_open_suffix_matches_active_source(self) -> None:
        result = validate_live_equivalence(
            snapshot=MERGED_PREFIX_SNAPSHOT,
            active_source=SOURCE_V1,
            compare_trees=fake_compare(equal=True),
        )

        self.assertTrue(result.valid)
        self.assertEqual(result.merged_prefix, (101,))
        self.assertEqual(result.open_suffix, (102, 103))

    def test_trunk_drift_requires_remote_successor_identity(self) -> None:
        result = validate_live_equivalence(
            snapshot=DRIFTED_TRUNK_SNAPSHOT,
            active_source=LOCAL_ONLY_SUCCESSOR,
            compare_trees=fake_compare(equal=True),
        )

        self.assertFalse(result.valid)
        self.assertEqual(result.code, "successor_source_not_remote")
```

- [ ] Run validation tests and confirm the current whole-chain ancestry
  validator cannot express the merged-prefix invariant.

```bash
python3 -m unittest skills/carve-changesets/scripts/tests/test_validate.py -v
```

- [ ] Implement equivalence reconstruction in a disposable ref: start at exact
  current remote trunk, apply each open native layer in order, compare its tree
  to the active immutable source, and delete only the disposable ref on exit.

```python
@dataclass(frozen=True)
class LiveEquivalence:
    valid: bool
    code: str
    merged_prefix: tuple[int, ...]
    open_suffix: tuple[int, ...]
    reconstructed_tree: str
    source_tree: str


def validate_live_equivalence(
    *,
    snapshot: NativeStackSnapshot,
    active_source: SourceIdentity,
) -> LiveEquivalence:
    require_remote_source(active_source)
    merged, opened = partition_at_first_open(snapshot.layers)
    reconstructed = reconstruct_open_suffix(
        trunk_head=snapshot.trunk_head,
        layers=opened,
    )
    return compare_equivalent_trees(
        reconstructed=reconstructed,
        source=active_source.sha,
        merged=merged,
        opened=opened,
    )
```

- [ ] Implement `assess_chain_ready()` so `chain_ready` requires exact-head
  validation for every layer, a current clean `review-code-change` result for
  every layer, native topology readback, and successful live equivalence. Return
  `blocked` naming the first stale or missing gate; never promote
  materialization alone.

- [ ] Add terminal-state tests for `prs_open` and `all_merged`. `prs_open`
  requires current `chain_ready` evidence plus exact remote heads, PR bases,
  semantic trailers, native GitHub membership, and non-merge gates. `all_merged`
  requires every chain PR merged, an empty suffix, completed native
  synchronization, current-trunk equivalence, current validation, and authorized
  cleanup completed or explicitly bounded.

- [ ] Add a `StackFixHandback` parser/renderer in `rehydrate.py`. Require exact
  PR number/head, invalidated suffix branches and PRs, prior evidence IDs,
  requested native phase, authority still needed, and resumable command.
  Document the handback contract in Task 8 so all normative prose changes land
  together.

```json
{
  "kind": "stack_fix_handback",
  "reviewed_pr": 102,
  "reviewed_head": "2222222222222222222222222222222222222222",
  "invalidated_suffix": {
    "branches": ["feature-2", "feature-3"],
    "pull_requests": [102, 103]
  },
  "invalidated_evidence": ["review:102:2222222", "validation:feature-3:3333333"],
  "requested_phase": "repair",
  "authority_required": "rewrite and push the named open suffix",
  "resume_command": "python3 skills/carve-changesets/scripts/cli.py repair --pr 102"
}
```

- [ ] Ensure `repair` consumes this handback only after fresh topology readback
  and invalidates all evidence tied to changed heads. Under the reviewed
  profile, it must return `blocked` before local cascading rebase because the
  complete repair cannot be published safely.

- [ ] Add interruption-state tests for a native rebase conflict, an existing
  stack lock, local/remote divergence, and an interrupted native modify.
  Preserve documented dependency recovery state, report the exact continuation
  or abort command, and never parse `.git/gh-stack` internals to manufacture
  recovery.

- [ ] Run validation, rehydration, and handoff contract tests, then all required
  checks.

```bash
python3 -m unittest \
  skills/carve-changesets/scripts/tests/test_validate.py \
  skills/carve-changesets/scripts/tests/test_rehydrate.py \
  skills/carve-changesets/scripts/tests/test_skill_contract.py -v
just format
just lint
just test
```

- [ ] Update `CHANGELOG.md` and commit as
  `feat: validate live native stack equivalence`.

## Task 7: Cut Over the CLI and Remove the Custom Stack Manager

**Files:**

- Modify: `skills/carve-changesets/scripts/cli.py`

- Modify: `skills/carve-changesets/scripts/github.py`

- Delete: `skills/carve-changesets/scripts/propagate.py`

- Delete: `skills/carve-changesets/scripts/recovery.py`

- Delete: `skills/carve-changesets/scripts/tests/test_propagate.py`

- Delete: `skills/carve-changesets/scripts/tests/test_recovery.py`

- Modify: `skills/carve-changesets/scripts/tests/test_github.py`

- Modify: `skills/carve-changesets/scripts/tests/test_scripts_integration.py`

- Create: `skills/carve-changesets/scripts/tests/test_legacy_adoption.py`

- Modify: `CHANGELOG.md`

- [ ] Add failing CLI tests for the final command map and deterministic
  retirement messages.

```python
class NativeCommandSurfaceTest(unittest.TestCase):
    def test_final_remote_commands_are_native_transitions(self) -> None:
        parser = build_parser()

        self.assertParses(parser, "push-chain")
        self.assertParses(parser, "pr-create")
        self.assertParses(parser, "repair")
        self.assertParses(parser, "merge-propagate")
        self.assertParses(parser, "recover-suffix")

    def test_custom_propagate_command_is_retired(self) -> None:
        result = invoke_cli("propagate")

        self.assertEqual(result.returncode, 2)
        self.assertIn("use the native repair workflow", result.stderr)
```

- [ ] Run CLI integration tests and confirm the custom commands still exist.

```bash
python3 -m unittest skills/carve-changesets/scripts/tests/test_scripts_integration.py -v
```

- [ ] Remove ordinary PR create/edit/merge functions from `github.py`. Retain
  authenticated repository lookup, PR reads, branch/head/base/state reads, and
  remote-source verification.

- [ ] Delete `propagate.py`, `recovery.py`, and their mechanism-specific tests.
  Move successor-lineage planning into the pure recovery manifest builder in
  `transitions.py`; it must not rewrite or push under the reviewed profile.

- [ ] Implement final command routing:

```text
create-chain       semantic materialization -> gh stack init -> materialized truth
status             gh stack view --json + GitHub/remote/trailer reconciliation
push-chain         push manifest -> capability gate -> blocked on reviewed profile
pr-create          submit manifest -> capability gate -> blocked on reviewed profile
repair             handback + manifest -> capability gate -> blocked on reviewed profile
merge-propagate    prefix/queue manifest -> capability gate -> blocked on reviewed profile
recover-suffix     successor manifest -> capability gate -> blocked on reviewed profile
```

- [ ] Add legacy-adoption tests. A legacy v1/v2 chain may be locally adopted
  with `gh stack init` only after commit/PR evidence agrees; native GitHub
  registration remains `blocked` because `gh stack link` is forbidden and the
  reviewed `submit` profile lacks required fences. Assert that adoption does not
  amend heads merely to normalize metadata.

- [ ] Search for forbidden custom-manager call sites and stale imports; the
  command must return no matches.

```bash
rg -n "pr_create|merge_pull_request|edit_pull_request|push_chain|propagate_from_live|merge_propagate_from_live|recover_suffix_from_live|gh stack link" \
  skills/carve-changesets/scripts \
  --glob '*.py'
```

- [ ] Run the complete carve script suite and all required checks.

```bash
just test-carve-changesets
just format
just lint
just test
```

- [ ] Update `CHANGELOG.md` and commit as
  `refactor: remove custom changeset stack management`.

## Task 8: Cut Over Normative Prose and Record Behavioral Evidence

**Files:**

- Modify: `skills/carve-changesets/SKILL.md`

- Modify: `skills/carve-changesets/references/SPEC.md`

- Modify: `skills/carve-changesets/references/cli.md`

- Modify: `skills/carve-changesets/references/plan-schema.md`

- Modify: `skills/carve-changesets/references/suite-handoffs.md`

- Modify: `skills/carve-changesets/evals/cases.json`

- Modify: `skills/carve-changesets/evals/expectations.json`

- Modify: `skills/carve-changesets/evals/integration_cases.json`

- Create: `skills/carve-changesets/evals/results/<recorded-after-summary>.json`

- Modify: `CHANGELOG.md`

- [ ] Update the deterministic corpus before normative prose so it has explicit
  cases for native-only topology, `chain_ready` on the reviewed profile,
  fail-closed publication, operation-scoped authority, live equivalence,
  stack-fix handback, legacy local adoption, and forbidden fallback.

- [ ] Run the deterministic corpus against the still-old prose and confirm the
  new expectations fail for the intended contract gap.

```bash
just eval-carve-changesets
```

Expected: at least one new case fails because the old skill still delegates
stack mechanics to custom publication/propagation commands.

- [ ] Rewrite the normative documents to match the implemented contract. Keep
  semantic seam selection and indivisibility rules prominent; describe native
  stack mechanics by responsibility and phase, not by duplicating upstream
  implementation details. In `plan-schema.md`, make `remote` default to
  `origin`, make source identity immutable, and prohibit persisted position or
  predecessor. In `suite-handoffs.md`, define the exact `StackFixHandback`
  payload from Task 6.

- [ ] Add contract assertions covering these exact obligations:

```python
REQUIRED_NATIVE_CONTRACT = (
    "gh stack is the sole stack engine",
    "chain_ready",
    "operation-scoped authority",
    "current trunk",
    "open suffix",
    "successor source",
    "stack_fix_handback",
)

FORBIDDEN_FALLBACK_LANGUAGE = (
    "use gh pr create",
    "run propagate.py",
    "run recovery.py",
    "fall back to the custom stack manager",
)
```

- [ ] Run contract, corpus, and full checks.

```bash
python3 -m unittest skills/carve-changesets/scripts/tests/test_skill_contract.py -v
just eval-carve-changesets
just format
just lint
just test
```

- [ ] Update `CHANGELOG.md` and commit the normative cutover as
  `docs: rebuild carve changesets on gh stack`.

- [ ] From the resulting committed clean tree, record the `after` evidence.

```bash
just eval-record carve-changesets --stage after
```

Expected: the summary names the normative-cutover commit SHA, uses the same tier
and suite as the baseline, reports every case observation, and includes the
scoped diff against the recorded `before` run.

- [ ] Inspect the result JSON for candidate SHA, cleanliness, suite, status,
  totals, and per-case observations.

```bash
for result in skills/carve-changesets/evals/results/*-after.json; do
  python3 -m json.tool "$result" >/dev/null
done
git diff --check
git status --short
```

- [ ] Add the result and changelog entry, run all required checks, and commit as
  `test: record native gh stack behavior evidence`.

## Task 9: Final Cross-Layer Verification

**Files:**

- Modify only if verification exposes a defect: the smallest file already owned
  by Tasks 1–8

- Modify when a fix commit is required: `CHANGELOG.md`

- [ ] Run the complete deterministic, unit, integration, lint, and formatting
  suite from a clean tree.

```bash
just eval-carve-changesets
just format
just lint
just test
git diff --check
git status --short
```

- [ ] Exercise the command boundary in a disposable local repository with a fake
  reviewed-profile adapter and capture these terminal outcomes:

```text
valid proposal                         -> plan_ready
semantic commits + init                -> materialized truth, no terminal claim
validated and reviewed local stack     -> chain_ready
push-chain --execute                   -> blocked before mutation
pr-create --execute                    -> blocked before mutation
repair handback --execute              -> blocked before mutation
merge-propagate --execute              -> blocked before mutation
recover-suffix --execute               -> blocked before mutation
```

- [ ] Verify every `blocked` result contains phase, exact stack/source
  identities, evidence read, missing capabilities, authority still required, and
  one resumable next action.

- [ ] Verify no code path invokes `gh stack push`, `gh stack submit`,
  `gh stack sync`, `gh stack merge`, `gh pr create`, `gh pr edit`, or
  `gh pr merge` under the reviewed profile.

```bash
rg -n "\[.*gh.*stack.*(push|submit|sync|merge)|gh pr (create|edit|merge)" \
  skills/carve-changesets/scripts \
  --glob '*.py'
```

Expected: only contract fixtures or explicit forbidden-command assertions match;
executable production call sites do not.

- [ ] If verification required a code or prose correction, add a focused
  regression test, update `CHANGELOG.md`, repeat the full suite, and commit the
  correction with a file-backed Conventional Commit message. Because a
  normative-prose correction changes the candidate, record and commit a fresh
  `after` eval result from the corrected clean commit.

- [ ] Confirm the branch history is reviewable and every changelog entry except
  the newest has its full SHA.

```bash
git log --oneline --decorate main..HEAD
git status --short
```

Expected: the worktree is clean, the baseline and final eval summaries point to
resolvable commits, and the implementation has no custom stack-management
fallback.
