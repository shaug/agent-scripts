from __future__ import annotations

import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

import db_compare as db_compare_mod
from chain import create_chain
from legacy_helpers import chdir, init_repo


class DbCompareTests(unittest.TestCase):
    def test_db_compare_rejects_unknown_command_representations_before_git(
        self,
    ) -> None:
        invalid_values = ["x", ("python3",), {"python3": "-V"}]
        with patch.object(db_compare_mod, "ensure_git_repo") as ensure_git_repo:
            for value in invalid_values:
                with self.subTest(value=value, boundary="source"):
                    with self.assertRaises(db_compare_mod.CommandError):
                        db_compare_mod.db_compare(
                            {},
                            source_argv=value,
                            chain_argv=["true"],
                            out_dir=Path("unused"),
                        )
                with self.subTest(value=value, boundary="chain"):
                    with self.assertRaises(db_compare_mod.CommandError):
                        db_compare_mod.db_compare(
                            {},
                            source_argv=["true"],
                            chain_argv=value,
                            out_dir=Path("unused"),
                        )
            ensure_git_repo.assert_not_called()

    def test_db_compare_creates_outputs(self) -> None:
        repo_dir, plan = init_repo()
        try:
            out_dir = repo_dir / ".carve-changesets" / "db-compare-test"
            with chdir(repo_dir):
                create_chain(plan)
                db_compare_mod.db_compare(
                    plan,
                    source_argv=["cat", "a.txt"],
                    chain_argv=["cat", "a.txt"],
                    out_dir=out_dir,
                )

            source_out = out_dir / "source.txt"
            chain_out = out_dir / "chain.txt"
            self.assertTrue(source_out.exists())
            self.assertTrue(chain_out.exists())
            self.assertEqual(source_out.read_text(), chain_out.read_text())
        finally:
            shutil.rmtree(repo_dir)


if __name__ == "__main__":
    unittest.main()
