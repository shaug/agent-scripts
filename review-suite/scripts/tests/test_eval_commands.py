"""Command-contract tests for the three review-suite evaluation entrypoints.

These names are part of the repository's contract with #58 and with anyone
running an evaluation, so they are asserted rather than assumed. The paid path
must stay out of the ordinary quality gates.
"""

from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
JUSTFILE = REPOSITORY_ROOT / "justfile"
README = REPOSITORY_ROOT / "README.md"
EVAL_README = REPOSITORY_ROOT / "review-suite" / "evals" / "README.md"

TEST_COMMAND = "test-review-suite"
AUDIT_COMMAND = "audit-review-corpus"
EVAL_COMMAND = "eval-review-suite"


def recipes(text: str) -> dict[str, str]:
    """Split a justfile into recipe name -> its dependency and body text."""
    found: dict[str, str] = {}
    name = None
    for line in text.splitlines():
        match = re.match(r"^([a-z][a-z0-9-]*)\s*([^:]*):(.*)$", line)
        if match and not line.startswith((" ", "\t")):
            name = match.group(1)
            found[name] = f"{match.group(2)}:{match.group(3)}\n"
        elif name and (line.startswith((" ", "\t")) or not line.strip()):
            found[name] += line + "\n"
        else:
            name = None
    return found


class JustfileContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.recipes = recipes(JUSTFILE.read_text())

    def test_all_three_recipes_exist_under_their_exact_names(self):
        for name in (TEST_COMMAND, AUDIT_COMMAND, EVAL_COMMAND):
            self.assertIn(name, self.recipes)

    def test_the_evaluation_recipe_takes_one_executor_argument(self):
        header = self.recipes[EVAL_COMMAND].splitlines()[0]
        self.assertIn("executor:", header)
        self.assertIn('--executor "{{executor}}"', self.recipes[EVAL_COMMAND])

    def test_the_deterministic_recipes_take_no_argument(self):
        for name in (TEST_COMMAND, AUDIT_COMMAND):
            with self.subTest(recipe=name):
                self.assertEqual(":", self.recipes[name].splitlines()[0].strip())

    def test_test_runs_the_review_suite_tests(self):
        self.assertIn("review-suite/scripts/tests", self.recipes["test"])

    def test_no_quality_gate_can_reach_the_paid_command(self):
        """`test`, `lint`, and `check` must never spend money."""
        reachable = set()
        frontier = ["test", "lint", "check"]
        while frontier:
            name = frontier.pop()
            if name in reachable or name not in self.recipes:
                continue
            reachable.add(name)
            dependencies, _, _ = self.recipes[name].partition(":")
            body = self.recipes[name]
            frontier.extend(dependencies.split())
            frontier.extend(
                candidate for candidate in self.recipes if f"just {candidate}" in body
            )
        self.assertNotIn(EVAL_COMMAND, reachable)
        for name in sorted(reachable):
            with self.subTest(recipe=name):
                self.assertNotIn(EVAL_COMMAND, self.recipes[name])
                self.assertNotIn("evals/runner.py", self.recipes[name])
                self.assertNotIn("claude_executor.py", self.recipes[name])

    def test_the_recipes_point_at_the_canonical_scripts(self):
        self.assertIn(
            "review-suite/scripts/evals/audit_corpus.py", self.recipes[AUDIT_COMMAND]
        )
        self.assertIn(
            "review-suite/scripts/evals/runner.py", self.recipes[EVAL_COMMAND]
        )


class DocumentationContractTests(unittest.TestCase):
    """Documented prose is compared with Markdown line wrapping collapsed."""

    @staticmethod
    def unwrapped(path: Path) -> str:
        return re.sub(r"\s+", " ", path.read_text())

    def test_both_readmes_document_all_three_command_names(self):
        for path in (README, EVAL_README):
            text = self.unwrapped(path)
            for name in (TEST_COMMAND, AUDIT_COMMAND, EVAL_COMMAND):
                with self.subTest(path=path.name, command=name):
                    self.assertIn(f"just {name}", text)

    def test_both_readmes_show_the_evaluation_argument(self):
        for path in (README, EVAL_README):
            with self.subTest(path=path.name):
                self.assertIn(
                    f"just {EVAL_COMMAND} '<executor command>'", self.unwrapped(path)
                )

    def test_both_readmes_state_that_the_paid_path_is_opt_in(self):
        for path in (README, EVAL_README):
            with self.subTest(path=path.name):
                text = self.unwrapped(path)
                self.assertIn("never launches a paid runtime", text)
                self.assertIn(
                    f"`just {EVAL_COMMAND}` is deliberately absent from `test`, "
                    "`lint`, and `check`",
                    text,
                )


class RecipeExecutionTests(unittest.TestCase):
    """Run the recipes through `just` when it is installed."""

    @classmethod
    def setUpClass(cls):
        if (
            subprocess.run(
                ["just", "--version"], capture_output=True, check=False
            ).returncode
            != 0
        ):
            raise unittest.SkipTest("just is not installed")

    def just(self, *args):
        return subprocess.run(
            ["just", *args],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_audit_review_corpus_passes(self):
        completed = self.just(AUDIT_COMMAND)
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn("corpus audit passed", completed.stdout)

    def test_eval_review_suite_requires_its_argument(self):
        completed = self.just(EVAL_COMMAND)
        self.assertNotEqual(0, completed.returncode)

    def test_eval_review_suite_reports_a_bad_executor(self):
        completed = self.just(EVAL_COMMAND, "/nonexistent/review-executor")
        self.assertEqual(1, completed.returncode, completed.stdout)
        self.assertIn("spawn_failure", completed.stderr)

    def test_eval_review_suite_accepts_the_deterministic_executor(self):
        completed = self.just(
            EVAL_COMMAND,
            f"{sys.executable} review-suite/scripts/evals/fixture_executor.py",
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn('"baseline_eligible": false', completed.stdout)


if __name__ == "__main__":
    unittest.main()
