"""Disposable-remote integration tests for the standalone `update_pr` workflow
(issue #100).

Every test drives `update_pr.run_update_pr` against a real temporary Git
repository *and* a real disposable local bare repository used as the
publication remote (`git init --bare`, addressed by its filesystem path —
never a configured named remote, never this repository's actual `origin`),
matching `carve-changesets/scripts/tests/helpers.py`'s established
"disposable local remote" convention and this module's own "no mocked Git
state" convention. No test in this file, and no code path `update_pr.py`
itself can reach, ever touches this repository's real `origin` remote.

Covers the ticket's required scenarios: a successful converge-then-publish
run; a stale expected-old remote state; local non-fast-forward history
relative to the recorded expected-old head; a misconfigured ("wrong")
publication target; a mismatched remote-iteration grant; and an unreachable
remote. Also covers the remote-target lock actually being exercised through
`run_update_pr` (not just `local_execution.py`'s own unit tests) and that a
well-formed grant does not itself block a run.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(
        name, SKILL_ROOT / "scripts" / filename
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


UP = _load("review_fix_loop_update_pr", "update_pr.py")
LC = UP.LC
LE = UP.LE
VALIDATE = UP.VALIDATE


# ---------------------------------------------------------------------------
# Repository + disposable remote fixtures
# ---------------------------------------------------------------------------


def init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    LE.git("init", "-q", "-b", "main", cwd=path)
    LE.git("config", "user.email", "test@example.com", cwd=path)
    LE.git("config", "user.name", "Test", cwd=path)
    (path / "README.md").write_text("initial\n")
    LE.git("add", "-A", cwd=path)
    LE.git("commit", "-q", "-m", "initial commit", cwd=path)


def init_bare_remote(root: Path, *, name: str = "remote.git") -> Path:
    bare = root / name
    LE.git("init", "-q", "--bare", str(bare))
    return bare


def start_candidate(
    repo: Path,
    bare: Path,
    *,
    branch: str = "fix/100-example",
    marker: str = "broken",
    validation_flag: str = "pass",
    push_head: bool = True,
) -> tuple[str, str]:
    """Create `branch` off `main` with one commit, and (by default) push it
    to `bare` at the same ref name — establishing the "existing pull request"
    state `update_pr` requires an expected old head for. Returns
    `(base_sha, head_sha)`."""
    base_sha = LE.current_head(repo)
    LE.git("checkout", "-q", "-b", branch, cwd=repo)
    (repo / "marker.txt").write_text(marker + "\n")
    (repo / "validation_flag.txt").write_text(validation_flag + "\n")
    LE.git("add", "-A", cwd=repo)
    LE.git("commit", "-q", "-m", "start candidate", cwd=repo)
    head_sha = LE.current_head(repo)
    if push_head:
        LE.git("push", str(bare), f"{branch}:refs/heads/{branch}", cwd=repo)
    return base_sha, head_sha


ALWAYS_PASS_VALIDATION = [
    {"name": "focused unit test", "command": "true", "scope": "focused"},
    {"name": "full repository gate", "command": "true", "scope": "full"},
]


def make_invocation(
    repo: Path,
    bare: Path,
    *,
    branch: str,
    base_sha: str,
    head_sha: str,
    invocation_id: str = "update-pr-test",
    max_fix_cycles: int = 3,
    validation: list[dict[str, str]] | None = None,
    grants: list[dict[str, str]] | None = None,
    head_repository: str = "shaug/agent-scripts",
    source_repository: str | None = None,
    remote_url: str | None = None,
) -> dict[str, Any]:
    common_dir = LE.git_common_dir(repo)
    diff = LE.git("diff", base_sha, head_sha, cwd=repo).stdout
    worktree = LE.worktree_status(repo)
    head_ref = f"refs/heads/{branch}"
    publication: dict[str, Any] = {
        "policy": "update_pr",
        "pull_request": {
            "head_repository": head_repository,
            "head_ref": head_ref,
            "expected_old_head_sha": head_sha,
            "base_ref": "main",
            "base_sha": base_sha,
        },
    }
    if grants is not None:
        publication["remote_iteration_grants"] = grants
    return {
        "schema_version": "1.0",
        "invocation_id": invocation_id,
        "repository": {
            "identity": "shaug/agent-scripts",
            "git_common_directory": str(common_dir),
        },
        "candidate": {
            "branch": branch,
            "head_sha": head_sha,
            "comparison_base": {"ref": "main", "sha": base_sha},
            "diff": {"format": "unified_diff", "complete": True, "content": diff},
            "worktree": worktree,
            "all_changes_committed": True,
            "pull_request": {"repository": "shaug/agent-scripts", "number": 123},
            "source_binding": {
                "repository": source_repository or head_repository,
                "remote_url": remote_url or str(bare),
                "ref": head_ref,
                "observed_object_id": head_sha,
            },
        },
        "change_contract": {
            "goal": "Fix the example.",
            "acceptance_criteria": ["marker.txt reads 'fixed'"],
            "non_goals": ["Unrelated refactors"],
            "preserved_behaviors": ["Existing README content"],
            "allowed_remediation_scope": "marker.txt only",
            "sources": {
                "repository_instructions": [],
                "named_documents": [],
                "nearby_patterns": [],
            },
        },
        "review_execution": {"mode": "fresh_subagent"},
        "fix_cycle_budget": {"max_fix_cycles": max_fix_cycles},
        "validation": validation or ALWAYS_PASS_VALIDATION,
        "publication": publication,
    }


CLEAN_TEMPLATE = {
    "schema_version": "1.4",
    "lens": "aggregate",
    "verdict": "clean",
    "findings": [],
    "blocking_reasons": [],
    "validation_limitations": [],
    "next_action": "No changes are required.",
}

FINDING_ID = "correctness-001"


def _finding() -> dict[str, Any]:
    return {
        "id": FINDING_ID,
        "lens": "correctness",
        "severity": "blocking",
        "confidence": "high",
        "rule": "example rule",
        "evidence": [
            {"location": "marker.txt:1", "detail": "marker.txt is not 'fixed'"}
        ],
        "concern": "marker.txt does not read 'fixed'",
        "impact": "the candidate is incomplete",
        "proposed_change": "write 'fixed' into marker.txt",
        "expected_effect": "marker.txt reads 'fixed'",
    }


def make_marker_reviewer(repo: Path):
    """A fake reviewer whose verdict is a real function of `marker.txt`'s
    content at the exact head it is asked to review, mirroring
    `test_local_commit.py`'s own fixture of the same name."""

    def reviewer(
        *, packet, briefing, head_sha, comparison_base_sha, independence, sequence
    ):
        del packet, briefing, independence, sequence
        content = LE.git("show", f"{head_sha}:marker.txt", cwd=repo).stdout.strip()
        candidate = {"head_sha": head_sha, "comparison_base_sha": comparison_base_sha}
        if content == "fixed":
            result = {
                **CLEAN_TEMPLATE,
                "candidate": candidate,
                "lens_executions": [
                    {
                        "lens": lens,
                        "head_sha": head_sha,
                        "comparison_base_sha": comparison_base_sha,
                        "verdict": "clean",
                        "freshly_executed": True,
                    }
                    for lens in (
                        "solution_simplicity",
                        "correctness",
                        "code_simplicity",
                    )
                ],
            }
        else:
            result = {
                **CLEAN_TEMPLATE,
                "candidate": candidate,
                "verdict": "changes_required",
                "findings": [_finding()],
                "lens_executions": [
                    {
                        "lens": "solution_simplicity",
                        "head_sha": head_sha,
                        "comparison_base_sha": comparison_base_sha,
                        "verdict": "clean",
                        "freshly_executed": True,
                    }
                ],
                "next_action": f"Fix {FINDING_ID}.",
            }
        return LC.ReviewPass(result=result)

    return reviewer


