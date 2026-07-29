"""Tests for re-grading already-captured raw attempts without re-running them."""

from __future__ import annotations

import json
import shlex
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from evals import grader, protocol, regrade, runner  # noqa: E402

FIXTURE_EXECUTOR = SCRIPTS_DIR / "evals" / "fixture_executor.py"


def fixture_command(mode: str | None = None) -> str:
    command = f"{sys.executable} {FIXTURE_EXECUTOR}"
    return f"{command} --mode {mode}" if mode else command


class RegradeTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp, ignore_errors=True)
        self.artifact_dir = self.temp / "artifacts"
        self.attempts_path = self.temp / "attempts.jsonl"

        attempts, _ = runner.evaluate(
            shlex.split(fixture_command()),
            corpus_root=None,
            runs=1,
            timeout=60.0,
            max_output_bytes=runner.DEFAULT_MAX_OUTPUT_BYTES,
            artifact_dir=self.artifact_dir,
        )
        self.source_attempts = attempts
        self.attempts_path.write_text(
            "".join(json.dumps(a, sort_keys=True) + "\n" for a in attempts)
        )

    def test_regrading_reproduces_the_original_grade(self):
        """No executor ran; every gradable attempt's grade is rebuilt from the
        retained raw artifact, and must land on exactly what a fresh
        `grader.grade` call on that same artifact produces."""
        regraded, _loaded = regrade.regrade_attempts(
            corpus_root=None,
            attempts_in=self.attempts_path,
            artifact_dir=self.artifact_dir,
        )
        self.assertEqual(len(self.source_attempts), len(regraded))
        gradable = [
            a for a in self.source_attempts if a["status"] in protocol.GRADABLE_STATUSES
        ]
        self.assertTrue(gradable, "fixture executor produced no gradable attempt")
        for original, rebuilt in zip(
            (
                a
                for a in self.source_attempts
                if a["status"] in protocol.GRADABLE_STATUSES
            ),
            (a for a in regraded if a["status"] in protocol.GRADABLE_STATUSES),
        ):
            self.assertEqual(original["case_id"], rebuilt["case_id"])
            self.assertEqual(original["run_number"], rebuilt["run_number"])
            self.assertIsNotNone(rebuilt["grade"])
            self.assertEqual(grader.GRADER_VERSION, rebuilt["grade"]["grader_version"])

    def test_non_gradable_attempts_are_carried_over_untouched(self):
        """A blocked or failed attempt has no raw result to re-grade from, so
        its `grade` (already `None`) must not be touched or looked up."""
        regraded, _loaded = regrade.regrade_attempts(
            corpus_root=None,
            attempts_in=self.attempts_path,
            artifact_dir=self.artifact_dir,
        )
        for attempt in regraded:
            if attempt["status"] not in protocol.GRADABLE_STATUSES:
                self.assertIsNone(attempt["grade"])

    def test_a_case_id_absent_from_the_given_corpus_is_rejected(self):
        """Regrading against the wrong corpus must fail loudly, not silently
        skip or mis-grade a case it cannot find an expectation for."""
        tampered = self.temp / "tampered.jsonl"
        lines = self.attempts_path.read_text().splitlines()
        attempt = json.loads(lines[0])
        attempt["case_id"] = "no-such-case"
        lines[0] = json.dumps(attempt, sort_keys=True)
        tampered.write_text("\n".join(lines) + "\n")

        with self.assertRaises(regrade.RegradeError):
            regrade.regrade_attempts(
                corpus_root=None,
                attempts_in=tampered,
                artifact_dir=self.artifact_dir,
            )

    def test_a_missing_retained_artifact_is_rejected(self):
        """Regrading depends entirely on the raw artifact still being on disk;
        a gradable attempt whose file was never retained (or was cleaned up)
        must fail rather than silently produce no grade."""
        empty_dir = self.temp / "empty-artifacts"
        empty_dir.mkdir()
        with self.assertRaises(regrade.RegradeError):
            regrade.regrade_attempts(
                corpus_root=None,
                attempts_in=self.attempts_path,
                artifact_dir=empty_dir,
            )

    def test_regrade_report_marks_itself_as_regraded(self):
        """The produced report must be self-describing: a reader must never
        mistake a re-graded report for a fresh execution's report."""
        regraded, loaded = regrade.regrade_attempts(
            corpus_root=None,
            attempts_in=self.attempts_path,
            artifact_dir=self.artifact_dir,
        )
        configuration = regrade._configuration(
            regraded,
            loaded,
            attempts_in=self.attempts_path,
            artifact_dir=self.artifact_dir,
        )
        self.assertTrue(configuration["regraded"])
        self.assertEqual(
            grader.GRADER_VERSION, configuration["regraded_grader_version"]
        )


if __name__ == "__main__":
    unittest.main()
