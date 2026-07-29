"""Prove `babysit-pr` rejects untrustworthy review-code-change evidence.

The bundled `references/review-suite/validate.py` enforces the shared schema
and cross-field semantics; `scripts/review_gate.py` adds the one caller-side
check the shared contract cannot make on its own — that a result is bound to
*this* run's exact current candidate — and refuses to treat anything else as a
clean, publishable review. These tests exercise the bundled gate directly so a
future schema or gate change cannot silently regress current-head enforcement.
"""

from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]
GATE_PATH = SKILL_ROOT / "scripts" / "review_gate.py"

SPEC = importlib.util.spec_from_file_location("babysit_pr_review_gate", GATE_PATH)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)

HEAD = "1212121212121212121212121212121212121212"
BASE = "abababababababababababababababababababab"

CLEAN_AGGREGATE = {
    "schema_version": "1.3",
    "lens": "aggregate",
    "candidate": {"head_sha": HEAD, "comparison_base_sha": BASE},
    "verdict": "clean",
    "findings": [],
    "blocking_reasons": [],
    "lens_executions": [
        {
            "lens": lens,
            "head_sha": HEAD,
            "comparison_base_sha": BASE,
            "verdict": "clean",
            "freshly_executed": True,
        }
        for lens in ("solution_simplicity", "correctness", "code_simplicity")
    ],
    "validation_limitations": [],
    "next_action": "No changes are required.",
}


class ReviewGateTests(unittest.TestCase):
    def test_current_clean_aggregate_is_accepted(self):
        self.assertEqual([], GATE.evaluate_aggregate(CLEAN_AGGREGATE, HEAD, BASE))

    def test_stale_schema_version_is_rejected_with_migration_action(self):
        stale = copy.deepcopy(CLEAN_AGGREGATE)
        stale["schema_version"] = "1.2"
        errors = GATE.evaluate_aggregate(stale, HEAD, BASE)
        self.assertTrue(errors)
        self.assertTrue(
            any("rebuild review evidence at schema 1.3" in e for e in errors)
        )

    def test_unsupported_future_schema_version_is_rejected(self):
        unknown = copy.deepcopy(CLEAN_AGGREGATE)
        unknown["schema_version"] = "9.9"
        errors = GATE.evaluate_aggregate(unknown, HEAD, BASE)
        self.assertTrue(errors)

    def test_malformed_result_is_rejected(self):
        malformed = copy.deepcopy(CLEAN_AGGREGATE)
        del malformed["findings"]
        errors = GATE.evaluate_aggregate(malformed, HEAD, BASE)
        self.assertTrue(errors)

    def test_blocked_verdict_is_rejected(self):
        blocked = {
            "schema_version": "1.3",
            "lens": "aggregate",
            "candidate": {},
            "verdict": "blocked",
            "findings": [],
            "blocking_reasons": ["review-solution-simplicity is unreadable"],
        }
        errors = GATE.evaluate_aggregate(blocked, HEAD, BASE)
        self.assertTrue(errors)
        self.assertTrue(any("blocked" in e for e in errors))

    def test_changes_required_verdict_is_rejected(self):
        changes_required = copy.deepcopy(CLEAN_AGGREGATE)
        changes_required["verdict"] = "changes_required"
        changes_required["findings"] = [
            {
                "id": "correctness.missing-null-check",
                "lens": "correctness",
                "severity": "blocking",
                "confidence": "high",
                "rule": "demonstrated correctness failure",
                "evidence": [{"location": "a.py:10", "detail": "unchecked None"}],
                "concern": "crash",
                "impact": "500 on empty input",
                "proposed_change": "add a guard",
                "expected_effect": "no crash",
            }
        ]
        errors = GATE.evaluate_aggregate(changes_required, HEAD, BASE)
        self.assertTrue(errors)
        self.assertTrue(any("changes_required" in e for e in errors))

    def test_incomplete_lens_executions_is_rejected(self):
        incomplete = copy.deepcopy(CLEAN_AGGREGATE)
        incomplete["lens_executions"] = [
            execution
            for execution in incomplete["lens_executions"]
            if execution["lens"] != "code_simplicity"
        ]
        errors = GATE.evaluate_aggregate(incomplete, HEAD, BASE)
        self.assertTrue(errors)

    def test_stale_head_lens_execution_is_rejected(self):
        stale_lens = copy.deepcopy(CLEAN_AGGREGATE)
        stale_lens["lens_executions"][0]["head_sha"] = (
            "9999999999999999999999999999999999999999"
        )
        errors = GATE.evaluate_aggregate(stale_lens, HEAD, BASE)
        self.assertTrue(errors)

    def test_result_bound_to_a_different_head_is_rejected(self):
        different_head = copy.deepcopy(CLEAN_AGGREGATE)
        other_head = "3434343434343434343434343434343434343434"
        different_head["candidate"]["head_sha"] = other_head
        for execution in different_head["lens_executions"]:
            execution["head_sha"] = other_head
        errors = GATE.evaluate_aggregate(different_head, HEAD, BASE)
        self.assertTrue(errors)
        self.assertTrue(any("current candidate" in e for e in errors))

    def test_result_bound_to_a_different_base_is_rejected(self):
        different_base = copy.deepcopy(CLEAN_AGGREGATE)
        other_base = "5656565656565656565656565656565656565656"
        different_base["candidate"]["comparison_base_sha"] = other_base
        for execution in different_base["lens_executions"]:
            execution["comparison_base_sha"] = other_base
        errors = GATE.evaluate_aggregate(different_base, HEAD, BASE)
        self.assertTrue(errors)
        self.assertTrue(any("current candidate" in e for e in errors))

    def test_non_aggregate_lens_result_is_rejected(self):
        single_lens = {
            "schema_version": "1.3",
            "lens": "correctness",
            "candidate": {"head_sha": HEAD, "comparison_base_sha": BASE},
            "verdict": "clean",
            "findings": [],
            "blocking_reasons": [],
        }
        errors = GATE.evaluate_aggregate(single_lens, HEAD, BASE)
        self.assertTrue(errors)
        self.assertTrue(any("aggregate" in e for e in errors))

    def test_cli_exits_nonzero_and_prints_errors_for_a_rejected_result(self):
        import json
        import subprocess
        import sys
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result.json"
            blocked = copy.deepcopy(CLEAN_AGGREGATE)
            blocked["schema_version"] = "1.2"
            path.write_text(json.dumps(blocked))
            completed = subprocess.run(
                [
                    sys.executable,
                    str(GATE_PATH),
                    str(path),
                    "--head",
                    HEAD,
                    "--base",
                    BASE,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(1, completed.returncode)
            self.assertIn("schema 1.3", completed.stderr + completed.stdout)

    def test_cli_exits_zero_for_a_current_clean_result(self):
        import json
        import subprocess
        import sys
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result.json"
            path.write_text(json.dumps(CLEAN_AGGREGATE))
            completed = subprocess.run(
                [
                    sys.executable,
                    str(GATE_PATH),
                    str(path),
                    "--head",
                    HEAD,
                    "--base",
                    BASE,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, completed.returncode)


if __name__ == "__main__":
    unittest.main()