def make_clean_reviewer():
    def reviewer(
        *, packet, briefing, head_sha, comparison_base_sha, independence, sequence
    ):
        del packet, briefing, independence, sequence
        candidate = {"head_sha": head_sha, "comparison_base_sha": comparison_base_sha}
        result = {
            **CLEAN_TEMPLATE,
            "candidate": candidate,
            "lens_executions": [
                {
                    "lens": lens,
                    "head_sha": head_sha,
                    "comparison_base_sha": comparison_base_sha,
                    "verdict": "clean",
                    "freshly_executed": True,
                }
                for lens in ("solution_simplicity", "correctness", "code_simplicity")
            ],
        }
        return LC.ReviewPass(result=result)

    return reviewer


def fixing_apply_fix(*, finding, attempt_path, change_contract, attempt_number):
    del finding, change_contract, attempt_number
    (attempt_path / "marker.txt").write_text("fixed\n")
    return f"fix: resolve {FINDING_ID}"


def accepting_decide(*, finding, change_contract, attempt_number):
    del change_contract, attempt_number
    return LC.FixDecision(
        disposition="accepted", rationale=f"{finding['id']} is tractable"
    )


class UpdatePrRepoTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "repo"
        init_repo(self.repo)
        self.bare = init_bare_remote(Path(self.tmp.name))


