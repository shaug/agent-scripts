"""Deterministic tests for the review-fix-loop local execution substrate
(issue #97): common-directory locking, isolated attempt worktrees,
checkpoint persistence and resume reconciliation, verified fast-forward-only
canonical promotion, and recovery of an interrupted attempt.

Every test operates against a real temporary Git repository via subprocess
`git` calls — there is no mocked or simulated Git state — so a passing test
proves the module's behavior against actual Git semantics (worktrees,
`merge --ff-only`, `flock`, process-exit lock release).
"""

from __future__ import annotations

import fcntl
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]

SPEC = importlib.util.spec_from_file_location(
    "review_fix_loop_local_execution", SKILL_ROOT / "scripts" / "local_execution.py"
)
assert SPEC and SPEC.loader
LE = importlib.util.module_from_spec(SPEC)
# Register before exec_module: the module's dataclasses use `from __future__
# import annotations`, so Python 3.11's dataclass machinery resolves their
# string type hints via `sys.modules[cls.__module__]` and needs this entry.
sys.modules[SPEC.name] = LE
SPEC.loader.exec_module(LE)


def init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    LE.git("init", "-q", "-b", "main", cwd=path)
    LE.git("config", "user.email", "test@example.com", cwd=path)
    LE.git("config", "user.name", "Test", cwd=path)
    (path / "README.md").write_text("initial\n")
    LE.git("add", "-A", cwd=path)
    LE.git("commit", "-q", "-m", "initial commit", cwd=path)


def write_and_commit(repo: Path, name: str, content: str, message: str) -> str:
    (repo / name).write_text(content)
    LE.git("add", "-A", cwd=repo)
    LE.git("commit", "-q", "-m", message, cwd=repo)
    return LE.current_head(repo)


class GitPrimitiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "repo"
        init_repo(self.repo)

    def test_git_common_dir_is_absolute_and_exists(self):
        common = LE.git_common_dir(self.repo)
        self.assertTrue(common.is_absolute())
        self.assertTrue(common.is_dir())
        self.assertEqual(common, (self.repo / ".git").resolve())

    def test_worktree_status_clean_repo(self):
        status = LE.worktree_status(self.repo)
        self.assertEqual(status["staged"], [])
        self.assertEqual(status["unstaged"], [])
        self.assertEqual(status["untracked"], [])
        self.assertIn("README.md", status["tracked"])
        self.assertTrue(LE.is_clean(status))

    def test_worktree_status_detects_untracked_and_ignored(self):
        (self.repo / ".gitignore").write_text("ignored.txt\n")
        LE.git("add", "-A", cwd=self.repo)
        LE.git("commit", "-q", "-m", "add gitignore", cwd=self.repo)
        (self.repo / "ignored.txt").write_text("ignored\n")
        (self.repo / "untracked.txt").write_text("untracked\n")
        status = LE.worktree_status(self.repo)
        self.assertIn("untracked.txt", status["untracked"])
        self.assertIn("ignored.txt", status["ignored"])
        self.assertFalse(LE.is_clean(status))

    def test_worktree_status_ignored_alone_is_clean(self):
        (self.repo / ".gitignore").write_text("ignored.txt\n")
        LE.git("add", "-A", cwd=self.repo)
        LE.git("commit", "-q", "-m", "add gitignore", cwd=self.repo)
        (self.repo / "ignored.txt").write_text("ignored\n")
        status = LE.worktree_status(self.repo)
        self.assertTrue(LE.is_clean(status))


class LockingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "repo"
        init_repo(self.repo)
        self.common = LE.git_common_dir(self.repo)

    def test_conflicting_local_ref_lock_is_busy(self):
        with LE.acquire_candidate_locks(self.common, "refs/heads/fix/97"):
            with self.assertRaises(LE.CandidateBusyError):
                with LE.acquire_candidate_locks(self.common, "refs/heads/fix/97"):
                    pass

    def test_different_local_refs_do_not_contend(self):
        with LE.acquire_candidate_locks(self.common, "refs/heads/fix/97-a"):
            with LE.acquire_candidate_locks(self.common, "refs/heads/fix/97-b"):
                pass  # no contention: distinct targets, no exception

    def test_lock_released_after_context_exit(self):
        with LE.acquire_candidate_locks(self.common, "refs/heads/fix/97"):
            pass
        with LE.acquire_candidate_locks(self.common, "refs/heads/fix/97"):
            pass  # re-acquiring after a clean exit must succeed

    def test_remote_target_lock_contention(self):
        target = ("shaug/agent-scripts", "refs/heads/pr-branch")
        with LE.acquire_candidate_locks(
            self.common, "refs/heads/fix/a", remote_target=target
        ):
            with self.assertRaises(LE.CandidateBusyError):
                with LE.acquire_candidate_locks(
                    self.common, "refs/heads/fix/b", remote_target=target
                ):
                    pass

    def test_cross_policy_contention_on_same_local_ref(self):
        """Two invocations (one update_pr, one local_commit) must not both
        own the same local ref, regardless of remote target."""
        with LE.acquire_candidate_locks(self.common, "refs/heads/fix/97"):
            with self.assertRaises(LE.CandidateBusyError):
                with LE.acquire_candidate_locks(
                    self.common,
                    "refs/heads/fix/97",
                    remote_target=("shaug/agent-scripts", "refs/heads/pr-branch"),
                ):
                    pass

    def test_remote_lock_busy_releases_already_acquired_local_lock(self):
        target = ("shaug/agent-scripts", "refs/heads/pr-branch")
        with LE.acquire_candidate_locks(
            self.common, "refs/heads/fix/a", remote_target=target
        ):
            try:
                with LE.acquire_candidate_locks(
                    self.common, "refs/heads/fix/b", remote_target=target
                ):
                    pass
            except LE.CandidateBusyError:
                pass
        # fix/b's local lock must not still be held after the failed acquisition.
        with LE.acquire_candidate_locks(self.common, "refs/heads/fix/b"):
            pass

    def test_two_local_branches_targeting_same_pr_ref_contend(self):
        target = ("shaug/agent-scripts", "refs/pull/42/head")
        with LE.acquire_candidate_locks(
            self.common, "refs/heads/branch-one", remote_target=target
        ):
            with self.assertRaises(LE.CandidateBusyError):
                with LE.acquire_candidate_locks(
                    self.common, "refs/heads/branch-two", remote_target=target
                ):
                    pass

    def test_lock_is_released_when_the_holding_descriptor_closes(self):
        """A crashed holder never runs our `release()` cleanup; only the
        kernel unlocks an `flock` when every file descriptor referencing it
        closes (on `close()` or process exit alike). This opens and locks the
        file directly — bypassing `acquire_candidate_locks` entirely — then
        closes it without an explicit `LOCK_UN`, so the assertion exercises
        exactly the kernel-driven release the design relies on
        ("the operating system releases them when the process exits") without
        spawning and killing a real subprocess, which proved to be a source of
        OS-scheduling timing flakiness in this environment.
        """
        lock_ref = "refs/heads/fix/process-exit"
        path = LE.local_ref_lock_path(self.common, lock_ref)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o644)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            with self.assertRaises(LE.CandidateBusyError):
                with LE.acquire_candidate_locks(self.common, lock_ref):
                    pass
        finally:
            os.close(fd)  # no LOCK_UN: mirrors an OS-driven release on exit
        with LE.acquire_candidate_locks(self.common, lock_ref):
            pass  # the kernel released the lock when the descriptor closed


def make_checkpoint(**overrides) -> dict:
    document = {
        "schema_version": "1.0",
        "invocation_id": "inv-1",
        "repository": {
            "identity": "shaug/agent-scripts",
            "git_common_directory": "/work/agent-scripts/.git",
        },
        "branch": "fix/97-example",
        "worktree": {
            "tracked": ["example.py"],
            "staged": [],
            "unstaged": [],
            "untracked": [],
            "ignored": [],
        },
        "initial_head": "3ea8f9134120a12e741c3b3f87f67a743ad52ad1",
        "current_head": "3ea8f9134120a12e741c3b3f87f67a743ad52ad1",
        "comparison_base": {
            "ref": "main",
            "sha": "6d4e80a7e96351b471797a093ebc111917c516bd",
        },
        "publication": {"policy": "local_commit"},
        "original_cycle_budget": 3,
        "cycle_attempts": [],
        "head_history": ["3ea8f9134120a12e741c3b3f87f67a743ad52ad1"],
        "base_revision_history": [
            {"ref": "main", "sha": "6d4e80a7e96351b471797a093ebc111917c516bd"}
        ],
        "review_records": [],
        "validation_outcomes": [],
        "preserved_failed_attempts": [],
        "source": {
            "status": "unavailable",
            "unavailable_reason": "standalone invocation has no recorded pushable source",
        },
        "current_phase": "establish_evidence",
        "expected_next_action": "run the first complete review",
    }
    document.update(overrides)
    return document


