from __future__ import annotations

import shutil
import unittest
from unittest import mock

from helpers import chdir, init_remote, init_repo, run
from propagate import downstream_base_after_merge, propagate_downstream, push_chain


class PropagateTests(unittest.TestCase):
    def test_downstream_base_after_merge_matrix(self) -> None:
        base = "main"
        source = "feature/test"
        total = 3

        self.assertEqual(downstream_base_after_merge(base, source, total, 0, 1), "main")
        self.assertEqual(
            downstream_base_after_merge(base, source, total, 0, 2),
            "feature/test-1-of-3",
        )
        self.assertEqual(downstream_base_after_merge(base, source, total, 1, 2), "main")
        self.assertEqual(
            downstream_base_after_merge(base, source, total, 2, 3),
            "feature/test-1-of-3",
        )

    def test_propagate_dry_run_updates_expected_pr_bases(self) -> None:
        repo_dir, plan = init_repo()
        try:
            from chain import create_chain

            with chdir(repo_dir):
                create_chain(plan)
                bases: list[str] = []

                def record_base(new_base: str, *, dry_run: bool) -> None:
                    del dry_run
                    bases.append(new_base)

                with mock.patch("propagate.pr_edit_base", side_effect=record_base):
                    propagate_downstream(
                        plan=plan,
                        merged_index=1,
                        dry_run=True,
                        update_pr_bases=True,
                        skip_local_merge=True,
                        push=False,
                        remote="origin",
                    )

                self.assertEqual(bases, ["main"])
        finally:
            shutil.rmtree(repo_dir)

    def test_propagate_can_push_to_bare_remote(self) -> None:
        repo_dir, plan = init_repo()
        remote_dir = None
        try:
            remote_dir = init_remote(repo_dir)

            run(["git", "checkout", "main"], cwd=repo_dir)
            run(["git", "push", "-u", "origin", "main"], cwd=repo_dir)
            run(["git", "checkout", plan["source_branch"]], cwd=repo_dir)
            run(["git", "push", "-u", "origin", plan["source_branch"]], cwd=repo_dir)

            from chain import create_chain

            with chdir(repo_dir):
                create_chain(plan)
                push_chain(plan, remote="origin", dry_run=False)

                cs1 = f"{plan['source_branch']}-1-of-2"
                run(["git", "checkout", cs1], cwd=repo_dir)
                (repo_dir / "a.txt").write_text("feature-a-updated\n")
                run(["git", "add", "a.txt"], cwd=repo_dir)
                run(["git", "commit", "-m", "cs1 update"], cwd=repo_dir)

                propagate_downstream(
                    plan=plan,
                    merged_index=1,
                    dry_run=False,
                    update_pr_bases=False,
                    skip_local_merge=False,
                    push=True,
                    remote="origin",
                )

            cs2 = f"{plan['source_branch']}-2-of-2"
            local_cs2 = run(["git", "rev-parse", cs2], cwd=repo_dir).stdout.strip()
            remote_cs2 = run(
                ["git", "ls-remote", "origin", cs2], cwd=repo_dir
            ).stdout.split()[0]
            self.assertEqual(local_cs2, remote_cs2)
        finally:
            shutil.rmtree(repo_dir)
            if remote_dir is not None:
                shutil.rmtree(remote_dir.parent)


if __name__ == "__main__":
    unittest.main()
