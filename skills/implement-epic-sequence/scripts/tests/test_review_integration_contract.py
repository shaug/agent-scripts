from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = SKILL_ROOT.parents[1]
REVIEW_SUITE = REPOSITORY_ROOT / "review-suite"
SPEC = importlib.util.spec_from_file_location(
    "review_contract_validator", REVIEW_SUITE / "scripts" / "validate.py"
)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def load(path: Path):
    return json.loads(path.read_text())


class ReviewIntegrationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = (SKILL_ROOT / "SKILL.md").read_text()
        cls.gates = (
            SKILL_ROOT / "references" / "review-and-merge-gates.md"
        ).read_text()
        cls.github = (SKILL_ROOT / "references" / "github.md").read_text()
        cls.cases = {
            case["id"]: case for case in load(SKILL_ROOT / "evals" / "cases.json")
        }
        cls.results = {
            item["case_id"]: item
            for item in load(SKILL_ROOT / "evals" / "results.json")
        }

    def test_review_suite_is_the_only_local_review_dependency(self):
        combined = self.skill + self.gates
        self.assertNotIn("code-review-pro", combined)
        self.assertIn("single local\nadversarial-review dependency", self.skill)
        self.assertIn("`review-code-change`", self.skill)
        self.assertIn("explicit\nmissing-dependency result", self.skill)
        self.assertIn("Do not substitute another review skill", self.gates)

    def test_epic_skill_owns_mechanics_not_lens_rubrics(self):
        self.assertIn("primary execution context", self.skill)
        self.assertIn("commit, push, build a new", self.skill)
        self.assertIn("without reproducing its lens rubrics or ordering", self.skill)
        self.assertNotIn("Review correctness, acceptance criteria", self.skill)
        self.assertIn("thread remains", self.skill)
        self.assertIn("current-head signal", self.github)

    def test_review_context_is_raw_fresh_and_read_only(self):
        combined = self.skill + self.gates
        self.assertIn("fresh or minimally inherited read-only context", combined)
        self.assertIn("raw ticket, repository", combined)
        self.assertIn("Exclude the implementation transcript", combined)
        self.assertIn("worktree state", self.gates)

    def test_fix_scope_cycles_and_deferred_findings_are_bounded(self):
        self.assertIn("blocking and strong-recommendation findings", self.skill)
        self.assertIn("Preserve deferred findings", self.skill)
        self.assertIn("at most three full fix/re-review cycles", self.skill)
        self.assertIn("Keep the PR open", self.skill)

    def test_base_drift_is_risk_based_without_weakening_remote_gates(self):
        combined = self.skill + self.gates + self.github
        self.assertIn("effective diff", combined)
        self.assertIn("resulting tree are unchanged", combined)
        self.assertIn("no conflict or relevant overlap", combined)
        self.assertIn("repository policy permits retention", combined)
        self.assertIn("rerun every affected gate", combined)
        self.assertIn("required human and connector review", self.skill)
        self.assertIn("zero unresolved connector-authored review threads", self.github)
        self.assertIn("CI success alone is not a clean review", self.gates)

    def test_forward_cases_cover_ticket_scenarios_and_suite_results_conform(self):
        required = {
            "correctness-fix-and-rereview",
            "solution-redesign-early-exit",
            "code-simplicity-targeted-correctness",
            "unrelated-base-drift-retained",
            "relevant-base-drift-restarts-gates",
            "missing-review-dependency",
            "clean-local-review-remote-policy-pending",
        }
        self.assertEqual(required, set(self.cases))
        self.assertEqual(required, set(self.results))
        for case_id, case in self.cases.items():
            with self.subTest(case=case_id):
                self.assertEqual([], VALIDATOR.validate_result(case["suite_result"]))
                if followup := case.get("followup_suite_result"):
                    self.assertEqual([], VALIDATOR.validate_result(followup))

    def test_forward_results_preserve_required_boundaries(self):
        self.assertEqual(
            "blocked", self.results["missing-review-dependency"]["workflow_state"]
        )
        self.assertEqual(
            "merged",
            self.results["unrelated-base-drift-retained"]["workflow_state"],
        )
        self.assertIn(
            "retain head-bound validation and review evidence",
            self.results["unrelated-base-drift-retained"]["observed_actions"],
        )
        self.assertEqual(
            "affected_gates_invalidated",
            self.results["relevant-base-drift-restarts-gates"]["workflow_state"],
        )
        remote = self.results["clean-local-review-remote-policy-pending"]
        self.assertIn("do not merge", remote["observed_actions"])
        targeted = self.results["code-simplicity-targeted-correctness"]
        self.assertIn("run targeted correctness", targeted["observed_actions"])


if __name__ == "__main__":
    unittest.main()