def make_invocation(checkpoint: dict, **overrides) -> dict:
    document = {
        "schema_version": "1.0",
        "invocation_id": checkpoint["invocation_id"],
        "repository": checkpoint["repository"],
        "candidate": {
            "branch": checkpoint["branch"],
            "head_sha": checkpoint["initial_head"],
            "comparison_base": checkpoint["base_revision_history"][0],
            "diff": {
                "format": "unified_diff",
                "complete": True,
                "content": "diff --git a b\n",
            },
            "worktree": checkpoint["worktree"],
            "all_changes_committed": True,
            "source_unavailable_reason": "standalone invocation has no recorded pushable source",
        },
        "change_contract": {
            "goal": "fix example",
            "acceptance_criteria": ["example works"],
            "non_goals": [],
            "preserved_behaviors": [],
            "allowed_remediation_scope": "example.py only",
            "sources": {
                "repository_instructions": [],
                "named_documents": [],
                "nearby_patterns": [],
            },
        },
        "review_execution": {"mode": "fresh_subagent"},
        "fix_cycle_budget": {"max_fix_cycles": checkpoint["original_cycle_budget"]},
        "validation": [
            {"name": "focused", "command": "python3 -m unittest", "scope": "focused"},
            {"name": "full", "command": "just test", "scope": "full"},
        ],
        "publication": {"policy": checkpoint["publication"]["policy"]},
    }
    document.update(overrides)
    return document


class CheckpointStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.common = Path(self.tmp.name) / ".git"
        self.common.mkdir(parents=True)

    def test_write_then_read_round_trip(self):
        checkpoint = make_checkpoint()
        path = LE.checkpoint_path(self.common, checkpoint["invocation_id"])
        LE.write_checkpoint_atomic(path, checkpoint)
        self.assertTrue(path.exists())
        reloaded = LE.read_checkpoint(path)
        self.assertEqual(reloaded, checkpoint)

    def test_write_rejects_invalid_checkpoint(self):
        checkpoint = make_checkpoint()
        del checkpoint["current_phase"]
        path = LE.checkpoint_path(self.common, "bad")
        with self.assertRaises(LE.InvalidCheckpointError):
            LE.write_checkpoint_atomic(path, checkpoint)
        self.assertFalse(path.exists())

    def test_read_rejects_invalid_checkpoint_on_disk(self):
        path = self.common / "bad-checkpoint.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"not": "a checkpoint"}))
        with self.assertRaises(LE.InvalidCheckpointError):
            LE.read_checkpoint(path)

    def test_write_is_atomic_no_leftover_temp_file(self):
        checkpoint = make_checkpoint()
        path = LE.checkpoint_path(self.common, checkpoint["invocation_id"])
        LE.write_checkpoint_atomic(path, checkpoint)
        leftovers = list(path.parent.glob(".tmp-checkpoint-*"))
        self.assertEqual(leftovers, [])

    def test_resume_reconciliation_success(self):
        checkpoint = make_checkpoint()
        invocation = make_invocation(checkpoint)
        LE.reconcile_checkpoint_for_resume(
            invocation=invocation,
            checkpoint=checkpoint,
            live_head=checkpoint["current_head"],
            live_base_sha=checkpoint["comparison_base"]["sha"],
            live_worktree_status={
                "tracked": ["example.py"],
                "staged": [],
                "unstaged": [],
                "untracked": [],
                "ignored": [],
            },
            lock_busy=False,
        )  # no exception raised

    def test_resume_rejects_when_lock_busy(self):
        checkpoint = make_checkpoint()
        invocation = make_invocation(checkpoint)
        with self.assertRaises(LE.CandidateBusyError):
            LE.reconcile_checkpoint_for_resume(
                invocation=invocation,
                checkpoint=checkpoint,
                live_head=checkpoint["current_head"],
                live_base_sha=checkpoint["comparison_base"]["sha"],
                live_worktree_status={
                    "tracked": [],
                    "staged": [],
                    "unstaged": [],
                    "untracked": [],
                    "ignored": [],
                },
                lock_busy=True,
            )

    def test_resume_rejects_stale_invocation_identity_mismatch(self):
        checkpoint = make_checkpoint()
        invocation = make_invocation(checkpoint)
        invocation["candidate"]["branch"] = "some-other-branch"
        with self.assertRaises(LE.CheckpointMismatchError):
            LE.reconcile_checkpoint_for_resume(
                invocation=invocation,
                checkpoint=checkpoint,
                live_head=checkpoint["current_head"],
                live_base_sha=checkpoint["comparison_base"]["sha"],
                live_worktree_status={
                    "tracked": [],
                    "staged": [],
                    "unstaged": [],
                    "untracked": [],
                    "ignored": [],
                },
                lock_busy=False,
            )

    def test_resume_rejects_dirty_worktree(self):
        checkpoint = make_checkpoint()
        invocation = make_invocation(checkpoint)
        with self.assertRaises(LE.DirtyWorktreeError):
            LE.reconcile_checkpoint_for_resume(
                invocation=invocation,
                checkpoint=checkpoint,
                live_head=checkpoint["current_head"],
                live_base_sha=checkpoint["comparison_base"]["sha"],
                live_worktree_status={
                    "tracked": [],
                    "staged": [],
                    "unstaged": ["dirty.py"],
                    "untracked": [],
                    "ignored": [],
                },
                lock_busy=False,
            )

    def test_resume_rejects_live_head_mismatch(self):
        checkpoint = make_checkpoint()
        invocation = make_invocation(checkpoint)
        with self.assertRaises(LE.CheckpointMismatchError):
            LE.reconcile_checkpoint_for_resume(
                invocation=invocation,
                checkpoint=checkpoint,
                live_head="f" * 40,
                live_base_sha=checkpoint["comparison_base"]["sha"],
                live_worktree_status={
                    "tracked": [],
                    "staged": [],
                    "unstaged": [],
                    "untracked": [],
                    "ignored": [],
                },
                lock_busy=False,
            )

    def test_resume_rejects_live_base_mismatch(self):
        checkpoint = make_checkpoint()
        invocation = make_invocation(checkpoint)
        with self.assertRaises(LE.CheckpointMismatchError):
            LE.reconcile_checkpoint_for_resume(
                invocation=invocation,
                checkpoint=checkpoint,
                live_head=checkpoint["current_head"],
                live_base_sha="a" * 40,
                live_worktree_status={
                    "tracked": [],
                    "staged": [],
                    "unstaged": [],
                    "untracked": [],
                    "ignored": [],
                },
                lock_busy=False,
            )


class AttemptLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "repo"
        init_repo(self.repo)
        self.common = LE.git_common_dir(self.repo)
        self.attempts_root = LE.default_attempts_root(self.common)
        self.canonical_head = LE.current_head(self.repo)

    def test_create_attempt_leaves_canonical_untouched(self):
        handle = LE.create_attempt(
            repo=self.repo,
            attempts_root=self.attempts_root,
            base_sha=self.canonical_head,
            invocation_id="inv-1",
            sequence=1,
        )
        self.assertTrue(handle.path.is_dir())
        self.assertNotEqual(handle.path, self.repo)
        (handle.path / "example.py").write_text("value = 1\n")
        # canonical worktree state is unaffected by edits in the attempt worktree
        self.assertFalse((self.repo / "example.py").exists())
        self.assertEqual(LE.current_head(self.repo), self.canonical_head)
        self.assertEqual(LE.current_branch(self.repo), "main")

    def test_commit_attempt_creates_commit_with_expected_parent(self):
        handle = LE.create_attempt(
            repo=self.repo,
            attempts_root=self.attempts_root,
            base_sha=self.canonical_head,
            invocation_id="inv-1",
            sequence=1,
        )
        (handle.path / "example.py").write_text("value = 1\n")
        new_head = LE.commit_attempt(handle, "fix(example): add value")
        parent = LE.git("rev-parse", f"{new_head}^", cwd=handle.path).stdout.strip()
        self.assertEqual(parent, self.canonical_head)
        self.assertEqual(LE.current_head(self.repo), self.canonical_head)

    def test_promote_attempt_success_advances_canonical_atomically(self):
        handle = LE.create_attempt(
            repo=self.repo,
            attempts_root=self.attempts_root,
            base_sha=self.canonical_head,
            invocation_id="inv-1",
            sequence=1,
        )
        (handle.path / "example.py").write_text("value = 1\n")
        new_head = LE.commit_attempt(handle, "fix(example): add value")

        new_canonical = LE.promote_attempt(
            canonical_worktree=self.repo,
            canonical_branch="main",
            attempt_sha=new_head,
            expected_old_head=self.canonical_head,
        )
        self.assertEqual(new_canonical, new_head)
        self.assertEqual(LE.current_head(self.repo), new_head)
        self.assertTrue((self.repo / "example.py").exists())
        self.assertTrue(LE.is_clean(LE.worktree_status(self.repo)))

    def test_promote_attempt_fails_closed_on_dirty_canonical(self):
        handle = LE.create_attempt(
            repo=self.repo,
            attempts_root=self.attempts_root,
            base_sha=self.canonical_head,
            invocation_id="inv-1",
            sequence=1,
        )
        (handle.path / "example.py").write_text("value = 1\n")
        new_head = LE.commit_attempt(handle, "fix(example): add value")

        (self.repo / "dirty.txt").write_text("uncommitted\n")
        with self.assertRaises(LE.DirtyWorktreeError):
            LE.promote_attempt(
                canonical_worktree=self.repo,
                canonical_branch="main",
                attempt_sha=new_head,
                expected_old_head=self.canonical_head,
            )
        # canonical is preserved exactly as it was: still dirty, still at old head
        self.assertEqual(LE.current_head(self.repo), self.canonical_head)
        self.assertTrue((self.repo / "dirty.txt").exists())

    def test_promote_attempt_fails_closed_when_canonical_advanced(self):
        handle = LE.create_attempt(
            repo=self.repo,
            attempts_root=self.attempts_root,
            base_sha=self.canonical_head,
            invocation_id="inv-1",
            sequence=1,
        )
        (handle.path / "example.py").write_text("value = 1\n")
        new_head = LE.commit_attempt(handle, "fix(example): add value")

        # Canonical advances out from under the attempt (a promotion race).
        advanced_head = write_and_commit(
            self.repo, "other.py", "value = 2\n", "unrelated change"
        )

        with self.assertRaises(LE.StaleBaseError):
            LE.promote_attempt(
                canonical_worktree=self.repo,
                canonical_branch="main",
                attempt_sha=new_head,
                expected_old_head=self.canonical_head,
            )
        # the losing attempt's candidate is preserved; canonical is untouched by promotion
        self.assertEqual(LE.current_head(self.repo), advanced_head)
        self.assertTrue(LE.branch_exists(self.repo, handle.branch))
        self.assertEqual(
            LE.git("rev-parse", handle.branch, cwd=self.repo).stdout.strip(), new_head
        )

    def test_promote_attempt_fails_closed_on_wrong_canonical_branch(self):
        handle = LE.create_attempt(
            repo=self.repo,
            attempts_root=self.attempts_root,
            base_sha=self.canonical_head,
            invocation_id="inv-1",
            sequence=1,
        )
        (handle.path / "example.py").write_text("value = 1\n")
        new_head = LE.commit_attempt(handle, "fix(example): add value")

        with self.assertRaises(LE.CandidateIntegrityFailureError):
            LE.promote_attempt(
                canonical_worktree=self.repo,
                canonical_branch="not-main",
                attempt_sha=new_head,
                expected_old_head=self.canonical_head,
            )
        self.assertEqual(LE.current_head(self.repo), self.canonical_head)

    def test_discard_attempt_preserves_patch_and_reason(self):
        handle = LE.create_attempt(
            repo=self.repo,
            attempts_root=self.attempts_root,
            base_sha=self.canonical_head,
            invocation_id="inv-1",
            sequence=1,
        )
        (handle.path / "example.py").write_text("value = 1\n")
        new_head = LE.commit_attempt(handle, "fix(example): add value")

        record = LE.discard_attempt(
            common_dir=self.common,
            handle=handle,
            attempt_sha=new_head,
            reason="the same finding survived this fix",
        )
        self.assertEqual(record["attempt_ref"], handle.branch)
        patch_path = Path(record["patch_path"])
        self.assertTrue(patch_path.exists())
        self.assertIn("example.py", patch_path.read_text())
        # the attempt branch/commit is left in place; nothing is lost
        self.assertTrue(LE.branch_exists(self.repo, handle.branch))

    def test_discard_attempt_without_commit_preserves_working_diff(self):
        handle = LE.create_attempt(
            repo=self.repo,
            attempts_root=self.attempts_root,
            base_sha=self.canonical_head,
            invocation_id="inv-1",
            sequence=1,
        )
        (handle.path / "example.py").write_text("value = 1\n")
        LE.git("add", "-A", cwd=handle.path)  # staged, but validation failed pre-commit

        record = LE.discard_attempt(
            common_dir=self.common,
            handle=handle,
            attempt_sha=None,
            reason="validation failed before a commit was created",
        )
        patch_path = Path(record["patch_path"])
        # nothing was committed, so the working diff itself is preserved instead
        self.assertTrue(patch_path.exists())

    def test_cleanup_attempt_removes_worktree_and_branch(self):
        handle = LE.create_attempt(
            repo=self.repo,
            attempts_root=self.attempts_root,
            base_sha=self.canonical_head,
            invocation_id="inv-1",
            sequence=1,
        )
        LE.cleanup_attempt(repo=self.repo, handle=handle)
        self.assertFalse(handle.path.exists())
        self.assertFalse(LE.branch_exists(self.repo, handle.branch))
        # the canonical branch and worktree are unaffected
        self.assertTrue(LE.branch_exists(self.repo, "main"))
        self.assertEqual(LE.current_head(self.repo), self.canonical_head)

    def test_cleanup_attempt_refuses_branch_outside_namespace(self):
        handle = LE.AttemptHandle(
            path=self.repo, branch="main", base_sha=self.canonical_head
        )
        with self.assertRaises(LE.UnsafeCleanupError):
            LE.cleanup_attempt(repo=self.repo, handle=handle)
        # nothing was touched: canonical branch and worktree remain exactly as they were
        self.assertTrue(LE.branch_exists(self.repo, "main"))
        self.assertTrue(self.repo.is_dir())
        self.assertEqual(LE.current_head(self.repo), self.canonical_head)

    def test_cleanup_attempt_refuses_forged_user_branch_handle(self):
        LE.git("branch", "user-owned-reference-branch", cwd=self.repo)
        handle = LE.AttemptHandle(
            path=self.repo,
            branch="user-owned-reference-branch",
            base_sha=self.canonical_head,
        )
        with self.assertRaises(LE.UnsafeCleanupError):
            LE.cleanup_attempt(repo=self.repo, handle=handle)
        self.assertTrue(LE.branch_exists(self.repo, "user-owned-reference-branch"))


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "repo"
        init_repo(self.repo)
        self.common = LE.git_common_dir(self.repo)
        self.attempts_root = LE.default_attempts_root(self.common)
        self.canonical_head = LE.current_head(self.repo)

    def _checkpoint(self, **overrides) -> dict:
        base = {
            "invocation_id": "inv-recover",
            "initial_head": self.canonical_head,
            "current_head": self.canonical_head,
            "head_history": [self.canonical_head],
        }
        base.update(overrides)
        return make_checkpoint(**base)

    def test_recovers_uniquely_identifiable_committed_attempt(self):
        handle = LE.create_attempt(
            repo=self.repo,
            attempts_root=self.attempts_root,
            base_sha=self.canonical_head,
            invocation_id="inv-recover",
            sequence=1,
        )
        (handle.path / "example.py").write_text("value = 1\n")
        attempt_sha = LE.commit_attempt(handle, "fix(example): add value")

        recovered = LE.recover_interrupted_attempts(
            repo=self.repo, invocation_id="inv-recover", checkpoint=self._checkpoint()
        )
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0].branch, handle.branch)
        self.assertEqual(recovered[0].attempt_sha, attempt_sha)
        self.assertEqual(recovered[0].base_sha, self.canonical_head)
        self.assertFalse(recovered[0].already_promoted)

    def test_recovers_attempt_interrupted_before_any_commit(self):
        LE.create_attempt(
            repo=self.repo,
            attempts_root=self.attempts_root,
            base_sha=self.canonical_head,
            invocation_id="inv-recover",
            sequence=1,
        )
        recovered = LE.recover_interrupted_attempts(
            repo=self.repo, invocation_id="inv-recover", checkpoint=self._checkpoint()
        )
        self.assertEqual(len(recovered), 1)
        self.assertIsNone(recovered[0].attempt_sha)
        self.assertEqual(recovered[0].base_sha, self.canonical_head)

    def test_already_promoted_attempt_is_not_reported_as_leftover(self):
        handle = LE.create_attempt(
            repo=self.repo,
            attempts_root=self.attempts_root,
            base_sha=self.canonical_head,
            invocation_id="inv-recover",
            sequence=1,
        )
        (handle.path / "example.py").write_text("value = 1\n")
        attempt_sha = LE.commit_attempt(handle, "fix(example): add value")
        LE.promote_attempt(
            canonical_worktree=self.repo,
            canonical_branch="main",
            attempt_sha=attempt_sha,
            expected_old_head=self.canonical_head,
        )
        checkpoint = self._checkpoint(
            current_head=attempt_sha,
            head_history=[self.canonical_head, attempt_sha],
            cycle_attempts=[
                {
                    "sequence": 1,
                    "started_from_head": self.canonical_head,
                    "outcome": "committed",
                    "resulting_head": attempt_sha,
                }
            ],
        )
        recovered = LE.recover_interrupted_attempts(
            repo=self.repo, invocation_id="inv-recover", checkpoint=checkpoint
        )
        self.assertEqual(recovered, [])

    def test_ambiguous_branch_not_derived_from_head_history_raises(self):
        # An attempt branch whose base commit is not any recorded head at all.
        rogue_base = write_and_commit(
            self.repo, "rogue.py", "value = 1\n", "unrelated base"
        )
        handle = LE.create_attempt(
            repo=self.repo,
            attempts_root=self.attempts_root,
            base_sha=rogue_base,
            invocation_id="inv-recover",
            sequence=1,
        )
        (handle.path / "more.py").write_text("value = 2\n")
        LE.commit_attempt(handle, "further edit")

        with self.assertRaises(LE.CandidateIntegrityFailureError):
            LE.recover_interrupted_attempts(
                repo=self.repo,
                invocation_id="inv-recover",
                checkpoint=self._checkpoint(),
            )

    def test_two_attempts_claiming_same_base_are_ambiguous(self):
        handle1 = LE.create_attempt(
            repo=self.repo,
            attempts_root=self.attempts_root,
            base_sha=self.canonical_head,
            invocation_id="inv-recover",
            sequence=1,
        )
        (handle1.path / "a.py").write_text("value = 1\n")
        LE.commit_attempt(handle1, "attempt one")

        handle2 = LE.create_attempt(
            repo=self.repo,
            attempts_root=self.attempts_root,
            base_sha=self.canonical_head,
            invocation_id="inv-recover",
            sequence=2,
        )
        (handle2.path / "b.py").write_text("value = 2\n")
        LE.commit_attempt(handle2, "attempt two")

        with self.assertRaises(LE.CandidateIntegrityFailureError):
            LE.recover_interrupted_attempts(
                repo=self.repo,
                invocation_id="inv-recover",
                checkpoint=self._checkpoint(),
            )


class CrossWorktreeLockingTests(unittest.TestCase):
    """Locks are keyed by Git common directory, so two linked worktrees of one
    repository must contend on the same candidate ref lock."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "repo"
        init_repo(self.repo)
        self.other_worktree = Path(self.tmp.name) / "other-worktree"
        LE.git(
            "worktree",
            "add",
            "-b",
            "other-branch",
            str(self.other_worktree),
            "main",
            cwd=self.repo,
        )

    def test_two_linked_worktrees_share_the_same_lock_namespace(self):
        common_from_primary = LE.git_common_dir(self.repo)
        common_from_linked = LE.git_common_dir(self.other_worktree)
        self.assertEqual(common_from_primary, common_from_linked)

        with LE.acquire_candidate_locks(common_from_primary, "refs/heads/main"):
            with self.assertRaises(LE.CandidateBusyError):
                with LE.acquire_candidate_locks(common_from_linked, "refs/heads/main"):
                    pass


if __name__ == "__main__":
    unittest.main()
