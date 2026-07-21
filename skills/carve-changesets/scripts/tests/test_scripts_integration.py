from __future__ import annotations

import shutil
import unittest

from common import DEFAULT_PLAN_PATH
from legacy_helpers import SCRIPTS_DIR, init_remote, init_repo, run, write_plan


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
            run([cli, "status", "--local-only"], cwd=repo_dir)
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
            run([cli, "pr-create"], cwd=repo_dir)
            run([cli, "push-chain", "--remote", "origin"], cwd=repo_dir)
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


if __name__ == "__main__":
    unittest.main()
