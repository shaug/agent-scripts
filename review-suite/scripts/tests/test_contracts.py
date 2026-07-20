from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "review_contract_validator", ROOT / "scripts" / "validate.py"
)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def load(path: Path):
    return json.loads(path.read_text())


def candidate_identity(packet):
    return {
        field: packet["candidate"][field]
        for field in ("head_sha", "comparison_base_sha")
        if field in packet["candidate"]
    }


class FixtureTests(unittest.TestCase):
    def test_fixture_packets_and_expected_results(self):
        manifest = load(ROOT / "fixtures" / "manifest.json")
        self.assertGreaterEqual(len(manifest), 6)
        for entry in manifest:
            with self.subTest(entry=entry["name"]):
                fixture = ROOT / "fixtures" / entry["name"]
                packet = load(fixture / "packet.json")
                result = load(fixture / "expected.json")
                packet_errors = VALIDATOR.validate_packet(packet)
                if entry["packet_valid"]:
                    self.assertEqual([], packet_errors)
                else:
                    self.assertTrue(packet_errors)
                    self.assertEqual("blocked", result["verdict"])
                self.assertEqual([], VALIDATOR.validate_result(result))

    def test_expected_outcomes_are_not_in_forward_test_prompt(self):
        prompt = (ROOT / "fixtures" / "PROMPT.md").read_text().lower()
        self.assertNotIn("behavior-bug", prompt)
        self.assertNotIn("changes_required", prompt)
        self.assertNotIn("strong_recommendation", prompt)

    def test_unrelated_base_drift_is_accepted(self):
        packet = load(ROOT / "fixtures" / "unrelated-base-drift" / "packet.json")
        self.assertEqual([], VALIDATOR.validate_packet(packet))

    def test_every_fixture_diff_is_a_parseable_patch(self):
        manifest = load(ROOT / "fixtures" / "manifest.json")
        for entry in manifest:
            with self.subTest(entry=entry["name"]):
                packet = load(ROOT / "fixtures" / entry["name"] / "packet.json")
                completed = subprocess.run(
                    ["git", "apply", "--numstat"],
                    input=packet["candidate"]["diff"]["content"],
                    capture_output=True,
                    check=False,
                    text=True,
                )
                self.assertEqual(0, completed.returncode, completed.stderr)


class PacketValidationTests(unittest.TestCase):
    def setUp(self):
        self.packet = load(ROOT / "fixtures" / "clean-change" / "packet.json")

    def test_missing_required_field_is_rejected(self):
        del self.packet["change_contract"]["acceptance_criteria"]
        self.assertTrue(VALIDATOR.validate_packet(self.packet))

    def test_unknown_enum_is_rejected(self):
        self.packet["validation"][0]["status"] = "skipped"
        self.assertTrue(VALIDATOR.validate_packet(self.packet))

    def test_unavailable_validation_requires_reason(self):
        self.packet["validation"][0] = {
            "name": "tests",
            "command": "pytest",
            "scope": "full",
            "status": "unavailable",
        }
        self.assertIn(
            "$.validation[0]: unavailable requires reason",
            VALIDATOR.validate_packet(self.packet),
        )

    def test_retain_rejects_active_base_drift_invalidator(self):
        drift_packet = load(ROOT / "fixtures" / "unrelated-base-drift" / "packet.json")
        drift_packet["base_drift"]["relevant_overlap"] = True
        self.assertTrue(VALIDATOR.validate_packet(drift_packet))

    def test_focused_and_full_validation_are_required(self):
        self.packet["validation"] = [self.packet["validation"][0]]
        self.assertIn(
            "$.validation: missing full validation",
            VALIDATOR.validate_packet(self.packet),
        )

    def test_malformed_validation_item_returns_errors(self):
        self.packet["validation"] = ["pytest"]
        self.assertTrue(VALIDATOR.validate_packet(self.packet))


