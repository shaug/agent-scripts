from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from evals.grader import grade_repo
from evals.helpers import cleanup_repo, init_eval_repo
from evals.runner import main as runner_main
from legacy_helpers import chdir, commit, run


class EvalGraderTests(unittest.TestCase):
    def test_grader_passes_on_deterministic_baseline(self) -> None:
        repo_dir, plan, source_hash = init_eval_repo()
        try:
            plan_path = repo_dir / ".carve-changesets/plan.json"
            with chdir(repo_dir):
                result = grade_repo(
                    plan_path=plan_path,
                    expected_source_hash=source_hash,
                    test_cmd="python3 -c \"print('ok')\"",
                    auto_create_chain=True,
                )
            self.assertTrue(result.ok, f"grader should pass: {result.failures}")
        finally:
            cleanup_repo(repo_dir)

    def test_grader_detects_source_branch_mutation(self) -> None:
        repo_dir, plan, source_hash = init_eval_repo()
        try:
            plan_path = repo_dir / ".carve-changesets/plan.json"
            with chdir(repo_dir):
                # Mutate the source branch after recording its hash.
                (repo_dir / "a.txt").write_text("mutated-source\n")
                run(["git", "add", "a.txt"], cwd=repo_dir)
                commit(repo_dir, "mutate source")

                result = grade_repo(
                    plan_path=plan_path,
                    expected_source_hash=source_hash,
                    test_cmd="python3 -c \"print('ok')\"",
                    auto_create_chain=True,
                )

            self.assertFalse(result.ok)
            self.assertTrue(
                any("source_hash_unchanged" in failure for failure in result.failures),
                f"expected source hash failure, got: {result.failures}",
            )
        finally:
            cleanup_repo(repo_dir)


class EvalRunnerTests(unittest.TestCase):
    def test_runner_skip_codex_produces_passing_summary(self) -> None:
        prompts_path = Path(__file__).resolve().parents[1] / "evals" / "prompts.csv"
        out_dir = Path(tempfile.mkdtemp(prefix="pcs-eval-out-"))
        try:
            rc = runner_main(
                [
                    "--prompts",
                    str(prompts_path),
                    "--out-dir",
                    str(out_dir),
                    "--skip-codex",
                ]
            )
            self.assertEqual(rc, 0)
            summary_path = out_dir / "summary.json"
            self.assertTrue(summary_path.exists())
        finally:
            shutil.rmtree(out_dir)


if __name__ == "__main__":
    unittest.main()