# ---------------------------------------------------------------------------
# Success
# ---------------------------------------------------------------------------


class SuccessTests(UpdatePrRepoTestCase):
    def test_converges_and_publishes_the_exact_expected_old_fast_forward(self):
        base_sha, head_sha = start_candidate(self.repo, self.bare, marker="broken")
        invocation = make_invocation(
            self.repo,
            self.bare,
            branch="fix/100-example",
            base_sha=base_sha,
            head_sha=head_sha,
        )
        result = UP.run_update_pr(
            invocation,
            repo=self.repo,
            reviewer=make_marker_reviewer(self.repo),
            decide=accepting_decide,
            apply_fix=fixing_apply_fix,
        )
        self.assertEqual(result["terminal_state"], "converged")
        self.assertNotIn("reason", result)
        self.assertEqual(result["publication"]["status"], "published")
        self.assertEqual(result["publication"]["remote_head_before"], head_sha)
        self.assertEqual(
            result["publication"]["remote_head_after"], result["head"]["final"]
        )
        self.assertEqual(result["unpushed_commits"], [])
        self.assertEqual(VALIDATE.validate_terminal_result(result), [])

        # The disposable remote itself actually advanced to the converged head.
        remote_head = LE.git(
            "ls-remote", str(self.bare), "refs/heads/fix/100-example", cwd=self.repo
        ).stdout.split()[0]
        self.assertEqual(remote_head, result["head"]["final"])

    def test_immediate_convergence_with_no_fix_cycle_still_publishes(self):
        base_sha, head_sha = start_candidate(self.repo, self.bare, marker="fixed")
        invocation = make_invocation(
            self.repo,
            self.bare,
            branch="fix/100-example",
            base_sha=base_sha,
            head_sha=head_sha,
        )
        result = UP.run_update_pr(
            invocation,
            repo=self.repo,
            reviewer=make_clean_reviewer(),
            decide=accepting_decide,
            apply_fix=fixing_apply_fix,
        )
        self.assertEqual(result["terminal_state"], "converged")
        self.assertEqual(result["publication"]["status"], "published")
        self.assertEqual(result["created_commits"], [])
        self.assertEqual(result["publication"]["remote_head_before"], head_sha)
        self.assertEqual(result["publication"]["remote_head_after"], head_sha)
        self.assertEqual(VALIDATE.validate_terminal_result(result), [])

    def test_a_well_formed_grant_does_not_block_publication(self):
        base_sha, head_sha = start_candidate(self.repo, self.bare, marker="fixed")
        invocation = make_invocation(
            self.repo,
            self.bare,
            branch="fix/100-example",
            base_sha=base_sha,
            head_sha=head_sha,
            grants=[
                {
                    "mechanism_id": "ci-check",
                    "kind": "external_ci",
                    "repository": "shaug/agent-scripts",
                    "ref": "refs/heads/fix/100-example",
                    "origin_only_evidence": "CI only evaluates the pushed remote ref",
                }
            ],
        )
        result = UP.run_update_pr(
            invocation,
            repo=self.repo,
            reviewer=make_clean_reviewer(),
            decide=accepting_decide,
            apply_fix=fixing_apply_fix,
        )
        self.assertEqual(result["terminal_state"], "converged")
        self.assertEqual(result["publication"]["status"], "published")


# ---------------------------------------------------------------------------
# Stale expected-old state (someone else's commit already sits on the remote)
# ---------------------------------------------------------------------------


