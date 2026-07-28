from __future__ import annotations

import copy
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

FIXTURE_SPEC = importlib.util.spec_from_file_location(
    "implement_ticket_fixture_executor", EXECUTOR_PATH
)
FIXTURE_EXECUTOR = importlib.util.module_from_spec(FIXTURE_SPEC)
assert FIXTURE_SPEC and FIXTURE_SPEC.loader
FIXTURE_SPEC.loader.exec_module(FIXTURE_EXECUTOR)

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
        self.assertEqual(48, len(self.cases))
        for case in self.cases:
            self.assertEqual(required, set(case["artifacts"]), case["id"])

    def test_acceptance_packets_separate_requirements_from_raw_observations(self):
        acceptance_cases = [
            case
            for case in self.cases
            if "acceptance_requirements" in case["artifacts"]["ticket"]
        ]
        self.assertGreaterEqual(len(acceptance_cases), 15)
        for case in acceptance_cases:
            requirements = case["artifacts"]["ticket"]["acceptance_requirements"]
            observations = case["artifacts"]["handoff"].get(
                "acceptance_observations", []
            )
            with self.subTest(case=case["id"]):
                self.assertTrue(requirements)
                self.assertTrue(all("status" not in item for item in requirements))
                self.assertTrue(all("status" not in item for item in observations))
                self.assertTrue(all("outcome" not in item for item in requirements))
                self.assertTrue(all(item.get("source") for item in requirements))

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

    def test_reference_executor_actions_fit_real_runtime_vocabulary(self):
        emitted_actions = {
            action
            for case in self.cases
            for action in FIXTURE_EXECUTOR.action_result(RUNNER.build_payload(case))[
                "actions"
            ]
        }
        emitted_actions.add("skill_contract_incomplete")
        self.assertEqual(
            set(),
            emitted_actions - set(CLAUDE_EXECUTOR.ACTION_VOCABULARY),
        )

    def test_forward_cases_execute_fresh_and_pass_separate_grading(self):
        observations, failures = RUNNER.evaluate(
            RUNNER.DEFAULT_CASES,
            RUNNER.DEFAULT_EXPECTATIONS,
            [sys.executable, str(EXECUTOR_PATH)],
        )
        self.assertEqual([], failures)
        self.assertEqual(48, len(observations))
        process_ids = {result["executor_pid"] for result in observations.values()}
        self.assertEqual(48, len(process_ids))

    def test_reference_executor_evaluates_the_supplied_skill_prompt(self):
        payload = RUNNER.build_payload(self.cases[2])
        payload["skill_prompt"] = payload["skill_prompt"].replace("`ready_prs`", "")
        observed = RUNNER.run_executor(
            [sys.executable, str(EXECUTOR_PATH)],
            payload,
        )
        self.assertEqual("blocked", observed["terminal_state"])
        self.assertIn("skill_contract_incomplete", observed["actions"])

    def test_acceptance_cases_depend_on_the_acceptance_skill_contract(self):
        for case_id, fragment in (
            (
                "functional-browser-missing-visual-layout",
                "Build the acceptance evidence ledger",
            ),
            (
                "epic-closed-children-missing-manual-browser",
                "every required child's criterion-specific acceptance ledger",
            ),
        ):
            case = next(item for item in self.cases if item["id"] == case_id)
            payload = RUNNER.build_payload(case)
            payload["skill_prompt"] = payload["skill_prompt"].replace(fragment, "")
            observed = RUNNER.run_executor(
                [sys.executable, str(EXECUTOR_PATH)], payload
            )
            with self.subTest(case=case_id):
                self.assertEqual("blocked", observed["terminal_state"])
                self.assertEqual([], observed["acceptance_ledger"])
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
        self.assertIn(
            "name_missing_carve_changesets",
            observations["missing-carve-changesets"]["actions"],
        )
        self.assertIn(
            "reject_stale_or_malformed_result",
            observations["stale-carved-result"]["actions"],
        )

    def test_acceptance_cases_fail_closed_or_complete_from_raw_evidence(self):
        observations, failures = RUNNER.evaluate(
            RUNNER.DEFAULT_CASES,
            RUNNER.DEFAULT_EXPECTATIONS,
            [sys.executable, str(EXECUTOR_PATH)],
        )
        self.assertEqual([], failures)
        for case_id in (
            "epic-closed-children-missing-manual-browser",
            "auto-closed-missing-postmerge-deployment",
            "authenticated-deployed-browser-unavailable",
            "functional-browser-missing-visual-layout",
            "merge-without-deploy-or-close-authority",
            "reopened-epic-correction-without-journey-revalidation",
            "stale-acceptance-evidence",
            "epic-auto-closed-child-incomplete",
            "prior-unrelated-deployment-evidence",
            "wrong-source-acceptance-evidence",
            "deployment-requirement-rejects-candidate-fallback",
            "epic-refreshes-after-blocked-merged-delivery",
        ):
            self.assertEqual("blocked", observations[case_id]["terminal_state"])
        self.assertEqual(
            "merged", observations["all-acceptance-current"]["terminal_state"]
        )
        self.assertEqual(
            "merged", observations["backend-only-no-ui-gates"]["terminal_state"]
        )
        self.assertIn(
            "avoid_irrelevant_ui_gates",
            observations["backend-only-no-ui-gates"]["actions"],
        )
        self.assertIn(
            "require_visual_layout_evidence",
            observations["functional-browser-missing-visual-layout"]["actions"],
        )
        self.assertIn(
            "select_auto_closed_incomplete_child",
            observations["epic-auto-closed-child-incomplete"]["actions"],
        )
        self.assertIn(
            "invoke_implement_ticket_for_recovery",
            observations["epic-auto-closed-child-incomplete"]["actions"],
        )
        self.assertEqual(
            "fail",
            observations["wrong-source-acceptance-evidence"]["acceptance_ledger"][0][
                "status"
            ],
        )
        deployment_fallback = observations[
            "deployment-requirement-rejects-candidate-fallback"
        ]
        self.assertEqual(
            "deployment", deployment_fallback["acceptance_ledger"][0]["identity"]
        )
        self.assertIn(
            "reject_stale_acceptance_evidence", deployment_fallback["actions"]
        )
        self.assertIn(
            "refresh_graph_after_verified_delivery",
            observations["epic-refreshes-after-blocked-merged-delivery"]["actions"],
        )

    def test_reference_executor_rejects_null_pass_identity(self):
        case = copy.deepcopy(
            next(item for item in self.cases if item["id"] == "all-acceptance-current")
        )
        post_merge = next(
            entry
            for entry in case["artifacts"]["handoff"]["acceptance_observations"]
            if entry["stage"] == "post_merge"
        )
        post_merge["deployed_sha"] = None
        observed = RUNNER.run_executor(
            [sys.executable, str(EXECUTOR_PATH)], RUNNER.build_payload(case)
        )
        self.assertEqual("blocked", observed["terminal_state"])
        self.assertIn("reject_missing_required_acceptance", observed["actions"])
        self.assertEqual("fail", observed["acceptance_ledger"][-1]["status"])

    def test_reference_executor_accepts_candidate_bound_postmerge_identity(self):
        case = copy.deepcopy(
            next(item for item in self.cases if item["id"] == "all-acceptance-current")
        )
        requirement = next(
            entry
            for entry in case["artifacts"]["ticket"]["acceptance_requirements"]
            if entry["stage"] == "post_merge"
        )
        observation = next(
            entry
            for entry in case["artifacts"]["handoff"]["acceptance_observations"]
            if entry["stage"] == "post_merge"
        )
        requirement["identity"] = "candidate"
        observation["candidate_sha"] = case["artifacts"]["pr"]["head"]
        observation["deployed_sha"] = None
        case["artifacts"]["handoff"]["current_deployed_sha"] = None

        observed = RUNNER.run_executor(
            [sys.executable, str(EXECUTOR_PATH)], RUNNER.build_payload(case)
        )

        self.assertEqual("merged", observed["terminal_state"])
        self.assertNotIn("reject_stale_acceptance_evidence", observed["actions"])
        self.assertEqual("pass", observed["acceptance_ledger"][-1]["status"])

    def test_target_skill_filter_runs_only_epic_cases(self):
        observations, failures = RUNNER.evaluate(
            RUNNER.DEFAULT_CASES,
            RUNNER.DEFAULT_EXPECTATIONS,
            [sys.executable, str(EXECUTOR_PATH)],
            target_skill="implement-epic",
        )
        self.assertEqual([], failures)
        self.assertEqual(13, len(observations))
        self.assertTrue(
            all(
                result["target_skill"] == "implement-epic"
                for result in observations.values()
            )
        )

    def test_epic_dependency_boundary_executes_before_child_selection(self):
        observations, failures = RUNNER.evaluate(
            RUNNER.DEFAULT_CASES,
            RUNNER.DEFAULT_EXPECTATIONS,
            [sys.executable, str(EXECUTOR_PATH)],
            target_skill="implement-epic",
        )
        self.assertEqual([], failures)
        positive = observations["epic-compatible-installed-implement-ticket"]
        self.assertEqual("mixed_ticket_results", positive["terminal_state"])
        self.assertIn("select_ready_child", positive["actions"])
        self.assertIn("invoke_installed_implement_ticket", positive["actions"])

        negative_ids = (
            "epic-missing-implement-ticket",
            "epic-third-party-implement-ticket",
            "epic-incompatible-implement-ticket",
            "epic-runtime-download-offer",
            "epic-unverifiable-implement-ticket",
            "epic-unreadable-implement-ticket",
        )
        for case_id in negative_ids:
            with self.subTest(case=case_id):
                result = observations[case_id]
                self.assertEqual("blocked", result["terminal_state"])
                self.assertIn(
                    "perform_no_child_selection_or_mutation", result["actions"]
                )
                self.assertNotIn("select_ready_child", result["actions"])
                self.assertNotIn("invoke_installed_implement_ticket", result["actions"])

        child_work_actions = {
            "select_ready_child",
            "invoke_installed_implement_ticket",
            "select_auto_closed_incomplete_child",
            "invoke_implement_ticket_for_recovery",
        }
        for case_id, result in observations.items():
            if child_work_actions.isdisjoint(result["actions"]):
                continue
            with self.subTest(case=case_id):
                self.assertIn(
                    "verify_installed_implement_ticket_dependency", result["actions"]
                )
                self.assertIn("bind_installed_implement_ticket", result["actions"])

    def test_epic_dependency_grading_rejects_unbound_or_failed_child_work(self):
        expectations = {
            item["case_id"]: item for item in json.loads(self.expectations_text)
        }
        cases = {item["id"]: item for item in self.cases}

        recovery_case = cases["epic-auto-closed-child-incomplete"]
        unbound_recovery = FIXTURE_EXECUTOR.action_result(
            RUNNER.build_payload(recovery_case)
        )
        unbound_recovery["actions"] = [
            action
            for action in unbound_recovery["actions"]
            if action
            not in {
                "verify_installed_implement_ticket_dependency",
                "bind_installed_implement_ticket",
            }
        ]
        recovery_failures = RUNNER.grade(
            recovery_case["id"],
            unbound_recovery,
            expectations[recovery_case["id"]],
        )
        self.assertTrue(
            any("missing actions" in failure for failure in recovery_failures)
        )

        failed_case = cases["epic-missing-implement-ticket"]
        failed_with_child_work = FIXTURE_EXECUTOR.action_result(
            RUNNER.build_payload(failed_case)
        )
        failed_with_child_work["actions"].extend(
            [
                "select_auto_closed_incomplete_child",
                "invoke_implement_ticket_for_recovery",
            ]
        )
        failed_dependency_failures = RUNNER.grade(
            failed_case["id"],
            failed_with_child_work,
            expectations[failed_case["id"]],
        )
        self.assertTrue(
            any(
                "forbidden actions" in failure for failure in failed_dependency_failures
            )
        )


if __name__ == "__main__":
    unittest.main()
