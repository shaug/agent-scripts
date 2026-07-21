from __future__ import annotations

import shutil
import subprocess
import unittest
from unittest import mock

import github as github_mod
from chain import create_chain
from common import CommandError
from legacy_helpers import chdir, init_repo


class GithubTests(unittest.TestCase):
    def test_pr_create_dry_run_uses_body_file(self) -> None:
        repo_dir, plan = init_repo()
        try:
            with chdir(repo_dir):
                create_chain(plan)
                captured: list[tuple[str, ...]] = []
                with mock.patch.object(
                    github_mod, "_print_command", side_effect=captured.append
                ):
                    github_mod.pr_create(plan, indices=[1, 2], dry_run=True)

            self.assertEqual(2, len(captured))
            for command in captured:
                self.assertEqual(("gh", "pr", "create"), command[:3])
                self.assertIn("--body-file", command)
                self.assertNotIn("--body", command)
        finally:
            shutil.rmtree(repo_dir)

    def test_gh_capture_wraps_missing_executable(self) -> None:
        with mock.patch("github.subprocess.run", side_effect=FileNotFoundError):
            with self.assertRaisesRegex(CommandError, "not found"):
                github_mod.gh_capture(("auth", "status"))

    def test_gh_capture_allows_only_named_return_codes(self) -> None:
        error = subprocess.CalledProcessError(
            4, ["gh", "example"], output="allowed", stderr="detail"
        )
        with mock.patch("github.subprocess.run", side_effect=error):
            stdout, stderr = github_mod.gh_capture(
                ("example",), allowed_returncodes=(4,)
            )
        self.assertEqual("allowed", stdout)
        self.assertEqual("detail", stderr)

        with mock.patch("github.subprocess.run", side_effect=error):
            with self.assertRaisesRegex(CommandError, "GitHub CLI command failed"):
                github_mod.gh_capture(("example",))


if __name__ == "__main__":
    unittest.main()