class StaleExpectedOldTests(UpdatePrRepoTestCase):
    def test_a_competing_remote_update_cannot_be_overwritten(self):
        base_sha, head_sha = start_candidate(self.repo, self.bare, marker="fixed")
        invocation = make_invocation(
            self.repo,
            self.bare,
            branch="fix/100-example",
            base_sha=base_sha,
            head_sha=head_sha,
        )

        # Simulate another clone winning the race: a second local clone
        # commits on top of the same expected-old head and pushes first.
        other_clone = Path(self.tmp.name) / "other-clone"
        LE.git("clone", "-q", str(self.repo), str(other_clone))
        LE.git("checkout", "-q", "fix/100-example", cwd=other_clone)
        (other_clone / "marker.txt").write_text("someone-else-fixed-it\n")
        LE.git("add", "-A", cwd=other_clone)
        LE.git(
            "-c",
            "user.email=other@example.com",
            "-c",
            "user.name=Other",
            "commit",
            "-q",
            "-m",
            "a competing fix",
            cwd=other_clone,
        )
        LE.git(
            "push",
            str(self.bare),
            "fix/100-example:refs/heads/fix/100-example",
            cwd=other_clone,
        )
        competing_head = LE.current_head(other_clone)
        self.assertNotEqual(competing_head, head_sha)

        result = UP.run_update_pr(
            invocation,
            repo=self.repo,
            reviewer=make_clean_reviewer(),
            decide=accepting_decide,
            apply_fix=fixing_apply_fix,
        )
        self.assertEqual(result["terminal_state"], "blocked")
        self.assertEqual(result["reason"], "remote_advanced")
        self.assertEqual(result["publication"]["status"], "failed")
        self.assertEqual(result["publication"]["remote_head_before"], competing_head)
        # Our own converged local commit is preserved, not lost or overwritten.
        self.assertEqual(result["head"]["final"], head_sha)
        self.assertEqual(VALIDATE.validate_terminal_result(result), [])

        # The remote still holds the competing candidate's head, untouched.
        remote_head = LE.git(
            "ls-remote", str(self.bare), "refs/heads/fix/100-example", cwd=self.repo
        ).stdout.split()[0]
        self.assertEqual(remote_head, competing_head)


# ---------------------------------------------------------------------------
# Non-fast-forward history (this invocation's own recorded expected-old head
# is not actually an ancestor of its local candidate)
# ---------------------------------------------------------------------------


class NonFastForwardHistoryTests(UpdatePrRepoTestCase):
    def test_local_candidate_not_descending_from_expected_old_fails_closed(self):
        base_sha, head_sha = start_candidate(self.repo, self.bare, marker="fixed")

        # A sibling branch's commit, unrelated to fix/100-example's real
        # history, used as a deliberately wrong `expected_old_head_sha` — the
        # local candidate cannot possibly be a descendant of it.
        LE.git("checkout", "-q", "-b", "unrelated", base_sha, cwd=self.repo)
        (self.repo / "unrelated.txt").write_text("unrelated\n")
        LE.git("add", "-A", cwd=self.repo)
        LE.git("commit", "-q", "-m", "unrelated commit", cwd=self.repo)
        unrelated_sha = LE.current_head(self.repo)
        LE.git("checkout", "-q", "fix/100-example", cwd=self.repo)

        invocation = make_invocation(
            self.repo,
            self.bare,
            branch="fix/100-example",
            base_sha=base_sha,
            head_sha=head_sha,
        )
        invocation["publication"]["pull_request"]["expected_old_head_sha"] = (
            unrelated_sha
        )
        # The remote must still report the (now-wrong) expected value so the
        # pre-push staleness check passes and the ancestry check is reached.
        LE.git(
            "push",
            "--force",
            str(self.bare),
            f"{unrelated_sha}:refs/heads/fix/100-example",
            cwd=self.repo,
        )

        result = UP.run_update_pr(
            invocation,
            repo=self.repo,
            reviewer=make_clean_reviewer(),
            decide=accepting_decide,
            apply_fix=fixing_apply_fix,
        )
        self.assertEqual(result["terminal_state"], "blocked")
        self.assertEqual(result["reason"], "candidate_integrity_failure")
        # No push was ever attempted (the ancestry check fires first), so
        # this is `withheld`, not `failed` — matching every other blocked
        # reason outside `remote_advanced`/`publication_failed`.
        self.assertEqual(result["publication"]["status"], "withheld")
        self.assertEqual(VALIDATE.validate_terminal_result(result), [])

        # Nothing was pushed: the remote still holds the unrelated commit.
        remote_head = LE.git(
            "ls-remote", str(self.bare), "refs/heads/fix/100-example", cwd=self.repo
        ).stdout.split()[0]
        self.assertEqual(remote_head, unrelated_sha)


