from __future__ import annotations

import shutil
import unittest

from common import DEFAULT_PLAN_PATH
from legacy_helpers import SCRIPTS_DIR, commit, init_remote, init_repo, run, write_plan


class ScriptIntegrationTests(unittest.TestCase):
    def test_single_cli_exercises_ported_surface(self) -> None:
        repo_dir, plan = init_repo()
        remote_dir = None
        try:
            cli = str(SCRIPTS_DIR / "cli.py")
            plan_path = repo_dir / DEFAULT_PLAN_PATH
            remote_dir = init_remote(repo_dir)
            run(["git", "checkout", "main"], cwd=repo_dir)
            run(["git", "push", "-u", "origin", "main"], cwd=repo_dir)
            run(["git", "checkout", plan["source_branch"]], cwd=repo_dir)
            run(["git", "push", "-u", "origin", plan["source_branch"]], cwd=repo_dir)

            run(
                [
                    cli,
                    "init-plan",
                    "--base",
                    plan["base_branch"],
                    "--source",
                    plan["source_branch"],
                    "--title",
                    plan["feature_title"],
                    "--changesets",
                    "2",
                    "--force",
                ],
                cwd=repo_dir,
            )
            write_plan(plan_path, plan)
            run(
                [
                    cli,
                    "preflight",
                    "--base",
                    plan["base_branch"],
                    "--source",
                    plan["source_branch"],
                    "--skip-tests",
                ],
                cwd=repo_dir,
            )
            run([cli, "validate"], cwd=repo_dir)
            run([cli, "squash-ref"], cwd=repo_dir)
            run([cli, "create-chain"], cwd=repo_dir)
            run(
                [
                    cli,
                    "status",
                    "--source",
                    plan["source_branch"],
                    "--base",
                    plan["base_branch"],
                    "--local-only",
                ],
                cwd=repo_dir,
            )
            run([cli, "squash-check"], cwd=repo_dir)
            run(
                [
                    cli,
                    "validate-chain",
                    "--test-cmd",
                    "python3 -c \"print('ok')\"",
                    "--local-only",
                ],
                cwd=repo_dir,
            )
            run([cli, "compare"], cwd=repo_dir)
            run([cli, "push-chain", "--remote", "origin"], cwd=repo_dir)
            run(
                [
                    "git",
                    "remote",
                    "set-url",
                    "origin",
                    "git@github.com:example/carve-eval.git",
                ],
                cwd=repo_dir,
            )
            run([cli, "pr-create"], cwd=repo_dir)
        finally:
            shutil.rmtree(repo_dir)
            if remote_dir is not None:
                shutil.rmtree(remote_dir.parent)

    def test_help_lists_mutation_class_for_every_operation(self) -> None:
        result = run([str(SCRIPTS_DIR / "cli.py"), "--help"], cwd=SCRIPTS_DIR)
        for mutation_class in ("read-only", "local-mutating", "remote-mutating"):
            self.assertIn(f"[{mutation_class}]", result.stdout)
        self.assertIn("remote mutation is dry-run", result.stdout)
        self.assertIn("by default", result.stdout)

    def test_status_rehydrates_without_a_plan(self) -> None:
        repo_dir, plan = init_repo()
        try:
            cli = str(SCRIPTS_DIR / "cli.py")
            plan_path = repo_dir / DEFAULT_PLAN_PATH
            write_plan(plan_path, plan)
            run([cli, "create-chain"], cwd=repo_dir)
            shutil.rmtree(plan_path.parent)

            result = run(
                [
                    cli,
                    "status",
                    "--source",
                    plan["source_branch"],
                    "--base",
                    plan["base_branch"],
                    "--local-only",
                ],
                cwd=repo_dir,
            )

            self.assertIn("feature/test-1", result.stdout)
            self.assertIn("feature/test-2", result.stdout)
        finally:
            shutil.rmtree(repo_dir)

    def test_strict_validate_rejects_a_rewritten_middle_branch(self) -> None:
        repo_dir, plan = init_repo()
        try:
            cli = str(SCRIPTS_DIR / "cli.py")
            plan_path = repo_dir / DEFAULT_PLAN_PATH
            write_plan(plan_path, plan)
            run([cli, "create-chain"], cwd=repo_dir)
            message = run(
                ["git", "show", "-s", "--format=%B", "feature/test-2"],
                cwd=repo_dir,
            ).stdout
            run(["git", "checkout", "-b", "replacement", "main"], cwd=repo_dir)
            run(
                ["git", "checkout", "feature/test", "--", "a.txt", "b.txt", "c.txt"],
                cwd=repo_dir,
            )
            run(["git", "add", "a.txt", "b.txt", "c.txt"], cwd=repo_dir)
            commit(repo_dir, message)
            replacement = run(["git", "rev-parse", "HEAD"], cwd=repo_dir).stdout.strip()
            run(
                ["git", "update-ref", "refs/heads/feature/test-2", replacement],
                cwd=repo_dir,
            )

            result = run(
                [cli, "validate", "--strict", "--local-only"],
                cwd=repo_dir,
                check=False,
            )

            self.assertEqual(1, result.returncode)
            self.assertIn("predecessor_ancestry_broken", result.stdout)
        finally:
            shutil.rmtree(repo_dir)

    def test_strict_validate_rejects_different_source_history(self) -> None:
        repo_dir, plan = init_repo()
        try:
            cli = str(SCRIPTS_DIR / "cli.py")
            plan_path = repo_dir / DEFAULT_PLAN_PATH
            write_plan(plan_path, plan)
            run([cli, "create-chain"], cwd=repo_dir)
            run(["git", "checkout", "-b", "alternate-source", "main"], cwd=repo_dir)
            run(
                ["git", "checkout", "feature/test", "--", "a.txt", "b.txt", "c.txt"],
                cwd=repo_dir,
            )
            run(["git", "add", "a.txt", "b.txt", "c.txt"], cwd=repo_dir)
            commit(repo_dir, "alternate source history")
            alternate = run(["git", "rev-parse", "HEAD"], cwd=repo_dir).stdout.strip()
            run(
                ["git", "update-ref", "refs/heads/feature/test", alternate],
                cwd=repo_dir,
            )

            result = run(
                [cli, "validate", "--strict", "--local-only"],
                cwd=repo_dir,
                check=False,
            )

            self.assertEqual(1, result.returncode)
            self.assertIn("source_history_mismatch", result.stdout)
        finally:
            shutil.rmtree(repo_dir)


if __name__ == "__main__":
    unittest.main()
