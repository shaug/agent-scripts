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


#: `name param1 *variadic: dep1 dep2` - parameters precede the colon,
#: dependencies follow it. Keeping the three apart matters: deriving dependencies
#: by re-splitting a joined string silently yields nothing for
#: `test: test-plugins`, which would make the paid-path guard below inert.
#:
#: A parameter may carry just's `*` or `+` variadic prefix. Without that, a
#: variadic recipe matches nothing at all and every assertion about it becomes a
#: `KeyError` rather than a failure - including the paid-path guard, which would
#: stop seeing the one recipe that can spend money.
RECIPE_HEADER = re.compile(r"^([a-z][a-z0-9-]*)((?:\s+[*+]?[a-z0-9-]+)*)\s*:(.*)$")


def recipes(text: str) -> dict[str, dict[str, object]]:
    """Parse a justfile into {name: {parameters, dependencies, body}}."""
    found: dict[str, dict[str, object]] = {}
    name = None
    for line in text.splitlines():
        indented = line.startswith((" ", "\t"))
        if ":=" in line and not indented:
            name = None  # a top-level assignment, not a recipe
            continue
        header = None if indented else RECIPE_HEADER.match(line)
        if header:
            name = header.group(1)
            found[name] = {
                "parameters": header.group(2).split(),
                "dependencies": header.group(3).split(),
                "body": "",
            }
        elif name and (indented or not line.strip()):
            found[name]["body"] += line + "\n"
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

    def test_the_evaluation_recipe_takes_an_executor_and_forwards_the_rest(self):
        """The executor stays required; runner options must reach the runner.

        A recipe taking only an executor cannot execute a frozen per-stratum
        configuration at all: `--corpus` defaults to the protocol-proof corpus
        and `--runs` to 1, so the documented command would silently evaluate the
        wrong corpus once.
        """
        self.assertEqual(
            ["executor", "*args"], self.recipes[EVAL_COMMAND]["parameters"]
        )
        self.assertIn('--executor "{{executor}}"', self.recipes[EVAL_COMMAND]["body"])
        self.assertIn("{{args}}", self.recipes[EVAL_COMMAND]["body"])

    def test_the_deterministic_recipes_take_no_argument(self):
        for name in (TEST_COMMAND, AUDIT_COMMAND):
            with self.subTest(recipe=name):
                self.assertEqual([], self.recipes[name]["parameters"])

    def test_the_justfile_parser_sees_real_dependencies(self):
        """Guard the guard: an empty closure would make the check below inert."""
        self.assertEqual(["test-plugins"], self.recipes["test"]["dependencies"])
        self.assertEqual(["test", "lint"], self.recipes["check"]["dependencies"])
        self.assertEqual(
            ["lint-py", "lint-md", "lint-skills", "validate-plugins"],
            self.recipes["lint"]["dependencies"],
        )

    def test_test_runs_the_review_suite_tests(self):
        self.assertIn("review-suite/scripts/tests", self.recipes["test"]["body"])

    def _quality_gate_closure(self) -> set[str]:
        reachable: set[str] = set()
        frontier = ["test", "lint", "check"]
        while frontier:
            name = frontier.pop()
            if name in reachable or name not in self.recipes:
                continue
            reachable.add(name)
            recipe = self.recipes[name]
            frontier.extend(recipe["dependencies"])
            frontier.extend(
                candidate
                for candidate in self.recipes
                if f"just {candidate}" in recipe["body"]
            )
        return reachable

    def test_the_quality_gate_closure_reaches_every_transitive_recipe(self):
        """A closure that stops at the seeds would prove nothing."""
        reachable = self._quality_gate_closure()
        for name in (
            "test",
            "lint",
            "check",
            "test-plugins",
            "lint-py",
            "lint-md",
            "lint-skills",
            "validate-plugins",
        ):
            with self.subTest(recipe=name):
                self.assertIn(name, reachable)

    def test_no_quality_gate_can_reach_the_paid_command(self):
        """`test`, `lint`, and `check` must never spend money."""
        reachable = self._quality_gate_closure()
        self.assertNotIn(EVAL_COMMAND, reachable)
        for name in sorted(reachable):
            with self.subTest(recipe=name):
                recipe = self.recipes[name]
                self.assertNotIn(EVAL_COMMAND, recipe["dependencies"])
                for forbidden in (
                    EVAL_COMMAND,
                    "evals/runner.py",
                    "claude_executor",
                ):
                    self.assertNotIn(forbidden, recipe["body"])

    def test_the_recipes_point_at_the_canonical_scripts(self):
        self.assertIn(
            "review-suite/scripts/evals/audit_corpus.py",
            self.recipes[AUDIT_COMMAND]["body"],
        )
        self.assertIn(
            "review-suite/scripts/evals/runner.py", self.recipes[EVAL_COMMAND]["body"]
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
    """Run the recipes through `just` when it is installed.

    CI does not install `just`, so this class must skip cleanly there. An absent
    executable makes `subprocess.run` raise rather than return a status, so the
    probe has to catch `OSError`; checking only the return code turns a missing
    `just` into an erroring `setUpClass` instead of a skip.
    """

    @classmethod
    def setUpClass(cls):
        try:
            completed = subprocess.run(
                ["just", "--version"], capture_output=True, check=False
            )
        except OSError as error:
            raise unittest.SkipTest(f"just is unavailable: {error}") from error
        if completed.returncode != 0:
            raise unittest.SkipTest("just is present but not runnable")

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
