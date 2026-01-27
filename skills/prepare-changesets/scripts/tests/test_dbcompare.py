from __future__ import annotations

import shutil
import unittest

import dbcompare as dbcompare_mod
from chain import create_chain
from helpers import chdir, init_repo


class DbCompareTests(unittest.TestCase):
    def test_db_compare_creates_outputs(self) -> None:
        repo_dir, plan = init_repo()
        try:
            out_dir = repo_dir / ".prepare-changesets" / "db-compare-test"
            with chdir(repo_dir):
                create_chain(plan)
                dbcompare_mod.db_compare(
                    plan,
                    source_cmd="cat a.txt",
                    chain_cmd="cat a.txt",
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
