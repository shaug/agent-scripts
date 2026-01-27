from __future__ import annotations

import shutil
import unittest

from common import DEFAULT_PLAN_PATH
from helpers import SCRIPTS_DIR, init_remote, init_repo, run, write_plan


class ScriptIntegrationTests(unittest.TestCase):
    def test_scripts_are_runnable(self) -> None:
        repo_dir, plan = init_repo()
        remote_dir = None
        try:
            scripts = SCRIPTS_DIR
            plan_path = repo_dir / DEFAULT_PLAN_PATH

            remote_dir = init_remote(repo_dir)

            run(["git", "checkout", "main"], cwd=repo_dir)
            run(["git", "push", "-u", "origin", "main"], cwd=repo_dir)
            run(["git", "checkout", plan["source_branch"]], cwd=repo_dir)
            run(["git", "push", "-u", "origin", plan["source_branch"]], cwd=repo_dir)

            # Exercise init-plan script, then replace it with the test-specific plan.
            run(
                [
                    str(scripts / "init_plan.py"),
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
                    str(scripts / "preflight.py"),
                    "--base",
                    plan["base_branch"],
                    "--source",
                    plan["source_branch"],
                    "--skip-tests",
                ],
                cwd=repo_dir,
            )
            run(
                [
                    str(scripts / "squash_ref.py"),
                    "--base",
                    plan["base_branch"],
                    "--source",
                    plan["source_branch"],
                ],
                cwd=repo_dir,
            )
            run([str(scripts / "validate.py")], cwd=repo_dir)
            run([str(scripts / "status.py")], cwd=repo_dir)
            run([str(scripts / "create_chain.py")], cwd=repo_dir)
            run([str(scripts / "squash_check.py")], cwd=repo_dir)
            run(
                [
                    str(scripts / "validate_chain.py"),
                    "--test-cmd",
                    "python3 -c \"print('ok')\"",
                ],
                cwd=repo_dir,
            )
            run([str(scripts / "compare.py")], cwd=repo_dir)
            run(
                [
                    str(scripts / "propagate.py"),
                    "--merged-index",
                    "1",
                    "--skip-local-merge",
                ],
                cwd=repo_dir,
            )
            run([str(scripts / "pr_create.py")], cwd=repo_dir)
            run(
                [
                    str(scripts / "db_compare.py"),
                    "--source-cmd",
                    "cat a.txt",
                    "--chain-cmd",
                    "cat a.txt",
                    "--out-dir",
                    str(repo_dir / ".prepare-changesets" / "db-compare-script"),
                ],
                cwd=repo_dir,
            )
            run(
                [
                    str(scripts / "push_chain.py"),
                    "--remote",
                    "origin",
                ],
                cwd=repo_dir,
            )
        finally:
            shutil.rmtree(repo_dir)
            if remote_dir is not None:
                shutil.rmtree(remote_dir.parent)


if __name__ == "__main__":
    unittest.main()
