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

CLAUDE_EXECUTOR_PATH = SKILL_ROOT / "scripts" / "evals" / "claude_executor.py"
CLAUDE_SPEC = importlib.util.spec_from_file_location(
    "implement_ticket_claude_executor", CLAUDE_EXECUTOR_PATH
)
CLAUDE_EXECUTOR = importlib.util.module_from_spec(CLAUDE_SPEC)
assert CLAUDE_SPEC and CLAUDE_SPEC.loader
CLAUDE_SPEC.loader.exec_module(CLAUDE_EXECUTOR)


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
        self.assertEqual(23, len(self.cases))
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
        self.assertEqual(23, len(observations))
        process_ids = {result["executor_pid"] for result in observations.values()}
        self.assertEqual(23, len(process_ids))

    def test_reference_executor_evaluates_the_supplied_skill_prompt(self):
        payload = RUNNER.build_payload(self.cases[2])
        payload["skill_prompt"] = payload["skill_prompt"].replace("`ready_prs`", "")
        observed = RUNNER.run_executor(
            [sys.executable, str(EXECUTOR_PATH)],
            payload,
        )
        self.assertEqual("blocked", observed["terminal_state"])
        self.assertIn("skill_contract_incomplete", observed["actions"])

    def test_vocabulary_spam_fails_every_case(self):
        """An executor emitting the whole action vocabulary must never pass.

        This forces every expectation record to keep at least one
        forbidden action, so the anti-gaming defense stays complete as
        cases are added.
        """
        expectations = json.loads(self.expectations_text)
        vocabulary = sorted(CLAUDE_EXECUTOR.ACTION_VOCABULARY)
        for expected in expectations:
            spam = {
                "target_skill": expected["target_skill"],
                "terminal_state": expected["terminal_state"],
                "actions": vocabulary,
            }
            with self.subTest(case=expected["case_id"]):
                failures = RUNNER.grade(expected["case_id"], spam, expected)
                self.assertTrue(
                    any("forbidden actions" in failure for failure in failures),
                    f"{expected['case_id']} has no forbidden_actions teeth",
                )

    def test_claude_executor_reports_model_claims_verbatim(self):
        normalized = CLAUDE_EXECUTOR.normalize(
            {"target_skill": "implement-ticket"},
            {"terminal_state": "ready_pr", "actions": ["invoke_ready_to_merge"]},
        )
        # No backfill: a model that omits target_skill must fail grading.
        self.assertIsNone(normalized["target_skill"])

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
        self.assertEqual(
            "ready_prs",
            observations["oversized-authorized-carved-stack"]["terminal_state"],
        )
        self.assertIn(
            "route_to_tracker_split",
            observations["oversized-ticket-split-rubric"]["actions"],
        )
        self.assertIn(
            "verify_full_stack_on_base",
            observations["implement-epic-verifies-stacked-child"]["actions"],
        )


if __name__ == "__main__":
    unittest.main()