# ---------------------------------------------------------------------------
# Wrong target (the invocation's own contract disagrees with itself)
# ---------------------------------------------------------------------------


class WrongTargetTests(UpdatePrRepoTestCase):
    def test_source_binding_repository_mismatch_fails_closed_before_any_lock(self):
        base_sha, head_sha = start_candidate(self.repo, self.bare, marker="fixed")
        invocation = make_invocation(
            self.repo,
            self.bare,
            branch="fix/100-example",
            base_sha=base_sha,
            head_sha=head_sha,
            head_repository="shaug/agent-scripts",
            source_repository="someone-else/a-fork",
        )
        result = UP.run_update_pr(
            invocation,
            repo=self.repo,
            reviewer=make_clean_reviewer(),
            decide=accepting_decide,
            apply_fix=fixing_apply_fix,
        )
        self.assertEqual(result["terminal_state"], "blocked")
        self.assertEqual(result["reason"], "missing_authority")
        self.assertEqual(result["publication"]["status"], "withheld")
        self.assertEqual(result["budget"]["consumed_cycles"], 0)
        self.assertEqual(VALIDATE.validate_terminal_result(result), [])

        # No lock was ever taken and no remote was ever touched: the target
        # was rejected before "Resolve" could finish.
        remote_head = LE.git(
            "ls-remote", str(self.bare), "refs/heads/fix/100-example", cwd=self.repo
        ).stdout.split()[0]
        self.assertEqual(remote_head, head_sha)

    def test_fork_target_is_resolved_explicitly_without_assuming_origin(self):
        """A consistent fork target (source_binding and pull_request agree,
        and the remote_url is genuinely a different repository's remote,
        never this repo's own origin) must publish exactly as a
        same-repository branch would."""
        fork_bare = init_bare_remote(Path(self.tmp.name), name="fork.git")
        base_sha, head_sha = start_candidate(
            self.repo, fork_bare, marker="fixed", branch="fix/100-fork-example"
        )
        invocation = make_invocation(
            self.repo,
            fork_bare,
            branch="fix/100-fork-example",
            base_sha=base_sha,
            head_sha=head_sha,
            head_repository="contributor/agent-scripts-fork",
            source_repository="contributor/agent-scripts-fork",
        )
        result = UP.run_update_pr(
            invocation,
            repo=self.repo,
            reviewer=make_clean_reviewer(),
            decide=accepting_decide,
            apply_fix=fixing_apply_fix,
        )
        self.assertEqual(result["terminal_state"], "converged")
        self.assertEqual(result["publication"]["status"], "published")
        remote_head = LE.git(
            "ls-remote",
            str(fork_bare),
            "refs/heads/fix/100-fork-example",
            cwd=self.repo,
        ).stdout.split()[0]
        self.assertEqual(remote_head, result["head"]["final"])
        # The (unrelated, untouched) main-repository bare remote never saw
        # this ref at all — proof this never fell back to "origin."
        main_repo_refs = LE.git(
            "ls-remote",
            str(self.bare),
            "refs/heads/fix/100-fork-example",
            cwd=self.repo,
        ).stdout.strip()
        self.assertEqual(main_repo_refs, "")


# ---------------------------------------------------------------------------
# Missing / mismatched grants
# ---------------------------------------------------------------------------


class MismatchedGrantTests(UpdatePrRepoTestCase):
    def test_a_grant_for_a_different_ref_fails_closed_before_any_lock(self):
        base_sha, head_sha = start_candidate(self.repo, self.bare, marker="fixed")
        invocation = make_invocation(
            self.repo,
            self.bare,
            branch="fix/100-example",
            base_sha=base_sha,
            head_sha=head_sha,
            grants=[
                {
                    "mechanism_id": "ci-check",
                    "kind": "external_ci",
                    "repository": "shaug/agent-scripts",
                    "ref": "refs/heads/some-other-branch",
                    "origin_only_evidence": "CI only evaluates the pushed remote ref",
                }
            ],
        )
        result = UP.run_update_pr(
            invocation,
            repo=self.repo,
            reviewer=make_clean_reviewer(),
            decide=accepting_decide,
            apply_fix=fixing_apply_fix,
        )
        self.assertEqual(result["terminal_state"], "blocked")
        self.assertEqual(result["reason"], "missing_authority")
        self.assertIn("some-other-branch", result["operator_action"])
        self.assertEqual(VALIDATE.validate_terminal_result(result), [])

        remote_head = LE.git(
            "ls-remote", str(self.bare), "refs/heads/fix/100-example", cwd=self.repo
        ).stdout.split()[0]
        self.assertEqual(remote_head, head_sha)


