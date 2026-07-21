from __future__ import annotations

import shutil
import subprocess
import unittest
from unittest import mock

import github as github_mod
from chain import create_chain
from common import CommandError
from legacy_helpers import chdir, commit, init_remote, init_repo, run


class GithubTests(unittest.TestCase):
    def test_pr_create_dry_run_uses_body_file(self) -> None:
        repo_dir, plan = init_repo()
        try:
            with chdir(repo_dir):
                create_chain(plan)
                captured: list[tuple[str, ...]] = []
                with (
                    mock.patch.object(
                        github_mod,
                        "github_repo_for_remote",
                        return_value="github.com/acme/widgets",
                    ),
                    mock.patch.object(
                        github_mod, "_print_command", side_effect=captured.append
                    ),
                ):
                    github_mod.pr_create(plan, indices=[1, 2], dry_run=True)

            self.assertEqual(2, len(captured))
            for command in captured:
                self.assertEqual(("gh", "pr", "create"), command[:3])
                self.assertIn("github.com/acme/widgets", command)
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

    def test_pr_create_binds_and_verifies_exact_remote_candidate(self) -> None:
        repo_dir, plan = init_repo()
        remote_dir = None
        try:
            remote_dir = init_remote(repo_dir)
            with chdir(repo_dir):
                create_chain(plan)
                run(["git", "push", "origin", "feature/test-1"], cwd=repo_dir)
                head = run(
                    ["git", "rev-parse", "feature/test-1"], cwd=repo_dir
                ).stdout.strip()
                body = github_mod.pr_body_for(
                    plan, 1, len(plan["changesets"]), plan["changesets"][0]
                )
                created = {
                    "number": 91,
                    "url": "https://example.test/pr/91",
                    "headRefOid": head,
                    "baseRefName": "main",
                    "body": body,
                }
                with (
                    mock.patch.object(
                        github_mod,
                        "github_repo_for_remote",
                        return_value="github.com/acme/widgets",
                    ),
                    mock.patch.object(github_mod, "ensure_gh_ready"),
                    mock.patch.object(github_mod, "gh_capture") as create_call,
                    mock.patch.object(
                        github_mod, "gh_json", return_value=created
                    ) as view,
                ):
                    github_mod.pr_create(
                        plan, indices=[1], dry_run=False, remote="origin"
                    )

            create_call.assert_called_once()
            self.assertIn("--body-file", create_call.call_args.args[0])
            self.assertEqual(
                (
                    "pr",
                    "view",
                    "feature/test-1",
                    "-R",
                    "github.com/acme/widgets",
                    "--json",
                    "number,url,headRefOid,baseRefName,body",
                ),
                view.call_args.args[0],
            )
        finally:
            shutil.rmtree(repo_dir)
            if remote_dir is not None:
                shutil.rmtree(remote_dir.parent)

    def test_pr_create_rejects_local_head_not_on_remote(self) -> None:
        repo_dir, plan = init_repo()
        remote_dir = None
        try:
            remote_dir = init_remote(repo_dir)
            with chdir(repo_dir):
                create_chain(plan)
                run(["git", "push", "origin", "feature/test-1"], cwd=repo_dir)
                run(["git", "checkout", "feature/test-1"], cwd=repo_dir)
                (repo_dir / "local-only.txt").write_text("not published\n")
                run(["git", "add", "local-only.txt"], cwd=repo_dir)
                old_message = run(
                    ["git", "show", "-s", "--format=%B", "HEAD"], cwd=repo_dir
                ).stdout
                commit(repo_dir, old_message)
                with (
                    mock.patch.object(
                        github_mod,
                        "github_repo_for_remote",
                        return_value="github.com/acme/widgets",
                    ),
                    mock.patch.object(github_mod, "ensure_gh_ready"),
                    mock.patch.object(github_mod, "gh_capture") as create_call,
                ):
                    with self.assertRaisesRegex(CommandError, "differs from origin"):
                        github_mod.pr_create(
                            plan, indices=[1], dry_run=False, remote="origin"
                        )
            create_call.assert_not_called()
        finally:
            shutil.rmtree(repo_dir)
            if remote_dir is not None:
                shutil.rmtree(remote_dir.parent)

    def test_non_default_remote_binds_all_gh_pr_calls_to_its_repository(
        self,
    ) -> None:
        repo_dir, plan = init_repo()
        try:
            with chdir(repo_dir):
                create_chain(plan)
                run(
                    ["git", "remote", "add", "origin", "git@github.com:wrong/repo.git"],
                    cwd=repo_dir,
                )
                run(
                    [
                        "git",
                        "remote",
                        "add",
                        "release",
                        "ssh://git@github.enterprise.test/acme/widgets.git",
                    ],
                    cwd=repo_dir,
                )
                head = run(
                    ["git", "rev-parse", "feature/test-1"], cwd=repo_dir
                ).stdout.strip()
                body = github_mod.pr_body_for(
                    plan, 1, len(plan["changesets"]), plan["changesets"][0]
                )
                created = {
                    "number": 92,
                    "url": "https://github.enterprise.test/acme/widgets/pull/92",
                    "headRefOid": head,
                    "baseRefName": "main",
                    "body": body,
                }
                with (
                    mock.patch.dict("os.environ", {"GH_REPO": "wrong/other"}),
                    mock.patch.object(github_mod, "ensure_gh_ready") as auth,
                    mock.patch.object(
                        github_mod, "_local_remote_head", return_value=head
                    ),
                    mock.patch.object(github_mod, "gh_capture") as create_call,
                    mock.patch.object(
                        github_mod, "gh_json", return_value=created
                    ) as view_call,
                ):
                    github_mod.pr_create(
                        plan, indices=[1], dry_run=False, remote="release"
                    )

                repository = "github.enterprise.test/acme/widgets"
                auth.assert_called_once_with(repository)
                self.assertIn(
                    ("-R", repository),
                    list(
                        zip(
                            create_call.call_args.args[0],
                            create_call.call_args.args[0][1:],
                        )
                    ),
                )
                self.assertIn(
                    ("-R", repository),
                    list(
                        zip(
                            view_call.call_args.args[0],
                            view_call.call_args.args[0][1:],
                        )
                    ),
                )

                with mock.patch.object(
                    github_mod, "gh_json", return_value=[]
                ) as list_call:
                    self.assertEqual(
                        [],
                        github_mod.pull_requests_for_source(
                            plan["source_branch"], remote="release"
                        ),
                    )
                self.assertIn(
                    ("-R", repository),
                    list(
                        zip(
                            list_call.call_args.args[0],
                            list_call.call_args.args[0][1:],
                        )
                    ),
                )
        finally:
            shutil.rmtree(repo_dir)


if __name__ == "__main__":
    unittest.main()
