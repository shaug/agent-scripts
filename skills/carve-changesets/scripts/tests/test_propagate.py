from __future__ import annotations

import shutil
import unittest
from unittest import mock

from chain import create_chain
from legacy_helpers import chdir, init_remote, init_repo, run
from propagate import push_chain


class PushChainTests(unittest.TestCase):
    def test_push_chain_never_sends_base_or_source_to_force_push(self) -> None:
        repo_dir, plan = init_repo()
        remote_dir = None
        try:
            remote_dir = init_remote(repo_dir)
            with chdir(repo_dir):
                create_chain(plan)
                pushed: list[str] = []
                with mock.patch(
                    "propagate.push_changeset_branch",
                    side_effect=lambda branch, **_kwargs: pushed.append(branch),
                ):
                    push_chain(plan, remote="origin", dry_run=True)

            self.assertEqual(["feature/test-1", "feature/test-2"], pushed)
            self.assertNotIn(plan["base_branch"], pushed)
            self.assertNotIn(plan["source_branch"], pushed)
        finally:
            shutil.rmtree(repo_dir)
            if remote_dir is not None:
                shutil.rmtree(remote_dir.parent)

    def test_push_chain_uses_exact_refspecs_and_leases(self) -> None:
        repo_dir, plan = init_repo()
        remote_dir = None
        try:
            remote_dir = init_remote(repo_dir)
            with chdir(repo_dir):
                create_chain(plan)
                push_chain(plan, remote="origin", dry_run=False)

            for branch in ("feature/test-1", "feature/test-2"):
                remote = run(
                    ["git", "ls-remote", "origin", f"refs/heads/{branch}"],
                    cwd=repo_dir,
                ).stdout.strip()
                self.assertTrue(remote)
            base = run(
                ["git", "ls-remote", "origin", "refs/heads/main"], cwd=repo_dir
            ).stdout.strip()
            self.assertEqual("", base)
        finally:
            shutil.rmtree(repo_dir)
            if remote_dir is not None:
                shutil.rmtree(remote_dir.parent)


if __name__ == "__main__":
    unittest.main()
