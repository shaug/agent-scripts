#!/usr/bin/env python3
"""Standalone `update_pr` publication tail for `review-fix-loop` (issue #100).

Composes the exact same review/fix/converge engine `local_commit.py` (issue
#99) already implements — this module never reimplements Resolve/Establish
evidence/Review/Decide/Fix/Validate and commit/Invalidate and repeat; it
supplies `local_commit._run_engine` with a populated `local_commit._Policy`
built from this invocation's resolved publication target, so every
intermediate fix commit stays local, exactly as under `local_commit`, until
the aggregate review is clean. Only the final "Publish" workflow step differs:
after convergence, this module performs the design's exact expected-old,
fast-forward-only Git update (`design/review-fix-loop.md`, "Publication
policy" > `update_pr`) instead of `local_commit`'s unconditional "publish
nothing."

## What this module adds on top of the shared engine

- `resolve_publication_target` — resolves and cross-validates the fork/remote
  publication target from `candidate.source_binding` (the actual pushable
  remote URL and ref, which may be a fork, never assumed to be "origin") and
  `publication.pull_request` (the PR's own head-repository/head-ref/expected-
  old identity), per design's "Resolve fork and remote publication targets
  explicitly." A mismatch between the two — this invocation's own contract
  disagreeing with itself about what it is allowed to push — fails closed
  with `blocked/missing_authority` before any lock, review, or mutation.
- `validate_remote_iteration_grants` — validates every
  `publication.remote_iteration_grants` entry (this ticket's "Require and
  validate the origin-visible grants described by the design") resolves to
  the same repository and fully qualified ref as the resolved publication
  target. This module does not implement invoking any origin-visible-
  exception mechanism itself (no host port in this ticket's scope needs
  mid-loop remote visibility); it only validates grant structure so a stale
  or mismatched grant fails closed rather than silently being accepted.
- A `check_remote` policy hook: at the two loop boundaries
  `local_commit._run_engine` already calls it from (before establishing
  evidence for a fresh review, and before starting a fix attempt), reread the
  live remote head via `git ls-remote` and stop with
  `blocked/remote_advanced` if it no longer matches the invocation's recorded
  `expected_old_head_sha`. A transient remote-query failure here does not
  itself stop the invocation — ordinary iteration stays entirely local and
  only the final publish step's own failure is authoritative — so a
  momentarily unreachable remote never blocks otherwise-convergent local
  work.
- A `publish` policy hook, invoked exactly once, only immediately after the
  aggregate review is clean: fetch and reread the exact remote head; require
  it to equal `expected_old_head_sha`; prove the local candidate is a
  non-rewriting descendant of it; perform one
  `--force-with-lease=<head_ref>:<expected_old_head_sha>` push; and read the
  ref back to confirm it now equals the converged local head. Any failure at
  any of those steps returns a `blocked` outcome that preserves the converged
  local commit exactly as `local_commit` always would — this module never
  merges, rebases, force-updates, or otherwise supersedes a competing
  candidate.

## Host boundary

Identical to `local_commit.py`'s: `reviewer`, `decide`, and `apply_fix` are
still the caller-supplied ports for the three genuinely host/runtime actions.
This module adds no new host port — resolving the publication target,
checking the remote, and publishing are all real Git operations this
dependency-free module performs itself via `local_execution.py`'s bundled
`git` helper, exactly as `local_commit.py` already does for every other Git
operation. No test in this skill's suite, and no code path in this module,
ever touches this repository's real `origin` remote — every test drives a
disposable local (`file://`-equivalent path) bare repository, matching
`carve-changesets/scripts/tests/helpers.py`'s established convention.
"""

from __future__ import annotations

import dataclasses
import sys
from importlib import util as importlib_util
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent


def _load_bundled_module(name: str, path: Path):
    spec = importlib_util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib_util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# `local_commit.py` already loads its own bundled `validate.py` and
# `local_execution.py` as `LC.VALIDATE`/`LC.LE`; reuse those exact instances
# rather than loading a second, separate copy of either module.
LC = _load_bundled_module(
    "review_fix_loop_local_commit_for_update_pr", HERE / "local_commit.py"
)
VALIDATE = LC.VALIDATE
LE = LC.LE

# Re-exported so a caller can build ports without importing local_commit.py
# directly.
ReviewPass = LC.ReviewPass
FixDecision = LC.FixDecision
ValidationOutcome = LC.ValidationOutcome
default_run_validation = LC.default_run_validation


