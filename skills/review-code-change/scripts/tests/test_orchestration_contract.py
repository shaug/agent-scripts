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


class OrchestrationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = (SKILL_ROOT / "SKILL.md").read_text()
        cls.protocol = (
            SKILL_ROOT / "references" / "orchestration-protocol.md"
        ).read_text()
        cls.cases = {
            case["id"]: case for case in load(SKILL_ROOT / "evals" / "cases.json")
        }
        cls.results = {
            record["case_id"]: record
            for record in load(SKILL_ROOT / "evals" / "results.json")
        }

    def test_skill_uses_only_local_lenses_in_default_order(self):
        names = [
            "review-solution-simplicity",
            "review-correctness",
            "review-code-simplicity",
        ]
        positions = [
            self.skill.index(
                f"`{name}`", self.skill.index("Run the deliberate sequence")
            )
            for name in names
        ]
        self.assertEqual(sorted(positions), positions)
        self.assertNotIn("code-review-pro", self.skill + self.protocol)
        self.assertIn("Build the shared packet once", self.skill)
        self.assertIn("implementation transcripts", self.skill)
        self.assertIn("at most three", self.skill)
        self.assertIn("Do not edit", self.skill)

    def test_forward_evaluations_cover_every_case_and_conform(self):
        self.assertEqual(set(self.cases), set(self.results))
        for case_id, record in self.results.items():
            with self.subTest(case=case_id):
                result = record["result"]
                self.assertEqual([], VALIDATOR.validate_result(result))
                self.assertEqual("aggregate", result["lens"])
                self.assertEqual(self.cases[case_id]["candidate"], result["candidate"])

    def test_harness_lens_results_are_valid_and_candidate_bound(self):
        for case_id, case in self.cases.items():
            for expected_lens, result in case["harness_outcomes"].items():
                with self.subTest(case=case_id, lens=expected_lens):
                    self.assertEqual([], VALIDATOR.validate_result(result))
                    if (
                        case_id == "mismatched-lens-result"
                        and expected_lens == "solution_simplicity"
                    ):
                        self.assertNotEqual(expected_lens, result["lens"])
                        self.assertNotEqual(case["candidate"], result["candidate"])
                    else:
                        self.assertEqual(expected_lens, result["lens"])
                        self.assertEqual(case["candidate"], result["candidate"])

    def test_sequence_and_verdict_boundaries(self):
        expected = {
            "ordered-clean": (
                ["solution_simplicity", "correctness", "code_simplicity"],
                "clean",
            ),
            "early-solution-redesign": (["solution_simplicity"], "changes_required"),
            "correctness-overrides-simplification": (
                ["solution_simplicity", "correctness", "code_simplicity"],
                "clean",
            ),
            "deduplicate-overlap": (
                ["solution_simplicity", "correctness", "code_simplicity"],
                "changes_required",
            ),
            "targeted-correctness-recheck": (
                ["code_simplicity", "correctness"],
                "clean",
            ),
            "missing-dependency": ([], "blocked"),
            "missing-evidence": ([], "blocked"),
            "deferred-only-clean": (
                ["solution_simplicity", "correctness", "code_simplicity"],
                "clean",
            ),
            "cycle-budget-exhausted": (
                ["solution_simplicity", "correctness"],
                "changes_required",
            ),
            "mismatched-lens-result": (["solution_simplicity"], "blocked"),
        }
        for case_id, (sequence, verdict) in expected.items():
            with self.subTest(case=case_id):
                record = self.results[case_id]
                self.assertEqual(sequence, record["observed_sequence"])
                self.assertEqual(verdict, record["result"]["verdict"])

    def test_correctness_dispositions_cover_supplied_solution_proposals(self):
        for case_id, case in self.cases.items():
            observed = self.results[case_id]["observed_sequence"]
            solution = case["harness_outcomes"].get("solution_simplicity")
            correctness = case["harness_outcomes"].get("correctness")
            if not solution or "correctness" not in observed:
                continue
            gating_ids = {
                finding["id"]
                for finding in solution["findings"]
                if finding["severity"] in {"blocking", "strong_recommendation"}
            }
            if not gating_ids:
                continue
            with self.subTest(case=case_id):
                disposition_ids = {
                    item["finding_id"]
                    for item in correctness.get("proposal_dispositions", [])
                }
                self.assertEqual(gating_ids, disposition_ids)
                aggregate_ids = {
                    item["finding_id"]
                    for item in self.results[case_id]["result"].get(
                        "proposal_dispositions", []
                    )
                }
                self.assertEqual(gating_ids, aggregate_ids)

    def test_conflict_dedup_deferred_and_budget_semantics(self):
        conflict = self.results["correctness-overrides-simplification"]["result"]
        self.assertEqual([], conflict["findings"])
        self.assertEqual(
            "unsafe",
            conflict["proposal_dispositions"][0]["disposition"],
        )
        self.assertEqual(
            "solution-simplicity.remove-conditional-write",
            conflict["proposal_dispositions"][0]["finding_id"],
        )

        deduplicated = self.results["deduplicate-overlap"]["result"]
        self.assertEqual(1, len(deduplicated["findings"]))
        self.assertIn(
            "code-simplicity.reuse-active-admin",
            deduplicated["findings"][0]["related_finding_ids"],
        )

        deferred = self.results["deferred-only-clean"]["result"]
        self.assertTrue(
            all(item["severity"] == "defer" for item in deferred["findings"])
        )

        exhausted = self.results["cycle-budget-exhausted"]["result"]
        self.assertIn("budget is exhausted", exhausted["next_action"])

    def test_standalone_raw_evidence_builds_one_clean_ordered_review(self):
        evaluation = SKILL_ROOT / "evals" / "standalone-clean"
        prompt = (evaluation / "prompt.md").read_text()
        evidence = "\n".join(
            (evaluation / name).read_text()
            for name in (
                "ticket.md",
                "repository-evidence.md",
                "candidate.diff",
                "validation.md",
            )
        )
        record = load(evaluation / "result.json")

        self.assertNotIn("expected", prompt.lower())
        self.assertNotIn("change_contract", evidence)
        self.assertEqual(
            [
                "review-solution-simplicity",
                "review-correctness",
                "review-code-simplicity",
            ],
            record["observed_sequence"],
        )
        self.assertEqual([], VALIDATOR.validate_result(record["result"]))
        self.assertEqual("clean", record["result"]["verdict"])
        self.assertEqual(
            "1212121212121212121212121212121212121212",
            record["result"]["candidate"]["head_sha"],
        )


if __name__ == "__main__":
    unittest.main()
