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

    def test_create_chain_is_append_only_for_existing_prefix(self) -> None:
        repo_dir, plan = init_repo()
        try:
            from helpers import run

            with chdir(repo_dir):
                create_chain(plan)
                cs1 = f"{plan['source_branch']}-1"
                cs2 = f"{plan['source_branch']}-2"
                cs1_before = run(["git", "rev-parse", cs1], cwd=repo_dir).stdout.strip()
                cs2_before = run(["git", "rev-parse", cs2], cwd=repo_dir).stdout.strip()

                plan["changesets"].append(
                    {
                        "slug": "noop-3",
                        "description": "Placeholder changeset to test append-only behavior.",
                        "include_paths": ["does-not-exist.txt"],
                        "exclude_paths": [],
                        "commit_message": "cs3",
                        "pr_notes": [],
                    }
                )

                create_chain(plan)
                cs1_after = run(["git", "rev-parse", cs1], cwd=repo_dir).stdout.strip()
                cs2_after = run(["git", "rev-parse", cs2], cwd=repo_dir).stdout.strip()
                cs3 = f"{plan['source_branch']}-3"
                cs3_rc = run(
                    ["git", "rev-parse", "--verify", cs3], cwd=repo_dir, check=False
                ).returncode

            self.assertEqual(cs1_before, cs1_after)
            self.assertEqual(cs2_before, cs2_after)
            self.assertEqual(cs3_rc, 0)
        finally:
            shutil.rmtree(repo_dir)


if __name__ == "__main__":
    unittest.main()
