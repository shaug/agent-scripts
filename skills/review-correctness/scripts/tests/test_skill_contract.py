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
        self.assertIn("proposal_dispositions", skill)
        self.assertIn("Do not turn a rejected hypothetical edit", skill)
        self.assertNotIn("code-review-pro", skill)

    def test_correctness_fixture_results_conform(self):
        expectations = {
            "behavior-bug": "changes_required",
            "auth-regression": "changes_required",
            "missing-test": "changes_required",
            "repository-convention-clean": "clean",
        }
        for fixture_name, verdict in expectations.items():
            with self.subTest(fixture=fixture_name):
                fixture = REVIEW_SUITE / "fixtures" / fixture_name
                packet = load(fixture / "packet.json")
                result = load(fixture / "expected.json")
                self.assertEqual([], VALIDATOR.validate_pair(packet, result))
                self.assertEqual("correctness", result["lens"])
                self.assertEqual(verdict, result["verdict"])

    def test_standalone_eval_uses_raw_evidence(self):
        evaluation = SKILL_ROOT / "evals" / "standalone-ticket-regression"
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
            / "standalone-ticket-regression.result.json"
        )

        # The reviewer-visible input directory must not contain the answer key.
        self.assertEqual(
            [], [path for path in evaluation.glob("*result*") if path.is_file()]
        )
        self.assertNotIn("expected", prompt.lower())
        self.assertNotIn("change_contract", evidence)
        self.assertEqual([], VALIDATOR.validate_result(result))
        self.assertEqual("correctness", result["lens"])
        self.assertEqual("changes_required", result["verdict"])
        self.assertEqual(
            "8484848484848484848484848484848484848484",
            result["candidate"]["head_sha"],
        )
        self.assertTrue(
            any("idempotency" in finding["id"] for finding in result["findings"])
        )


if __name__ == "__main__":
    unittest.main()
