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

    def test_skill_requires_the_traversal_and_verification_sufficiency_passes(self):
        # #53: the two required passes must be part of this single lens, not
        # a routed specialist module.
        skill = (SKILL_ROOT / "SKILL.md").read_text()
        normalized = " ".join(skill.split())
        self.assertIn("Consumer/impact-traversal pass", normalized)
        self.assertIn("Verification-sufficiency pass", normalized)
        self.assertIn("consumer_impact_evidence", normalized)
        self.assertIn("verification_sufficiency_evidence", normalized)
        self.assertIn("not routed specialist modules", normalized)
        self.assertIn(
            "do not build or delegate to a separate security, "
            "concurrency-as-a-context, compatibility/migration, operations, "
            "or ui module",
            normalized.lower(),
        )

    def test_no_specialist_module_exists(self):
        # #53 acceptance criterion: no specialist module (security,
        # concurrency-as-a-context, migration, operational, or UI) exists
        # anywhere in review-correctness.
        for name in ("specialists", "specialist"):
            self.assertFalse((SKILL_ROOT / name).exists())
            self.assertFalse((SKILL_ROOT / "references" / name).exists())
        for path in SKILL_ROOT.rglob("*"):
            if path.is_dir():
                self.assertNotIn("specialist", path.name.lower(), str(path))

    def test_correctness_fixture_results_conform(self):
        expectations = {
            "behavior-bug": "changes_required",
            "auth-regression": "changes_required",
            "missing-test": "changes_required",
            "repository-convention-clean": "clean",
            "verification-sufficiency-guard": "clean",
        }
        for fixture_name, verdict in expectations.items():
            with self.subTest(fixture=fixture_name):
                fixture = REVIEW_SUITE / "fixtures" / fixture_name
                packet = load(fixture / "packet.json")
                result = load(fixture / "expected.json")
                self.assertEqual([], VALIDATOR.validate_pair(packet, result))
                self.assertEqual("correctness", result["lens"])
                self.assertEqual(verdict, result["verdict"])

    def test_consumer_impact_traversal_fixture_conforms(self):
        # This aggregate-lens fixture (from #52) models the sibling-call-site
        # traversal this lens must now perform; kept separate from the
        # correctness-lens-only expectations above.
        fixture = REVIEW_SUITE / "fixtures" / "consumer-impact-traversal"
        packet = load(fixture / "packet.json")
        result = load(fixture / "expected.json")
        self.assertEqual([], VALIDATOR.validate_pair(packet, result))
        self.assertEqual("aggregate", result["lens"])
        self.assertEqual("clean", result["verdict"])
        self.assertTrue(result["consumer_impact_evidence"])

    def _load_standalone_eval(self, name: str):
        evaluation = SKILL_ROOT / "evals" / name
        prompt = (evaluation / "prompt.md").read_text()
        evidence = "\n".join(
            (evaluation / filename).read_text()
            for filename in (
                "ticket.md",
                "repository-evidence.md",
                "candidate.diff",
                "validation.md",
            )
        )
        result = load(SKILL_ROOT / "evals" / "expected" / f"{name}.result.json")

        # The reviewer-visible input directory must not contain the answer key.
        self.assertEqual(
            [], [path for path in evaluation.glob("*result*") if path.is_file()]
        )
        self.assertNotIn("expected", prompt.lower())
        self.assertNotIn("change_contract", evidence)
        self.assertEqual([], VALIDATOR.validate_result(result))
        return result

    def test_standalone_eval_uses_raw_evidence(self):
        result = self._load_standalone_eval("standalone-ticket-regression")
        self.assertEqual("correctness", result["lens"])
        self.assertEqual("changes_required", result["verdict"])
        self.assertEqual(
            "8484848484848484848484848484848484848484",
            result["candidate"]["head_sha"],
        )
        self.assertTrue(
            any("idempotency" in finding["id"] for finding in result["findings"])
        )

    def test_standalone_sibling_call_site_traversal_finds_the_missed_consumer(self):
        # #53 required fixture 1 (real-runtime shape): a changed shared
        # helper's default tightens while a sibling call site the diff never
        # touches keeps an explicit permissive override.
        result = self._load_standalone_eval("standalone-sibling-call-site-traversal")
        self.assertEqual("correctness", result["lens"])
        self.assertEqual("changes_required", result["verdict"])
        self.assertTrue(
            any(
                "legacy_importer" in finding["id"]
                or "legacy_importer" in finding["location"]
                for finding in result["findings"]
            )
        )
        self.assertTrue(result["consumer_impact_evidence"])
        self.assertEqual(
            "inconsistency_found",
            result["consumer_impact_evidence"][0]["disposition"],
        )

    def test_standalone_verification_sufficiency_gap_is_not_a_silent_clean(self):
        # #53 required fixture 2 (real-runtime shape): the only claimed test
        # exercises the already-safe branch, not the actual owner-absent
        # triggering condition the change addresses.
        result = self._load_standalone_eval("standalone-verification-sufficiency-gap")
        self.assertEqual("correctness", result["lens"])
        self.assertEqual("changes_required", result["verdict"])
        self.assertTrue(result["verification_sufficiency_evidence"])
        self.assertEqual(
            "no",
            result["verification_sufficiency_evidence"][0]["exercises_material_risk"],
        )


if __name__ == "__main__":
    unittest.main()
