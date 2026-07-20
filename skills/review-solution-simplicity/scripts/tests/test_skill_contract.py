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


class SkillContractTests(unittest.TestCase):
    def test_skill_uses_shared_contract_and_is_read_only(self):
        skill = (SKILL_ROOT / "SKILL.md").read_text()
        self.assertIn("../../review-suite/CONTRACT.md", skill)
        self.assertIn("Preserve read-only integrity", skill)
        self.assertIn("From raw evidence", skill)
        self.assertNotIn("code-review-pro", skill)

    def test_solution_simplicity_fixture_results_conform(self):
        expectations = {
            "imagined-machinery": "changes_required",
            "necessary-complexity": "clean",
            "speculative-backfill": "changes_required",
            "missing-simplification-requirements": "blocked",
        }
        for fixture_name, verdict in expectations.items():
            with self.subTest(fixture=fixture_name):
                fixture = REVIEW_SUITE / "fixtures" / fixture_name
                packet = load(fixture / "packet.json")
                result = load(fixture / "expected.json")
                self.assertEqual([], VALIDATOR.validate_pair(packet, result))
                self.assertEqual("solution_simplicity", result["lens"])
                self.assertEqual(verdict, result["verdict"])

    def test_standalone_eval_reconstructs_contract_from_raw_evidence(self):
        evaluation = SKILL_ROOT / "evals" / "standalone-provider-framework"
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
        result = load(evaluation / "result.json")

        self.assertNotIn("expected", prompt.lower())
        self.assertNotIn("change_contract", evidence)
        self.assertEqual([], VALIDATOR.validate_result(result))
        self.assertEqual("solution_simplicity", result["lens"])
        self.assertEqual("changes_required", result["verdict"])
        self.assertEqual(
            "8787878787878787878787878787878787878787",
            result["candidate"]["head_sha"],
        )
        self.assertTrue(
            any("provider-framework" in finding["id"] for finding in result["findings"])
        )


if __name__ == "__main__":
    unittest.main()