class UpdatePrError(LC.LocalCommitError):
    """A precondition this module requires of its caller was not met.

    Raised only for a caller/programming error (an invalid invocation, or an
    invocation whose `publication.policy` is not `update_pr`) — never for an
    ordinary runtime stop condition, which is always a structured terminal
    result instead, matching `local_commit.LocalCommitError`'s own
    convention. `isinstance`-compatible with `LocalCommitError` since both
    entry points share the same internal engine and its internal-error
    raises.
    """


# ---------------------------------------------------------------------------
# Publication target resolution ("Resolve fork and remote publication targets
# explicitly")
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class PublicationTarget:
    """The resolved, cross-validated `update_pr` publication target.

    `remote_url` and `head_ref` are the actual pushable location — always
    taken from `candidate.source_binding`, never assumed to be this
    repository's own `origin` remote, so a fork's own remote URL is used
    exactly as a same-repository branch's would be. `repository` is the
    identity string shared by `source_binding.repository` and
    `publication.pull_request.head_repository` once cross-validated.
    """

    repository: str
    remote_url: str
    head_ref: str
    expected_old_head_sha: str
    base_ref: str
    base_sha: str


class TargetResolutionError(RuntimeError):
    """The invocation's own publication fields disagree with each other, or a
    remote-iteration grant does not resolve to the same target.

    Always converted to a structured `blocked/missing_authority` terminal
    result by this module's callers — never raised across the
    `run_update_pr` boundary — per the design's "Publication fails closed
    when grants or target identity are missing or stale" requirement.
    """

    def __init__(self, message: str):
        super().__init__(message)


def resolve_publication_target(invocation: Mapping[str, Any]) -> PublicationTarget:
    """Resolve and cross-validate this invocation's publication target.

    `validate.validate_invocation` already requires `update_pr` to carry both
    `candidate.source_binding` and `publication.pull_request`; this function
    checks the one thing schema validation cannot: that the two halves of the
    invocation's own contract agree about which repository and ref are being
    published to. A same-repository branch and a fork both resolve
    identically here — this function never special-cases "origin."
    """
    source_binding = invocation["candidate"]["source_binding"]
    pull_request = invocation["publication"]["pull_request"]

    if source_binding["repository"] != pull_request["head_repository"]:
        raise TargetResolutionError(
            "candidate.source_binding.repository "
            f"{source_binding['repository']!r} does not match "
            "publication.pull_request.head_repository "
            f"{pull_request['head_repository']!r}; refusing to resolve an "
            "ambiguous publication target"
        )
    if source_binding["ref"] != pull_request["head_ref"]:
        raise TargetResolutionError(
            f"candidate.source_binding.ref {source_binding['ref']!r} does not "
            "match publication.pull_request.head_ref "
            f"{pull_request['head_ref']!r}; refusing to resolve an ambiguous "
            "publication target"
        )
    if not pull_request["head_ref"].startswith("refs/"):
        raise TargetResolutionError(
            "publication.pull_request.head_ref "
            f"{pull_request['head_ref']!r} is not a fully qualified ref"
        )

    return PublicationTarget(
        repository=source_binding["repository"],
        remote_url=source_binding["remote_url"],
        head_ref=pull_request["head_ref"],
        expected_old_head_sha=pull_request["expected_old_head_sha"],
        base_ref=pull_request["base_ref"],
        base_sha=pull_request["base_sha"],
    )


def validate_remote_iteration_grants(
    invocation: Mapping[str, Any], target: PublicationTarget
) -> list[str]:
    """Validate every `remote_iteration_grants` entry against the resolved
    target ("Require and validate the origin-visible grants described by the
    design").

    This module does not implement invoking any origin-visible-exception
    mechanism (design's "Origin-visible exception"): no host port in this
    ticket's scope demonstrably requires an origin-visible head mid-loop.
    Every grant is still validated so a stale or mismatched one fails closed
    rather than being silently accepted — "Unknown mechanisms,
    repository/ref mismatches, missing evidence ... fail closed without a
    remote write."
    """
    errors: list[str] = []
    for grant in invocation["publication"].get("remote_iteration_grants", []):
        if grant["repository"] != target.repository:
            errors.append(
                f"remote_iteration_grants[{grant['mechanism_id']!r}]: "
                f"repository {grant['repository']!r} does not match the "
                f"resolved publication target {target.repository!r}"
            )
        if grant["ref"] != target.head_ref:
            errors.append(
                f"remote_iteration_grants[{grant['mechanism_id']!r}]: ref "
                f"{grant['ref']!r} does not match the resolved publication "
                f"target ref {target.head_ref!r}"
            )
        elif not grant["ref"].startswith("refs/"):
            errors.append(
                f"remote_iteration_grants[{grant['mechanism_id']!r}]: ref "
                f"{grant['ref']!r} is not a fully qualified ref"
            )
    return errors


