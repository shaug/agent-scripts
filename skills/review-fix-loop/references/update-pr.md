# Standalone `update_pr` workflow

This document implements
[`design/review-fix-loop.md`](../../../design/review-fix-loop.md)'s "Publication
policy" > `update_pr`, "Origin-visible exception", workflow step 8 "Publish
after convergence", and the `update_pr` parts of "Local ownership and
checkpointing" > "Cooperative ownership" — for the executing agent that follows
[`SKILL.md`](../SKILL.md). It does not redefine any contract, locking,
checkpoint, reviewer-orchestration, or review/fix/converge-loop behavior already
owned by [`references/CONTRACT.md`](CONTRACT.md),
[`references/reviewer-orchestration.md`](reviewer-orchestration.md), and
[`references/local-commit.md`](local-commit.md); it composes them into the one
entry point issue #100 delivers:
[`scripts/update_pr.py`](../scripts/update_pr.py)'s `run_update_pr(...)`.

## What this module composes, and what it does not reimplement

`local_commit.py` (#99) already implements every workflow step from 1 "Resolve"
through 7 "Invalidate and repeat" as a private `_run_engine` function,
parameterized by a `_Policy` describing what, if anything, a publication policy
adds on top of the shared review/fix/converge loop. `run_local_commit` is a thin
wrapper around `_run_engine` bound to the trivial `local_commit` policy (every
hook `None` — its behavior is exactly what it always was before this policy
abstraction existed). `update_pr.py` is the *only other* caller of
`_run_engine`; it never reimplements the loop's control flow, fix-cycle budget
enforcement, or checkpoint/terminal-result assembly — it supplies a populated
`_Policy` built from this invocation's own resolved publication target:

- `remote_target` — the `(repository, head_ref)` pair `local_execution.py`'s
  `acquire_candidate_locks` already accepts as its `update_pr`-only
  remote-target lock argument (issue #97). This module does not reimplement
  locking; it only supplies the identity that lock is keyed by.
- `checkpoint_pull_request` — the `{head_repository, head_ref, base_ref}` shape
  `checkpoint.schema.json`'s `publication.pull_request` already defines (issue
  #96). This module does not redefine that shape; it only populates it from the
  resolved target.
- `check_remote` — a hook `_run_engine` calls at two points every ordinary loop
  iteration already reaches (immediately before establishing evidence for a
  fresh review, and immediately before starting a fix attempt). Returns `None`
  when the remote has not observably advanced, or
  `{"reason": "remote_advanced", "remote_head": <sha> | None}` when it has.
  `_run_engine` converts a non-`None` result into a `blocked` terminal result
  using the exact same `_default_publication` status rule described below — this
  module never computes `publication.status` itself for this path.
- `publish` — a hook `_run_engine` calls exactly once, only immediately after an
  aggregate review comes back `clean`, in place of `local_commit`'s
  unconditional "publish nothing" return. Returns a `_PublishOutcome`
  (`status: "published" | "failed"`, plus `remote_head_before`/
  `remote_head_after`/`blocked_reason`/`operator_action`); `_run_engine`
  converts that into the converged-and-published terminal result or a `blocked`
  one, again reusing the same status rule.

What issue #100 itself owns, and what did not exist before this module:

- `resolve_publication_target` — resolving and cross-validating the fork/remote
  publication target ("Resolve fork and remote publication targets explicitly").
- `validate_remote_iteration_grants` — validating every
  `remote_iteration_grants` entry against that resolved target ("Require and
  validate the origin-visible grants described by the design").
- The two `check_remote`/`publish` closures themselves: the actual
  `git ls-remote`/`git push --force-with-lease`/readback sequence design's
  "Publication policy" > `update_pr` describes.
- `local_commit.py`'s small, additive generalization that makes the shared
  engine policy-aware: `_Policy`, `_PublishOutcome`, `_default_publication`, the
  `_State.policy` field, and the `publication_override`/`source_override`
  parameters `_finalize`/`_terminal_result` now accept. Every one of these is
  additive — `run_local_commit`'s own behavior and its 21 existing tests are
  unchanged; see `local_commit.py`'s own module docstring for the exact
  cross-module contract these private names now form between the two files.

## Host boundary

Identical to `local_commit.py`'s: `reviewer`, `decide`, and `apply_fix` are
still the caller-supplied ports for the three genuinely host/runtime actions
(running one review pass, deciding a finding's disposition, and writing a fix's
content). This module adds no new host port. Resolving the publication target,
checking the remote, and publishing are real Git operations this dependency-free
module performs itself via `local_execution.py`'s bundled `git` helper —
`git ls-remote`, `git merge-base --is-ancestor`, and
`git push ... --force-with-lease=<head_ref>:<expected_old_head_sha>` — exactly
as `local_commit.py` already performs every other Git operation itself. No test
in this skill's suite, and no code path this module can reach, ever touches this
repository's real `origin` remote; every test drives a disposable local bare
repository addressed by its filesystem path, matching
`carve-changesets/scripts/tests/helpers.py`'s established convention.

## Resolving the publication target

`validate.validate_invocation` already requires an `update_pr` invocation to
carry both `candidate.source_binding` (the actual pushable location: a
repository identity, remote URL, fully qualified ref, and observed object ID)
and `publication.pull_request` (the PR's own head-repository, head-ref,
expected-old head SHA, base ref, and base SHA). Schema validation cannot check
that those two halves of the invocation's *own* contract agree with each other;
`resolve_publication_target` does:

- `candidate.source_binding.repository` must equal
  `publication.pull_request.head_repository`.
- `candidate.source_binding.ref` must equal `publication.pull_request.head_ref`.
- `publication.pull_request.head_ref` must be a fully qualified ref
  (`refs/...`).

A mismatch — the invocation disagreeing with itself about what it is allowed to
push — raises `TargetResolutionError`, and `run_update_pr` converts that into a
structured `blocked/missing_authority` terminal result before acquiring any
lock, running any review, or touching the repository at all. This is
deliberately symmetric for a same-repository branch and a fork: the resolved
target's `remote_url` always comes from `source_binding.remote_url`, never from
a configured `origin` remote or any assumption about which repository owns the
branch.

`validate_remote_iteration_grants` applies the identical check to every
`publication.remote_iteration_grants` entry (this ticket's "Require and validate
the origin-visible grants described by the design"): a grant whose
`repository`/`ref` do not match the resolved target, or whose `ref` is not fully
qualified, fails closed the same way. This module does not implement invoking
any origin-visible-exception mechanism itself — no host port in this ticket's
scope demonstrably requires an origin-visible head mid-loop — it only validates
grant structure so a stale or mismatched one is never silently accepted.

## The publish step

Design's "Publication policy" > `update_pr` describes six steps; `publish`
implements all of them:

1. Fetch and reread the exact remote head (`git ls-remote`).
2. Require it to equal `expected_old_head_sha`. A `None` (ref does not exist) or
   mismatched value returns `blocked` without ever attempting a push —
   `publication_failed` for a missing ref (a target/configuration problem),
   `remote_advanced` for a mismatched one (another clone won the race).
3. Prove the local candidate is a non-rewriting descendant of
   `expected_old_head_sha` via `git merge-base --is-ancestor`. A failure here
   means this invocation's own recorded expected-old head is not actually an
   ancestor of its local candidate (a configuration problem, not a race) and
   returns `blocked/candidate_integrity_failure` without attempting a push.
4. Perform one
   `git push <remote_url> <branch>:<head_ref> --force-with-lease=<head_ref>:<expected_old_head_sha>`
   — the strongest exact-old primitive the Git transport supports, combined with
   the independent ancestry check above. This is a compare-and-swap guard, never
   authority to rewrite history.
5. If the push itself is rejected (a race that occurred between steps 1 and 4),
   reread the remote head again to distinguish a genuine race
   (`remote_advanced`, with the actual competing head reported) from any other
   push failure (`publication_failed`).
6. On a successful push, read the ref back and require it to equal the converged
   local head; a mismatch is `publication_failed`.

Every failure path preserves the converged local commit untouched — `publish`
never merges, rebases, force-updates, or otherwise supersedes a competing
candidate — and reports it via the terminal result's `unpushed_commits`,
`head.final`, and `operator_action`, matching this ticket's "Preserve and report
the converged commit if the publication race is lost or publication is
unavailable" requirement.

## Publication status, reused rather than reinvented

`references/CONTRACT.md`'s terminal-result rule is: under `update_pr`, a
`converged` result's `publication.status` must be `published`; a
`changes_remaining` result's must be `withheld`; a `blocked` result's must be
`failed` only for `remote_advanced`/`publication_failed` and `withheld` for
every other reason (including `candidate_integrity_failure`, `candidate_busy`,
`missing_authority`, and every ordinary review/validation stop). This module
never recomputes that rule itself: `local_commit._default_publication` is the
one place it lives, and every blocked path in this module — the two mid-loop
`check_remote` stops and every non-published outcome of `publish` — routes its
blocked reason through that same function (directly, or via `_run_engine`'s own
use of it) rather than trusting a hook's own `"failed"` label as the
schema-facing status. This is why an early version of this implementation could
set `publication.status: "failed"` for `candidate_integrity_failure` and fail
its own schema validation — a defect worth naming here so a future change to
either side of this rule updates both together.

## Terminal states this module actually returns

- `converged` — the final head's review is `clean`, required validation passed,
  `write_isolation` was `enforced` throughout, and the exact expected-old
  fast-forward publish landed and read back correctly. `publication.status` is
  `published` and `unpushed_commits` is empty.
- `changes_remaining` — identical reasons to `local_commit`
  (`cycle_budget_exhausted`, `current_candidate_validation_failure`,
  `repeated_failed_attempt`, `expanding_findings`, `oscillation`).
  `publication.status` is `withheld` — remediation stopped before convergence,
  so this module never even attempts to resolve the publication target's live
  state.
- `blocked` — every `local_commit` blocked reason remains reachable
  (`candidate_busy`, `candidate_integrity_failure`, `checkpoint_mismatch`,
  `missing_capability`, `reviewer_integrity_failure`, `validation_unavailable`,
  `operator_input_required`, `scope_decision_required`), plus three this module
  adds:
  - `missing_authority` — the publication target or a remote-iteration grant
    failed to resolve, before any lock or mutation.
  - `remote_advanced` — the remote head observably moved away from
    `expected_old_head_sha`, either at a mid-loop check or at publish time.
  - `publication_failed` — the remote was unreachable, the push failed for a
    reason other than a losing race, or the post-push readback did not match.

## Tests

[`scripts/tests/test_update_pr.py`](../scripts/tests/test_update_pr.py) drives
`run_update_pr` against a real temporary Git repository and a real disposable
local bare repository used as the publication remote — never this repository's
actual `origin`. Fixtures shared with `test_local_commit.py` — the module
loader, a bare local repository, the always-passing validation commands, the
marker-file-driven fake reviewer, and the accepting decider/fixer — live in this
sibling directory's own
[`scripts/tests/helpers.py`](../scripts/tests/helpers.py) rather than being
duplicated across both files, matching
`carve-changesets/scripts/tests/helpers.py`'s established precedent. Covers: a
successful converge-then-publish run with and without a fix cycle; a well-formed
`remote_iteration_grants` entry that does not itself block publication; a fork
target resolved explicitly without assuming origin ownership (and proof the main
repository's own bare remote never saw the fork's ref at all); a competing
remote update that cannot be overwritten (a second clone wins the race, and the
converged local commit is preserved while the remote is left holding the
competitor's head); local non-fast-forward history relative to the recorded
expected-old head; a source-binding/pull-request repository mismatch (a
misconfigured target) failing closed before any lock; a remote-iteration grant
referencing the wrong ref failing closed before any lock; an unreachable remote
failing closed at the publish step alone, without losing the already-converged
local commit; the `update_pr`-only remote-target lock actually being exercised
through `run_update_pr` (not only `local_execution.py`'s own unit tests); and
rejection of an invalid invocation or a `local_commit`-policy invocation at the
API boundary.
