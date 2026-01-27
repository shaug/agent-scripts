from __future__ import annotations

import shutil
import unittest

import preflight as preflight_mod
from common import CommandError
from helpers import chdir, init_conflict_repo, init_repo, run


class PreflightTests(unittest.TestCase):
    def test_preflight_success_does_not_modify_source(self) -> None:
        repo_dir, plan = init_repo()
        try:
            source_hash_before = run(
                ["git", "rev-parse", plan["source_branch"]], cwd=repo_dir
            ).stdout.strip()
            with chdir(repo_dir):
                preflight_mod.preflight(
                    base=plan["base_branch"],
                    source=plan["source_branch"],
                    test_cmd="python3 -c \"print('ok')\"",
                    skip_tests=False,
                    skip_merge_check=False,
                )
            source_hash_after = run(
                ["git", "rev-parse", plan["source_branch"]], cwd=repo_dir
            ).stdout.strip()
            self.assertEqual(source_hash_before, source_hash_after)
        finally:
            shutil.rmtree(repo_dir)

    def test_preflight_detects_conflicts(self) -> None:
        repo_dir, plan = init_conflict_repo()
        try:
            with chdir(repo_dir):
                with self.assertRaises(CommandError):
                    preflight_mod.preflight(
                        base=plan["base_branch"],
                        source=plan["source_branch"],
                        test_cmd="",
                        skip_tests=True,
                        skip_merge_check=False,
                    )
        finally:
            shutil.rmtree(repo_dir)

    def test_preflight_fails_when_source_behind_base(self) -> None:
        repo_dir, plan = init_repo()
        try:
            run(["git", "checkout", plan["base_branch"]], cwd=repo_dir)
            (repo_dir / "base.txt").write_text("base-update\n")
            run(["git", "add", "base.txt"], cwd=repo_dir)
            run(["git", "commit", "-m", "base update"], cwd=repo_dir)
            with chdir(repo_dir):
                with self.assertRaises(CommandError):
                    preflight_mod.preflight(
                        base=plan["base_branch"],
                        source=plan["source_branch"],
                        test_cmd="",
                        skip_tests=True,
                        skip_merge_check=True,
                    )
        finally:
            shutil.rmtree(repo_dir)

    def test_preflight_allows_source_behind_with_override(self) -> None:
        repo_dir, plan = init_repo()
        try:
            run(["git", "checkout", plan["base_branch"]], cwd=repo_dir)
            (repo_dir / "base.txt").write_text("base-update\n")
            run(["git", "add", "base.txt"], cwd=repo_dir)
            run(["git", "commit", "-m", "base update"], cwd=repo_dir)
            with chdir(repo_dir):
                preflight_mod.preflight(
                    base=plan["base_branch"],
                    source=plan["source_branch"],
                    test_cmd="",
                    skip_tests=True,
                    skip_merge_check=True,
                    allow_source_behind_base=True,
                )
        finally:
            shutil.rmtree(repo_dir)

    def test_preflight_requires_recordkeeping_ignored(self) -> None:
        repo_dir, plan = init_repo()
        try:
            (repo_dir / ".gitignore").write_text("")
            run(["git", "add", ".gitignore"], cwd=repo_dir)
            run(["git", "commit", "-m", "update ignore"], cwd=repo_dir)
            with chdir(repo_dir):
                with self.assertRaises(CommandError):
                    preflight_mod.preflight(
                        base=plan["base_branch"],
                        source=plan["source_branch"],
                        test_cmd="",
                        skip_tests=True,
                        skip_merge_check=True,
                    )
        finally:
            shutil.rmtree(repo_dir)

    def test_preflight_allows_recordkeeping_tracked_with_override(self) -> None:
        repo_dir, plan = init_repo()
        try:
            (repo_dir / ".gitignore").write_text("")
            run(["git", "add", ".gitignore"], cwd=repo_dir)
            run(["git", "commit", "-m", "update ignore"], cwd=repo_dir)
            with chdir(repo_dir):
                preflight_mod.preflight(
                    base=plan["base_branch"],
                    source=plan["source_branch"],
                    test_cmd="",
                    skip_tests=True,
                    skip_merge_check=True,
                    allow_recordkeeping_tracked=True,
                )
        finally:
            shutil.rmtree(repo_dir)


if __name__ == "__main__":
    unittest.main()