class ResultValidationTests(unittest.TestCase):
    def setUp(self):
        self.clean = load(ROOT / "fixtures" / "clean-change" / "expected.json")
        self.gating = load(ROOT / "fixtures" / "behavior-bug" / "expected.json")

    def test_clean_with_gating_finding_is_rejected(self):
        result = copy.deepcopy(self.gating)
        result["verdict"] = "clean"
        self.assertTrue(VALIDATOR.validate_result(result))

    def test_changes_required_without_gating_finding_is_rejected(self):
        result = copy.deepcopy(self.clean)
        result["verdict"] = "changes_required"
        self.assertTrue(VALIDATOR.validate_result(result))

    def test_blocked_without_reason_is_rejected(self):
        result = copy.deepcopy(self.clean)
        result["verdict"] = "blocked"
        self.assertTrue(VALIDATOR.validate_result(result))

    def test_deferred_only_clean_result_is_accepted(self):
        result = copy.deepcopy(self.clean)
        result["findings"] = [
            {
                "id": "code-simplicity.existing-duplication",
                "lens": "code_simplicity",
                "severity": "defer",
                "confidence": "high",
                "rule": "The active ticket does not own the existing parser duplication.",
                "evidence": [
                    {
                        "location": "legacy_parser.py:10",
                        "detail": "The duplicated parser predates and is untouched by the candidate.",
                    }
                ],
                "concern": "An existing parser is duplicated outside the changed code.",
                "impact": "The duplication is real but not caused by this ticket.",
                "proposed_change": "Address the existing duplication separately.",
                "expected_effect": "Preserve active scope while recording evidenced follow-up work.",
            }
        ]
        self.assertEqual([], VALIDATOR.validate_result(result))

    def test_unknown_finding_enum_is_rejected(self):
        result = copy.deepcopy(self.gating)
        result["findings"][0]["confidence"] = "certain"
        self.assertTrue(VALIDATOR.validate_result(result))

    def test_result_must_match_packet_candidate(self):
        packet = load(ROOT / "fixtures" / "clean-change" / "packet.json")
        result = copy.deepcopy(self.clean)
        result["candidate"]["head_sha"] = "9999999999999999999999999999999999999999"
        errors = VALIDATOR.validate_pair(packet, result)
        self.assertIn("candidate.head_sha: result does not match packet", errors)

    def test_blocked_result_can_omit_missing_candidate_identity(self):
        packet = load(ROOT / "fixtures" / "missing-evidence" / "packet.json")
        del packet["candidate"]["head_sha"]
        result = load(ROOT / "fixtures" / "missing-evidence" / "expected.json")
        del result["candidate"]["head_sha"]
        self.assertEqual([], VALIDATOR.validate_pair(packet, result))

    def test_blocked_pair_rejects_unknown_packet_enum(self):
        packet = load(ROOT / "fixtures" / "clean-change" / "packet.json")
        packet["validation"][0]["status"] = "skipped"
        result = load(ROOT / "fixtures" / "missing-evidence" / "expected.json")
        result["candidate"] = candidate_identity(packet)
        self.assertTrue(VALIDATOR.validate_pair(packet, result))

    def test_blocked_pair_rejects_unknown_packet_property(self):
        packet = load(ROOT / "fixtures" / "clean-change" / "packet.json")
        packet["unexpected"] = True
        result = load(ROOT / "fixtures" / "missing-evidence" / "expected.json")
        result["candidate"] = candidate_identity(packet)
        self.assertTrue(VALIDATOR.validate_pair(packet, result))

    def test_blocked_pair_accepts_missing_exact_validation_result(self):
        packet = load(ROOT / "fixtures" / "clean-change" / "packet.json")
        del packet["validation"][0]["result"]
        result = load(ROOT / "fixtures" / "missing-evidence" / "expected.json")
        result["candidate"] = candidate_identity(packet)
        self.assertEqual([], VALIDATOR.validate_pair(packet, result))

    def test_blocked_result_cannot_invent_missing_identity(self):
        packet = load(ROOT / "fixtures" / "missing-evidence" / "packet.json")
        del packet["candidate"]["head_sha"]
        result = load(ROOT / "fixtures" / "missing-evidence" / "expected.json")
        errors = VALIDATOR.validate_pair(packet, result)
        self.assertIn(
            "candidate.head_sha: result invents identity absent from packet", errors
        )

    def test_merge_verdict_requires_complete_candidate_identity(self):
        result = copy.deepcopy(self.clean)
        del result["candidate"]["head_sha"]
        self.assertTrue(VALIDATOR.validate_result(result))

    def test_malformed_finding_returns_errors(self):
        result = copy.deepcopy(self.clean)
        result["findings"] = ["not-a-finding"]
        self.assertTrue(VALIDATOR.validate_result(result))

    def test_malformed_pair_candidate_returns_errors(self):
        packet = load(ROOT / "fixtures" / "clean-change" / "packet.json")
        result = copy.deepcopy(self.clean)
        result["candidate"] = None
        self.assertTrue(VALIDATOR.validate_pair(packet, result))


if __name__ == "__main__":
    unittest.main()