# ---------------------------------------------------------------------------
# Remote primitives
# ---------------------------------------------------------------------------


class _RemoteQueryError(RuntimeError):
    """`git ls-remote` itself failed (network, auth, or a nonexistent remote).

    Caught by every caller in this module; never propagates past this
    module's own policy hooks. A remote-query failure during ordinary
    iteration is tolerated (`_check_remote` treats it as "not observably
    advanced"); the same failure during the publish step is definitive and
    becomes `blocked/publication_failed`.
    """


def _ls_remote(remote_url: str, ref: str, *, cwd: Path) -> str | None:
    """Return the exact object ID `ref` resolves to on `remote_url`, or `None`
    if the remote has no such ref. Never mutates any local ref or the
    canonical worktree; safe to call at any point in the loop."""
    result = LE.git("ls-remote", remote_url, ref, cwd=cwd, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise _RemoteQueryError(
            f"git ls-remote {remote_url} {ref} failed: "
            f"{detail or f'exit code {result.returncode}'}"
        )
    line = result.stdout.strip()
    if not line:
        return None
    return line.split()[0]


# ---------------------------------------------------------------------------
# Policy hooks
# ---------------------------------------------------------------------------


def _make_check_remote(target: PublicationTarget, repo: Path):
    def check_remote(state: Any) -> dict[str, Any] | None:
        del state  # only the target's static identity matters for this check
        try:
            live = _ls_remote(target.remote_url, target.head_ref, cwd=repo)
        except _RemoteQueryError:
            # Tolerated: ordinary iteration never depends on remote
            # reachability. Only the publish step's own failure handling is
            # authoritative for a genuinely unreachable remote.
            return None
        if live is not None and live != target.expected_old_head_sha:
            return {"reason": "remote_advanced", "remote_head": live}
        return None

    return check_remote


def _make_publish(target: PublicationTarget, repo: Path):
    def publish(state: Any) -> LC._PublishOutcome:
        try:
            remote_before = _ls_remote(target.remote_url, target.head_ref, cwd=repo)
        except _RemoteQueryError as exc:
            return LC._PublishOutcome(
                status="failed",
                blocked_reason="publication_failed",
                operator_action=(
                    "could not query the remote head before publishing: "
                    f"{exc}; the converged commit {state.current_head} "
                    "remains local and unpushed"
                ),
            )

        if remote_before is None:
            return LC._PublishOutcome(
                status="failed",
                blocked_reason="publication_failed",
                operator_action=(
                    f"the remote ref {target.head_ref} does not exist on "
                    f"{target.repository}; cannot verify the expected old head "
                    f"before publishing. The converged commit "
                    f"{state.current_head} remains local and unpushed."
                ),
            )
        if remote_before != target.expected_old_head_sha:
            return LC._PublishOutcome(
                status="failed",
                blocked_reason="remote_advanced",
                remote_head_before=remote_before,
                remote_head_after=remote_before,
                operator_action=(
                    f"the remote head for {target.head_ref} is "
                    f"{remote_before!r}, not the expected old head "
                    f"{target.expected_old_head_sha!r}; another clone won the "
                    f"publication race. Reconcile the two candidates "
                    f"manually; the converged commit {state.current_head} "
                    "remains local and unpushed."
                ),
            )

        ancestry = LE.git(
            "merge-base",
            "--is-ancestor",
            target.expected_old_head_sha,
            state.current_head,
            cwd=repo,
            check=False,
        )
        if ancestry.returncode != 0:
            return LC._PublishOutcome(
                status="failed",
                blocked_reason="candidate_integrity_failure",
                remote_head_before=remote_before,
                remote_head_after=remote_before,
                operator_action=(
                    f"local head {state.current_head} is not a descendant of "
                    f"the expected old head {target.expected_old_head_sha!r}; "
                    "refusing to publish over what would be a rewritten "
                    "history"
                ),
            )

        refspec = f"{state.branch}:{target.head_ref}"
        lease = f"--force-with-lease={target.head_ref}:{target.expected_old_head_sha}"
        push_result = LE.git(
            "push", target.remote_url, refspec, lease, cwd=repo, check=False
        )
        if push_result.returncode != 0:
            try:
                remote_after = _ls_remote(target.remote_url, target.head_ref, cwd=repo)
            except _RemoteQueryError:
                remote_after = None
            if (
                remote_after is not None
                and remote_after != target.expected_old_head_sha
            ):
                return LC._PublishOutcome(
                    status="failed",
                    blocked_reason="remote_advanced",
                    remote_head_before=remote_before,
                    remote_head_after=remote_after,
                    operator_action=(
                        "the push was rejected: another clone advanced "
                        f"{target.head_ref} to {remote_after!r} before this "
                        "invocation published. Reconcile the two candidates "
                        f"manually; the converged commit {state.current_head} "
                        "remains local and unpushed."
                    ),
                )
            detail = (push_result.stderr or push_result.stdout or "").strip()
            return LC._PublishOutcome(
                status="failed",
                blocked_reason="publication_failed",
                remote_head_before=remote_before,
                remote_head_after=remote_after,
                operator_action=(
                    f"the publication push failed: {detail or 'unknown error'}; "
                    f"the converged commit {state.current_head} remains local "
                    "and unpushed"
                ),
            )

        try:
            remote_after = _ls_remote(target.remote_url, target.head_ref, cwd=repo)
        except _RemoteQueryError as exc:
            return LC._PublishOutcome(
                status="failed",
                blocked_reason="publication_failed",
                remote_head_before=remote_before,
                operator_action=(
                    "the push appeared to succeed but the post-push readback "
                    f"failed: {exc}"
                ),
            )
        if remote_after != state.current_head:
            return LC._PublishOutcome(
                status="failed",
                blocked_reason="publication_failed",
                remote_head_before=remote_before,
                remote_head_after=remote_after,
                operator_action=(
                    f"post-push readback of {target.head_ref} returned "
                    f"{remote_after!r}, not the converged head "
                    f"{state.current_head!r}"
                ),
            )

        return LC._PublishOutcome(
            status="published",
            remote_head_before=remote_before,
            remote_head_after=remote_after,
            non_converged_exposure=False,
            operator_action=(
                f"published: {target.head_ref} advanced from {remote_before} "
                f"to {remote_after} on {target.repository}"
            ),
        )

    return publish


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run_update_pr(
    invocation: Mapping[str, Any],
    *,
    repo: Path,
    reviewer: LC.ReviewerPort,
    decide: LC.DeciderPort,
    apply_fix: LC.FixerPort,
    run_validation: LC.ValidationRunnerPort = LC.default_run_validation,
    classify_validation_failure: LC.ValidationClassifierPort = LC._default_classify_validation_failure,
    host_supports_fresh_subagent: bool = True,
    attempts_root: Path | None = None,
    resume_checkpoint: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run (or resume) one standalone `update_pr` review-fix-loop invocation.

    Returns a schema-valid terminal-result document (`converged`,
    `changes_remaining`, or `blocked`). Every intermediate fix commit stays
    local until the aggregate review is clean; the exact one expected-old
    fast-forward push described by `design/review-fix-loop.md`'s "Publication
    policy" > `update_pr` happens at most once, immediately after that clean
    review, never before.

    Raises `UpdatePrError` only for a caller/programming error (an invalid
    invocation, or `publication.policy != "update_pr"`) — the same convention
    `local_commit.run_local_commit` already uses. A resolvable-but-invalid
    publication target (a repository/ref mismatch between
    `candidate.source_binding` and `publication.pull_request`, or a
    mismatched `remote_iteration_grants` entry) is not a programming error;
    it returns a structured `blocked/missing_authority` terminal result
    instead, per the design's fail-closed publication contract.
    """
    try:
        LC._validate_and_require_policy(invocation, "update_pr")
    except LC.LocalCommitError as exc:
        raise UpdatePrError(str(exc)) from exc

    try:
        target = resolve_publication_target(invocation)
    except TargetResolutionError as exc:
        return LC._minimal_blocked_result(
            invocation,
            repo=repo,
            reason="missing_authority",
            operator_action=str(exc),
            policy_name="update_pr",
        )

    grant_errors = validate_remote_iteration_grants(invocation, target)
    if grant_errors:
        return LC._minimal_blocked_result(
            invocation,
            repo=repo,
            reason="missing_authority",
            operator_action="; ".join(grant_errors),
            policy_name="update_pr",
        )

    policy = LC._Policy(
        name="update_pr",
        remote_target=(target.repository, target.head_ref),
        checkpoint_pull_request={
            "head_repository": target.repository,
            "head_ref": target.head_ref,
            "base_ref": target.base_ref,
        },
        check_remote=_make_check_remote(target, repo),
        publish=_make_publish(target, repo),
    )

    return LC._run_engine(
        invocation,
        repo=repo,
        reviewer=reviewer,
        decide=decide,
        apply_fix=apply_fix,
        run_validation=run_validation,
        classify_validation_failure=classify_validation_failure,
        host_supports_fresh_subagent=host_supports_fresh_subagent,
        attempts_root=attempts_root,
        resume_checkpoint=resume_checkpoint,
        policy=policy,
    )
