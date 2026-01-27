from __future__ import annotations

import shutil
import unittest

import helpers  # noqa: F401  # ensures sys.path is set
from chain import compare_chain, create_chain, validate_chain
from common import CommandError
from helpers import chdir, init_repo


class ChainTests(unittest.TestCase):
    def test_create_chain_and_compare_equivalence(self) -> None:
        repo_dir, plan = init_repo()
        try:
            from helpers import run

            source_hash_before = run(
                ["git", "rev-parse", plan["source_branch"]], cwd=repo_dir
            ).stdout.strip()
            with chdir(repo_dir):
                create_chain(plan)
                diffstat, namestatus = compare_chain(plan)
            source_hash_after = run(
                ["git", "rev-parse", plan["source_branch"]], cwd=repo_dir
            ).stdout.strip()

            self.assertEqual(
                source_hash_before, source_hash_after, "Source branch hash changed"
            )
            self.assertEqual(diffstat.strip(), "")
            self.assertEqual(namestatus.strip(), "")
        finally:
            shutil.rmtree(repo_dir)

    def test_validate_chain_runs_tests(self) -> None:
        repo_dir, plan = init_repo()
        try:
            with chdir(repo_dir):
                create_chain(plan)
                validate_chain(plan, test_cmd="python3 -c \"print('ok')\"")
        finally:
            shutil.rmtree(repo_dir)

    def test_validate_chain_fails_on_bad_command(self) -> None:
        repo_dir, plan = init_repo()
        try:
            with chdir(repo_dir):
                create_chain(plan)
                with self.assertRaises(CommandError):
                    validate_chain(
                        plan, test_cmd='python3 -c "import sys; sys.exit(7)"'
                    )
        finally:
            shutil.rmtree(repo_dir)

    def test_validate_chain_discovers_command_from_agents(self) -> None:
        repo_dir, plan = init_repo()
        try:
            (repo_dir / "AGENTS.md").write_text(
                "```bash\npython3 -c \"print('test ok')\"\n```\n"
            )
            from helpers import run

            run(["git", "add", "AGENTS.md"], cwd=repo_dir)
            run(["git", "commit", "-m", "add agents"], cwd=repo_dir)
            with chdir(repo_dir):
                create_chain(plan)
                validate_chain(plan, test_cmd="")
        finally:
            shutil.rmtree(repo_dir)


if __name__ == "__main__":
    unittest.main()
