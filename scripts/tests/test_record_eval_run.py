"""Behavioral tests for the eval-evidence recorder's public surface.

Each test is derived from an acceptance criterion of issue #135 and exercises
the recorder the way an author does: through its command line, asserting on
the summary it writes. No test inspects the recorder's internals, and no test
launches a model — the runs under test are stubbed commands whose exact text
the summary is required to preserve.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "record_eval_run", REPOSITORY_ROOT / "scripts" / "record_eval_run.py"
)
assert SPEC is not None and SPEC.loader is not None
record_eval_run = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(record_eval_run)


STUB_HARNESS = """\
import json, pathlib, sys

passed, failed = json.loads(sys.argv[1]), json.loads(sys.argv[2])
args = sys.argv[3:]
if "--output-dir" in args:
    directory = pathlib.Path(args[args.index("--output-dir") + 1])
    for case in passed + failed:
        (directory / (case + ".json")).write_text("{}")
print(
    json.dumps(
        {
            "total": len(passed) + len(failed),
            "passed": len(passed),
            "failed": len(failed),
            "failures": [case + ": terminal_state mismatch" for case in failed],
        }
    )
)
sys.exit(1 if failed else 0)
"""


class RecorderTests(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.root = Path(self._directory.name)
        self.skills = self.root / "skills"
        (self.skills / "demo-skill" / "evals").mkdir(parents=True)
        (self.skills / "tested-skill" / "scripts" / "tests").mkdir(parents=True)
        patcher = mock.patch.multiple(
            record_eval_run,
            REPOSITORY_ROOT=self.root,
            SKILLS_DIR=self.skills,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        self.harness = self.root / "stub_harness.py"
        self.harness.write_text(STUB_HARNESS, encoding="utf-8")

    def stub(self, passed: list[str], failed: list[str]) -> str:
        """A command mimicking a forward-eval harness: per-case files + summary."""
        return shlex.join(
            [
                sys.executable,
                str(self.harness),
                json.dumps(passed),
                json.dumps(failed),
            ]
        )

    def results(self, skill: str) -> list[Path]:
        directory = self.skills / skill / "evals" / "results"
        return sorted(directory.glob("*.json")) if directory.is_dir() else []

    def run_recorder(self, *argv: str) -> int:
        return record_eval_run.main(list(argv))

    def read_only_summary(self, skill: str) -> dict:
        files = self.results(skill)
        self.assertEqual(len(files), 1, f"expected one summary, got {files}")
        return json.loads(files[0].read_text(encoding="utf-8"))

    # AC: the target produces a committed-format summary from an executor run.
    def test_run_is_recorded_under_the_skills_results_directory(self) -> None:
        exit_code = self.run_recorder(
            "demo-skill",
            "--stage",
            "baseline",
            "--command",
            self.stub(passed=["alpha", "beta"], failed=[]),
            "--per-case-output-dir",
        )

        self.assertEqual(exit_code, 0)
        files = self.results("demo-skill")
        self.assertEqual(len(files), 1)
        self.assertTrue(files[0].name.endswith("-baseline.json"))

        summary = json.loads(files[0].read_text(encoding="utf-8"))
        self.assertEqual(summary["skill"], "demo-skill")
        self.assertEqual(summary["stage"], "baseline")
        self.assertEqual(summary["status"], "completed")
        self.assertRegex(summary["recorded_at"], r"^\d{4}-\d{2}-\d{2}T")
        self.assertEqual(summary["totals"], {"total": 2, "passed": 2, "failed": 0})
        self.assertEqual(summary["cases"], {"alpha": "pass", "beta": "pass"})
        # The exact command is recorded verbatim, so a reader can tell what
        # actually ran. Assert the harness, not the interpreter's filename,
        # which differs between environments.
        self.assertEqual(summary["command"][0], sys.executable)
        self.assertIn(str(self.harness), summary["command"])

    # AC: summaries carry per-case pass/fail, not just an aggregate.
    def test_failed_cases_are_recorded_individually(self) -> None:
        exit_code = self.run_recorder(
            "demo-skill",
            "--command",
            self.stub(passed=["alpha"], failed=["beta"]),
            "--per-case-output-dir",
        )

        self.assertEqual(exit_code, 1)
        summary = self.read_only_summary("demo-skill")
        self.assertEqual(summary["cases"], {"alpha": "pass", "beta": "fail"})
        self.assertEqual(summary["totals"]["failed"], 1)
        self.assertEqual(summary["failures"], ["beta: terminal_state mismatch"])

    # AC: results record diffs from the prior recorded run, which is what a
    # before/after pair around a prose change is read from.
    def test_later_run_records_the_diff_from_the_previous_run(self) -> None:
        self.run_recorder(
            "demo-skill",
            "--stage",
            "before",
            "--command",
            self.stub(passed=["alpha"], failed=["beta"]),
            "--per-case-output-dir",
        )
        self.run_recorder(
            "demo-skill",
            "--stage",
            "after",
            "--command",
            self.stub(passed=["beta"], failed=["alpha"]),
            "--per-case-output-dir",
        )

        files = self.results("demo-skill")
        self.assertEqual(len(files), 2)
        before, after = (json.loads(path.read_text(encoding="utf-8")) for path in files)

        self.assertIsNone(before["compared_to"])
        self.assertEqual(after["compared_to"], files[0].name)
        self.assertEqual(after["diff"]["newly_passing"], ["beta"])
        self.assertEqual(after["diff"]["newly_failing"], ["alpha"])

    # AC: an environment without real-model access records the attempt with the
    # limitation instead of silently producing no evidence.
    def test_harness_that_could_not_run_is_recorded_as_an_attempt(self) -> None:
        unavailable = shlex.join([sys.executable, "-c", "import sys; sys.exit(127)"])

        exit_code = self.run_recorder(
            "demo-skill",
            "--command",
            unavailable,
            "--per-case-output-dir",
        )

        self.assertEqual(exit_code, 1)
        summary = self.read_only_summary("demo-skill")
        self.assertEqual(summary["status"], "attempted")
        self.assertIn("not collected", summary["limitation"])

    # A run that happened and went red is evidence of a regression. Recording it
    # as an attempt would file it under "evidence deferred, land anyway".
    def test_failing_run_is_recorded_as_a_failure_not_an_attempt(self) -> None:
        exit_code = self.run_recorder(
            "tested-skill",
            "--command",
            shlex.join([sys.executable, "-c", "import sys; sys.exit(1)"]),
        )

        self.assertEqual(exit_code, 1)
        summary = self.read_only_summary("tested-skill")
        self.assertEqual(summary["status"], "failed")
        self.assertIsNone(summary["limitation"])
        self.assertEqual(summary["exit_code"], 1)
        self.assertTrue(summary["failures"])

    # A diff is only meaningful against a comparable run: same tier, and one
    # that actually produced case outcomes.
    def test_diff_is_not_drawn_against_an_incomparable_run(self) -> None:
        self.run_recorder(
            "demo-skill",
            "--stage",
            "baseline",
            "--command",
            shlex.join([sys.executable, "-c", "import sys; sys.exit(127)"]),
            "--per-case-output-dir",
        )
        self.run_recorder(
            "demo-skill",
            "--stage",
            "before",
            "--tier",
            "deterministic",
            "--command",
            self.stub(passed=["alpha"], failed=[]),
            "--per-case-output-dir",
        )

        deterministic = json.loads(
            self.results("demo-skill")[1].read_text(encoding="utf-8")
        )
        self.assertIsNone(deterministic["compared_to"])

    # The same rule in the other direction: a run that itself measured nothing
    # must not report an all-clear against a prior run that did.
    def test_run_with_no_cases_reports_no_comparison(self) -> None:
        self.run_recorder(
            "demo-skill",
            "--stage",
            "before",
            "--command",
            self.stub(passed=["alpha"], failed=[]),
            "--per-case-output-dir",
        )
        self.run_recorder(
            "demo-skill",
            "--stage",
            "after",
            "--command",
            shlex.join([sys.executable, "-c", "import sys; sys.exit(127)"]),
            "--per-case-output-dir",
        )

        after = json.loads(self.results("demo-skill")[1].read_text(encoding="utf-8"))
        self.assertEqual(after["status"], "attempted")
        self.assertEqual(after["cases"], {})
        self.assertIsNone(after["compared_to"])

    # AC: a skill with no real-model executor records the deterministic tier and
    # notes the gap, rather than presenting a deterministic run as model
    # evidence.
    def test_skill_without_a_real_model_executor_records_the_gap(self) -> None:
        exit_code = self.run_recorder(
            "tested-skill",
            "--command",
            shlex.join([sys.executable, "-c", "print('ok')"]),
        )

        self.assertEqual(exit_code, 0)
        summary = self.read_only_summary("tested-skill")
        self.assertEqual(summary["tier"], "deterministic")
        self.assertFalse(summary["forward_evals"])
        self.assertIn("no model read the prose", summary["gap"])
        self.assertIn("No real-model executor is registered", summary["gap"])

    # A skill with no registered corpus records nothing: substituting its unit
    # tests would commit a summary with no cases, totals, or diff.
    def test_skill_with_no_registered_evals_records_nothing(self) -> None:
        exit_code = self.run_recorder("tested-skill")

        self.assertEqual(exit_code, 2)
        self.assertEqual(self.results("tested-skill"), [])

    def test_real_model_tier_is_refused_where_no_adapter_exists(self) -> None:
        exit_code = self.run_recorder("tested-skill", "--tier", "real-model")

        self.assertEqual(exit_code, 2)
        self.assertEqual(self.results("tested-skill"), [])

    def test_unknown_skill_records_nothing(self) -> None:
        exit_code = self.run_recorder("not-a-skill")

        self.assertEqual(exit_code, 2)
        self.assertFalse((self.skills / "not-a-skill").exists())


class NormIsStatedTests(unittest.TestCase):
    """AC: the norm is written down where a contributor and a PR author read it."""

    def test_agents_md_states_the_norm_and_the_results_convention(self) -> None:
        agents = (REPOSITORY_ROOT / "AGENTS.md").read_text(encoding="utf-8")

        self.assertIn("skills/<skill>/evals/results/", agents)
        self.assertIn("just eval-record", agents)

    def test_pull_request_template_points_at_the_norm(self) -> None:
        template = REPOSITORY_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"

        self.assertTrue(template.is_file(), "PR template is missing")
        self.assertIn("AGENTS.md", template.read_text(encoding="utf-8"))

    def test_implement_tickets_real_model_run_uses_the_claude_executor(self) -> None:
        """AC: the target runs implement-ticket's real-model forward evals."""
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = record_eval_run.main(
                ["implement-ticket", "--tier", "real-model", "--dry-run"]
            )

        self.assertEqual(exit_code, 0)
        resolved = json.loads(stdout.getvalue())
        self.assertEqual(resolved["tier"], "real-model")
        self.assertIsNone(resolved["gap"])
        command = " ".join(resolved["command"])
        self.assertIn("run_forward.py", command)
        self.assertIn("--executor", command)
        self.assertIn("claude_executor.py", command)

    def test_deterministic_only_skill_resolves_without_naming_a_tier(self) -> None:
        """A registry entry with no real-model command still runs, with its gap."""
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = record_eval_run.main(["carve-changesets", "--dry-run"])

        self.assertEqual(exit_code, 0)
        resolved = json.loads(stdout.getvalue())
        self.assertEqual(resolved["tier"], "deterministic")
        self.assertIn("No real-model executor is registered", resolved["gap"])
        self.assertIn("carve-changesets", " ".join(resolved["command"]))

    def test_deterministic_run_states_the_gap_even_where_a_model_tier_exists(
        self,
    ) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            record_eval_run.main(
                ["implement-ticket", "--tier", "deterministic", "--dry-run"]
            )

        resolved = json.loads(stdout.getvalue())
        self.assertEqual(resolved["tier"], "deterministic")
        self.assertIn("no model read the prose", resolved["gap"])
        self.assertNotIn("No real-model executor is registered", resolved["gap"])

    def test_a_previous_summary_does_not_make_the_next_run_look_dirty(self) -> None:
        """Recording several skills in sequence must not report false dirt.

        Each summary is itself a file in the tree, so without the exemption
        only the first run of a batch could ever report a clean worktree.
        """
        status = "?? skills/babysit-pr/evals/results/2026-01-01T000000Z-0001-x.json\n"
        with mock.patch.object(
            record_eval_run.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 0, status, ""),
        ):
            identity = record_eval_run.candidate_identity()

        self.assertTrue(identity["worktree_clean"])

    def test_real_dirt_still_makes_a_run_unclean(self) -> None:
        status = " M scripts/record_eval_run.py\n"
        with mock.patch.object(
            record_eval_run.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 0, status, ""),
        ):
            identity = record_eval_run.candidate_identity()

        self.assertFalse(identity["worktree_clean"])

    def test_just_exposes_the_recorder_as_eval_record(self) -> None:
        justfile = (REPOSITORY_ROOT / "justfile").read_text(encoding="utf-8")

        self.assertIn("eval-record", justfile)
        self.assertIn("scripts/record_eval_run.py", justfile)


if __name__ == "__main__":
    unittest.main()
