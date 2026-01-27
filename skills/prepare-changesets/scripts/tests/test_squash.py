from __future__ import annotations

import shutil
import unittest

import helpers  # noqa: F401  # ensures sys.path is set
from chain import create_chain
from helpers import chdir, init_repo, run
from squash_check import squash_check
from squash_ref import create_squashed_ref


class SquashReferenceTests(unittest.TestCase):
    def test_squash_ref_creates_tree_equivalent_branch(self) -> None:
        repo_dir, plan = init_repo()
        try:
            with chdir(repo_dir):
                squashed = create_squashed_ref(
                    base=plan["base_branch"],
                    source=plan["source_branch"],
                    reuse_existing=False,
                    recreate=False,
                )

            source_tree = run(
                ["git", "rev-parse", f"{plan['source_branch']}^{{tree}}"], cwd=repo_dir
            ).stdout.strip()
            squashed_tree = run(
                ["git", "rev-parse", f"{squashed}^{{tree}}"], cwd=repo_dir
            ).stdout.strip()
            self.assertEqual(source_tree, squashed_tree)
        finally:
            shutil.rmtree(repo_dir)

    def test_squash_check_reports_no_diff_when_chain_matches_source(self) -> None:
        repo_dir, plan = init_repo()
        try:
            with chdir(repo_dir):
                create_squashed_ref(
                    base=plan["base_branch"],
                    source=plan["source_branch"],
                    reuse_existing=False,
                    recreate=False,
                )
                create_chain(plan)
                diffstat, namestatus = squash_check(plan)

            self.assertEqual(diffstat.strip(), "")
            self.assertEqual(namestatus.strip(), "")
        finally:
            shutil.rmtree(repo_dir)


if __name__ == "__main__":
    unittest.main()
