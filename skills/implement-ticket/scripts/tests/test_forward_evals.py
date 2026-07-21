from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = SKILL_ROOT / "scripts" / "evals" / "run_forward.py"
EXECUTOR_PATH = SKILL_ROOT / "scripts" / "evals" / "fixture_executor.py"

SPEC = importlib.util.spec_from_file_location("implement_ticket_forward", RUNNER_PATH)
RUNNER = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(RUNNER)


class ForwardEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = json.loads(RUNNER.DEFAULT_CASES.read_text())
        cls.expectations_text = RUNNER.DEFAULT_EXPECTATIONS.read_text()

    def test_every_packet_contains_raw_live_shaped_artifact_categories(self):
        required = {
            "ticket",
            "repository",
            "pr",
            "diff",
            "checks",
            "reviews",
            "threads",
            "worktree",
            "handoff",
        }
        self.assertEqual(18, len(self.cases))
        for case in self.cases:
            self.assertEqual(required, set(case["artifacts"]), case["id"])

    def test_executor_payload_is_result_blind(self):
        for case in self.cases:
            payload = RUNNER.build_payload(case)
            serialized = json.dumps(payload, sort_keys=True)
            self.assertNotIn(case["id"], serialized)
            self.assertNotIn("private_grader_marker", serialized)
            self.assertNotIn("never-send-expectations-to-executor", serialized)
            self.assertNotIn("required_actions", serialized)
            self.assertNotIn("terminal_state", serialized)
            self.assertNotIn(self.expectations_text, serialized)

    def test_forward_cases_execute_fresh_and_pass_separate_grading(self):
        observations, failures = RUNNER.evaluate(
            RUNNER.DEFAULT_CASES,
            RUNNER.DEFAULT_EXPECTATIONS,
            [sys.executable, str(EXECUTOR_PATH)],
        )
        self.assertEqual([], failures)
        self.assertEqual(18, len(observations))
        process_ids = {result["executor_pid"] for result in observations.values()}
        self.assertEqual(18, len(process_ids))

    def test_reference_executor_evaluates_the_supplied_skill_prompt(self):
        payload = RUNNER.build_payload(self.cases[2])
        payload["skill_prompt"] = payload["skill_prompt"].replace(
            "Map `ready PR only` to `ready_to_merge`",
            "",
        )
        observed = RUNNER.run_executor(
            [sys.executable, str(EXECUTOR_PATH)],
            payload,
        )
        self.assertEqual("blocked", observed["terminal_state"])
        self.assertIn("skill_contract_incomplete", observed["actions"])

    def test_required_composition_cases_are_executable(self):
        observations, failures = RUNNER.evaluate(
            RUNNER.DEFAULT_CASES,
            RUNNER.DEFAULT_EXPECTATIONS,
            [sys.executable, str(EXECUTOR_PATH)],
        )
        self.assertEqual([], failures)
        self.assertEqual(
            "requires_epic",
            observations["whole-epic-before-ticket-dependencies"]["terminal_state"],
        )
        self.assertIn(
            "preserve_tracker_pr_host_separation",
            observations["linear-ticket-github-pr"]["actions"],
        )
        self.assertIn(
            "do_not_invoke_babysit_pr_directly",
            observations["implement-epic-consumes-ticket-results"]["actions"],
        )


if __name__ == "__main__":
    unittest.main()