# ---------------------------------------------------------------------------
# Remote failure
# ---------------------------------------------------------------------------


class RemoteFailureTests(UpdatePrRepoTestCase):
    def test_an_unreachable_remote_fails_closed_at_publish_without_losing_the_commit(
        self,
    ):
        base_sha, head_sha = start_candidate(self.repo, self.bare, marker="broken")
        invocation = make_invocation(
            self.repo,
            self.bare,
            branch="fix/100-example",
            base_sha=base_sha,
            head_sha=head_sha,
            remote_url=str(Path(self.tmp.name) / "does-not-exist.git"),
        )
        result = UP.run_update_pr(
            invocation,
            repo=self.repo,
            reviewer=make_marker_reviewer(self.repo),
            decide=accepting_decide,
            apply_fix=fixing_apply_fix,
        )
        self.assertEqual(result["terminal_state"], "blocked")
        self.assertEqual(result["reason"], "publication_failed")
        self.assertEqual(result["publication"]["status"], "failed")
        # The fix cycle still ran and converged locally; only publication
        # itself failed, and the converged commit is preserved and reported.
        self.assertEqual(len(result["created_commits"]), 1)
        self.assertEqual(result["unpushed_commits"], result["created_commits"])
        self.assertEqual(VALIDATE.validate_terminal_result(result), [])
        self.assertEqual(LE.current_head(self.repo), result["head"]["final"])


# ---------------------------------------------------------------------------
# Locking actually wired through `run_update_pr`
# ---------------------------------------------------------------------------


class LockingTests(UpdatePrRepoTestCase):
    def test_remote_target_lock_already_held_blocks_without_mutation(self):
        base_sha, head_sha = start_candidate(self.repo, self.bare, marker="fixed")
        invocation = make_invocation(
            self.repo,
            self.bare,
            branch="fix/100-example",
            base_sha=base_sha,
            head_sha=head_sha,
        )
        common_dir = LE.git_common_dir(self.repo)
        with LE.acquire_candidate_locks(
            common_dir,
            "refs/heads/fix/100-example",
            remote_target=("shaug/agent-scripts", "refs/heads/fix/100-example"),
        ):
            result = UP.run_update_pr(
                invocation,
                repo=self.repo,
                reviewer=make_clean_reviewer(),
                decide=accepting_decide,
                apply_fix=fixing_apply_fix,
            )
        self.assertEqual(result["terminal_state"], "blocked")
        self.assertEqual(result["reason"], "candidate_busy")
        self.assertEqual(result["publication"]["status"], "withheld")
        self.assertEqual(VALIDATE.validate_terminal_result(result), [])


# ---------------------------------------------------------------------------
# Input validation (caller/programming errors, not structured stops)
# ---------------------------------------------------------------------------


class InputValidationTests(UpdatePrRepoTestCase):
    def test_rejects_local_commit_policy(self):
        base_sha, head_sha = start_candidate(self.repo, self.bare, marker="fixed")
        invocation = make_invocation(
            self.repo,
            self.bare,
            branch="fix/100-example",
            base_sha=base_sha,
            head_sha=head_sha,
        )
        invocation["publication"] = {"policy": "local_commit"}
        del invocation["candidate"]["source_binding"]
        invocation["candidate"]["source_unavailable_reason"] = "no source"
        with self.assertRaises(UP.UpdatePrError):
            UP.run_update_pr(
                invocation,
                repo=self.repo,
                reviewer=make_clean_reviewer(),
                decide=accepting_decide,
                apply_fix=fixing_apply_fix,
            )

    def test_rejects_invalid_invocation(self):
        base_sha, head_sha = start_candidate(self.repo, self.bare, marker="fixed")
        invocation = make_invocation(
            self.repo,
            self.bare,
            branch="fix/100-example",
            base_sha=base_sha,
            head_sha=head_sha,
        )
        del invocation["fix_cycle_budget"]
        with self.assertRaises(UP.UpdatePrError):
            UP.run_update_pr(
                invocation,
                repo=self.repo,
                reviewer=make_clean_reviewer(),
                decide=accepting_decide,
                apply_fix=fixing_apply_fix,
            )


if __name__ == "__main__":
    unittest.main()
