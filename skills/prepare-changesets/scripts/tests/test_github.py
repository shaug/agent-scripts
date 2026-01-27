from __future__ import annotations

import shutil
import unittest
from unittest import mock

import github as github_mod
from chain import create_chain
from helpers import chdir, init_repo


class GithubTests(unittest.TestCase):
    def test_pr_create_dry_run_builds_expected_commands(self) -> None:
        repo_dir, plan = init_repo()
        try:
            with chdir(repo_dir):
                create_chain(plan)
                captured: list[tuple[str, ...]] = []

                def capture(cmd: tuple[str, ...]) -> None:
                    captured.append(cmd)

                with mock.patch.object(github_mod, "_print_cmd", side_effect=capture):
                    github_mod.pr_create(plan, indices=[1, 2], dry_run=True)

                self.assertEqual(len(captured), 2)
                self.assertIn("gh", captured[0][0])
                self.assertEqual(captured[0][3:5], ("--base", "main"))
                self.assertEqual(captured[0][5:7], ("--head", "feature/test-1"))
                self.assertEqual(captured[1][3:5], ("--base", "feature/test-1"))
                self.assertEqual(captured[1][5:7], ("--head", "feature/test-2"))
        finally:
            shutil.rmtree(repo_dir)

    def test_pr_merge_dry_run(self) -> None:
        captured: list[tuple[str, ...]] = []

        def capture(cmd: tuple[str, ...]) -> None:
            captured.append(cmd)

        with mock.patch.object(github_mod, "_print_cmd", side_effect=capture):
            github_mod.pr_merge("feature/test-1", method="merge", dry_run=True)

        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0][:3], ("gh", "pr", "merge"))


if __name__ == "__main__":
    unittest.main()
