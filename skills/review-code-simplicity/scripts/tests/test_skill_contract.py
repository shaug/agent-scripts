from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = SKILL_ROOT.parents[1]
REVIEW_SUITE = REPOSITORY_ROOT / "review-suite"
# Import the skill's own bundled validator so these tests exercise the
# installed layout, not only the canonical monorepo copy.
SPEC = importlib.util.spec_from_file_location(
    "review_contract_validator",
    SKILL_ROOT / "references" / "review-suite" / "validate.py",
)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def load(path: Path):
    return json.loads(path.read_text())


class SkillContractTests(unittest.TestCase):
    def test_skill_uses_shared_contract_and_is_read_only(self):
        skill = (SKILL_ROOT / "SKILL.md").read_text()
        self.assertIn("references/review-suite/CONTRACT.md", skill)
        self.assertIn("allowed-tools: Read, Grep, Glob, Bash", skill)
        bundle = SKILL_ROOT / "references" / "review-suite"
        for name in (
            "CONTRACT.md",
            "review-packet.schema.json",
            "review-result.schema.json",
            "validate.py",
        ):
            self.assertTrue((bundle / name).is_file(), name)
        self.assertIn("Preserve read-only integrity", skill)
        self.assertIn("From raw evidence", skill)
        self.assertIn("already installed", skill)
        self.assertIn("licensing", skill)
        self.assertNotIn("code-review-pro", skill)

    def test_code_simplicity_fixture_results_conform(self):
        expectations = {
            "duplicated-policy": "changes_required",
            "multi-pass-control-flow": "changes_required",
            "complexity-relocating-wrapper": "changes_required",
            "shared-test-setup": "changes_required",
            "explicit-tests-preserved": "clean",
            "code-simplicity-clean": "clean",
        }
        for fixture_name, verdict in expectations.items():
            with self.subTest(fixture=fixture_name):
                fixture = REVIEW_SUITE / "fixtures" / fixture_name
                packet = load(fixture / "packet.json")
                result = load(fixture / "expected.json")
                self.assertEqual([], VALIDATOR.validate_pair(packet, result))
                self.assertEqual("code_simplicity", result["lens"])
                self.assertEqual(verdict, result["verdict"])

    def test_standalone_eval_finds_repository_reuse_from_raw_evidence(self):
        evaluation = SKILL_ROOT / "evals" / "standalone-duplicated-policy"
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
        result = load(
            SKILL_ROOT
            / "evals"
            / "expected"
            / "standalone-duplicated-policy.result.json"
        )

        # The reviewer-visible input directory must not contain the answer key.
        self.assertEqual(
            [], [path for path in evaluation.glob("*result*") if path.is_file()]
        )
        self.assertNotIn("expected", prompt.lower())
        self.assertNotIn("change_contract", evidence)
        self.assertEqual([], VALIDATOR.validate_result(result))
        self.assertEqual("code_simplicity", result["lens"])
        self.assertEqual("changes_required", result["verdict"])
        self.assertEqual(
            "8d8d8d8d8d8d8d8d8d8d8d8d8d8d8d8d8d8d8d8d",
            result["candidate"]["head_sha"],
        )
        self.assertTrue(
            any(
                "active-admin-policy" in finding["id"] for finding in result["findings"]
            )
        )


if __name__ == "__main__":
    unittest.main()
