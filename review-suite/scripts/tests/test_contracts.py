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

    def test_boolean_const_rejects_numeric_one(self):
        # Python's `1 == True` must not let numeric values satisfy
        # `"const": true`.
        self.packet["candidate"]["diff"]["complete"] = 1
        self.assertIn(
            "$.candidate.diff.complete: expected constant True",
            VALIDATOR.validate_packet(self.packet),
        )

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

    def test_clean_correctness_result_can_reject_an_unsafe_proposal(self):
        result = copy.deepcopy(self.clean)
        result["lens"] = "correctness"
        result["proposal_dispositions"] = [
            {
                "finding_id": "solution-simplicity.remove-claim-fence",
                "source_lens": "solution_simplicity",
                "disposition": "unsafe",
                "reason": "The predicates implement the required claim fence.",
                "evidence": [
                    {
                        "location": "worker.py:complete",
                        "detail": "The token predicate prevents stale completion.",
                    }
                ],
            }
        ]
        self.assertEqual([], VALIDATOR.validate_result(result))

    def test_simplification_lens_cannot_disposition_its_own_proposal(self):
        result = copy.deepcopy(self.clean)
        result["lens"] = "solution_simplicity"
        result["proposal_dispositions"] = [
            {
                "finding_id": "solution-simplicity.remove-claim-fence",
                "source_lens": "solution_simplicity",
                "disposition": "unsafe",
                "reason": "The predicates implement the required claim fence.",
                "evidence": [
                    {
                        "location": "worker.py:complete",
                        "detail": "The token predicate prevents stale completion.",
                    }
                ],
            }
        ]
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


class CleanRequiresPassingValidationTests(unittest.TestCase):
    """#51: a `clean` verdict must prove its own packet validation passed.

    Pair validation previously never cross-checked packet validation status
    against verdict: a schema-valid `clean` result could pair with every
    focused and full validation entry set to `failed`.
    """

    def setUp(self):
        self.packet = load(ROOT / "fixtures" / "clean-change" / "packet.json")
        self.result = load(ROOT / "fixtures" / "clean-change" / "expected.json")

    def _index(self, scope: str) -> int:
        return next(
            index
            for index, validation in enumerate(self.packet["validation"])
            if validation["scope"] == scope
        )

    def test_failed_focused_validation_invalidates_a_clean_pair(self):
        index = self._index("focused")
        self.packet["validation"][index]["status"] = "failed"
        self.packet["validation"][index]["result"] = "1 failed"
        errors = VALIDATOR.validate_pair(self.packet, self.result)
        self.assertTrue(errors)
        self.assertTrue(
            any("clean cannot pair with failed" in error for error in errors)
        )

    def test_failed_full_validation_invalidates_a_clean_pair(self):
        index = self._index("full")
        self.packet["validation"][index]["status"] = "failed"
        self.packet["validation"][index]["result"] = "1 failed"
        errors = VALIDATOR.validate_pair(self.packet, self.result)
        self.assertTrue(errors)
        self.assertTrue(
            any("clean cannot pair with failed" in error for error in errors)
        )

    def test_unavailable_validation_invalidates_a_clean_pair(self):
        index = self._index("full")
        self.packet["validation"][index] = {
            "name": "full tests",
            "command": "pytest",
            "scope": "full",
            "status": "unavailable",
            "reason": "The sandboxed runtime has no network access.",
        }
        errors = VALIDATOR.validate_pair(self.packet, self.result)
        self.assertTrue(errors)
        self.assertTrue(
            any("clean cannot pair with unavailable" in error for error in errors)
        )

    def test_all_required_validation_passed_produces_a_valid_clean_pair(self):
        self.assertEqual([], VALIDATOR.validate_pair(self.packet, self.result))


class AggregateLensExecutionEvidenceTests(unittest.TestCase):
    """#51: aggregate `clean` requires one fresh, current-head lens execution
    for every required lens, so a new-head aggregate cannot smuggle in an
    old-head or missing lens result."""

    def setUp(self):
        self.result = load(ROOT / "fixtures" / "clean-change" / "expected.json")

    def test_missing_required_lens_execution_invalidates_clean_aggregate(self):
        self.result["lens_executions"] = [
            execution
            for execution in self.result["lens_executions"]
            if execution["lens"] != "solution_simplicity"
        ]
        errors = VALIDATOR.validate_result(self.result)
        self.assertTrue(errors)
        self.assertTrue(
            any("missing required lens execution" in error for error in errors)
        )

    def test_duplicate_required_lens_execution_invalidates_clean_aggregate(self):
        self.result["lens_executions"].append(
            copy.deepcopy(self.result["lens_executions"][0])
        )
        errors = VALIDATOR.validate_result(self.result)
        self.assertTrue(errors)
        self.assertTrue(any("duplicate lens execution" in error for error in errors))

    def test_stale_head_lens_execution_invalidates_clean_aggregate(self):
        self.result["lens_executions"][0]["head_sha"] = "9" * 40
        errors = VALIDATOR.validate_result(self.result)
        self.assertTrue(errors)
        self.assertTrue(any("stale head or base" in error for error in errors))

    def test_stale_base_lens_execution_invalidates_clean_aggregate(self):
        self.result["lens_executions"][0]["comparison_base_sha"] = "9" * 40
        errors = VALIDATOR.validate_result(self.result)
        self.assertTrue(errors)
        self.assertTrue(any("stale head or base" in error for error in errors))

    def test_fresh_current_head_clean_executions_produce_a_valid_clean_aggregate(self):
        self.assertEqual([], VALIDATOR.validate_result(self.result))


class NewHeadFullRestartTests(unittest.TestCase):
    """#51 items 8-9: any head-changing fix restarts the full three-lens
    sequence. The pre-#51 re-review matrix let a correctness fix or a
    code-simplicity fix reach a new-head aggregate with only two of the three
    required lenses re-executed; both must now fail validation."""

    def setUp(self):
        self.result = load(ROOT / "fixtures" / "clean-change" / "expected.json")

    def _drop_solution_simplicity(self):
        self.result["lens_executions"] = [
            execution
            for execution in self.result["lens_executions"]
            if execution["lens"] != "solution_simplicity"
        ]

    def test_new_head_after_correctness_fix_requires_all_three_executions(self):
        # Pre-#51 matrix: "correctness fix -> correctness and downstream
        # lenses", which never re-ran solution simplicity on the new head.
        self._drop_solution_simplicity()
        errors = VALIDATOR.validate_result(self.result)
        self.assertTrue(errors)
        self.assertTrue(any("solution_simplicity" in error for error in errors))

    def test_new_head_after_code_simplicity_fix_requires_all_three_executions(self):
        # Pre-#51 matrix: "code-simplicity fix -> code, then targeted
        # correctness", which never re-ran solution simplicity on the new head.
        self._drop_solution_simplicity()
        errors = VALIDATOR.validate_result(self.result)
        self.assertTrue(errors)
        self.assertTrue(any("solution_simplicity" in error for error in errors))


class UnchangedHeadBaseDriftRegressionTest(unittest.TestCase):
    """#51 item 10: unchanged-head base drift keeps the existing retain rules,
    unaffected by the validation and lens-execution repairs above."""

    def test_unrelated_base_drift_remains_a_valid_clean_pair_at_v1_1(self):
        packet = load(ROOT / "fixtures" / "unrelated-base-drift" / "packet.json")
        result = load(ROOT / "fixtures" / "unrelated-base-drift" / "expected.json")
        self.assertEqual("retain", packet["base_drift"]["decision"])
        self.assertEqual([], VALIDATOR.validate_pair(packet, result))


class StaleSchemaVersionTests(unittest.TestCase):
    """#51 item 11 and #52 item 5: a stale result is rejected with a useful
    error rather than silently reinterpreted as newer evidence. Extended by
    #52 to also reject a stale v1.1 aggregate now that schema 1.2 exists, and
    by #53 to reject a stale v1.2 aggregate now that schema 1.3 exists."""

    def test_stale_v1_0_aggregate_result_is_rejected_with_a_useful_error(self):
        result = load(ROOT / "fixtures" / "clean-change" / "expected.json")
        result["schema_version"] = "1.0"
        errors = VALIDATOR.validate_result(result)
        self.assertTrue(errors)
        self.assertTrue(any("stale v1.0" in error for error in errors))
        self.assertTrue(any("1.1" in error for error in errors))

    def test_stale_v1_1_aggregate_result_is_rejected_with_a_useful_error(self):
        result = load(ROOT / "fixtures" / "clean-change" / "expected.json")
        result["schema_version"] = "1.1"
        errors = VALIDATOR.validate_result(result)
        self.assertTrue(errors)
        self.assertTrue(any("stale v1.1" in error for error in errors))
        self.assertTrue(any("1.2" in error for error in errors))

    def test_stale_v1_2_aggregate_result_is_rejected_with_a_useful_error(self):
        result = load(ROOT / "fixtures" / "clean-change" / "expected.json")
        result["schema_version"] = "1.2"
        errors = VALIDATOR.validate_result(result)
        self.assertTrue(errors)
        self.assertTrue(any("stale v1.2" in error for error in errors))
        self.assertTrue(any("1.3" in error for error in errors))


class ConsumerImpactEvidenceTests(unittest.TestCase):
    """#52: `consumer_impact_evidence` records a reviewer's traversal to other
    call sites/consumers of a changed shared symbol, making that traversal
    machine-checkable instead of an unenforced expectation a reviewer can
    silently skip. The validator enforces structure and non-emptiness; it does
    not determine which changed symbols require an entry (that is lens
    judgment, owned by a later child)."""

    def setUp(self):
        self.packet = load(
            ROOT / "fixtures" / "consumer-impact-traversal" / "packet.json"
        )
        self.result = load(
            ROOT / "fixtures" / "consumer-impact-traversal" / "expected.json"
        )

    def test_sibling_call_site_correctly_identified_and_inspected_is_valid_clean(
        self,
    ):
        # Required fixture 1: a changed shared symbol with a sibling call
        # site, correctly identified and inspected in
        # `consumer_impact_evidence`.
        self.assertEqual([], VALIDATOR.validate_pair(self.packet, self.result))

    def test_disposition_naming_only_the_hardened_call_site_is_rejected(self):
        # Required fixture 2: the same fixture, but with the evidence entry
        # naming only the hardened call site while still claiming the
        # consumers are consistent. `all_consumers_consistent` describes at
        # least one other consumer by definition, so it requires evidence
        # covering more than the changed symbol's own location.
        entry = self.result["consumer_impact_evidence"][0]
        entry["consumer_search_evidence"] = entry["consumer_search_evidence"][:1]
        errors = VALIDATOR.validate_result(self.result)
        self.assertTrue(errors)
        self.assertTrue(
            any("claims other consumers were found" in error for error in errors)
        )

    def test_single_consumer_with_concrete_search_evidence_is_valid_clean(self):
        # Required fixture 3: a changed symbol genuinely used from exactly one
        # call site, with concrete search evidence showing no other
        # consumers, disposition `no_other_consumers`.
        self.result["consumer_impact_evidence"] = [
            self.result["consumer_impact_evidence"][1]
        ]
        self.assertEqual([], VALIDATOR.validate_result(self.result))

    def test_no_other_consumers_without_search_evidence_is_rejected(self):
        # Required fixture 4: a changed symbol with disposition
        # `no_other_consumers` but no search evidence.
        self.result["consumer_impact_evidence"][1]["consumer_search_evidence"] = []
        errors = VALIDATOR.validate_result(self.result)
        self.assertTrue(errors)
        self.assertTrue(any("expected at least 1 item" in error for error in errors))

    def test_an_omitted_evidence_array_is_a_lens_judgment_gap_not_a_schema_gap(
        self,
    ):
        # This is a deliberate boundary, not an oversight: #52's own text
        # ("the validator enforces structure and non-emptiness; lens judgment
        # determines which changed symbols require an entry") and non-goals
        # ("Add independent correctness explorers or finding validators";
        # "Implement a complete static call graph ... or mandatory AST
        # tooling") both rule out having this validator inspect the packet's
        # diff to decide whether a changed symbol needed an entry. This
        # validator receives only a packet and a result — no repository
        # checkout to search — so it structurally cannot make that
        # determination; the real baseline miss this evidence exists to
        # surface involved a sibling call site the diff never touched, which
        # only live repository access (available to the reviewing agent, not
        # to this validator) can find. An aggregate `clean` result that omits
        # `consumer_impact_evidence` entirely therefore remains schema-valid;
        # whether a given traversal was actually complete is judged by
        # forward-testing the populating lens's real output against a
        # fixture's expected result, exactly as this contract family already
        # judges every other lens-specific finding (a duplicated-policy or
        # behavior-bug miss is likewise never something this validator can
        # detect unaided).
        del self.result["consumer_impact_evidence"]
        self.assertEqual([], VALIDATOR.validate_result(self.result))

    def test_only_correctness_or_aggregate_results_may_include_the_evidence(self):
        self.result["lens"] = "code_simplicity"
        for finding in self.result.get("findings", []):
            finding["lens"] = "code_simplicity"
        errors = VALIDATOR.validate_result(self.result)
        self.assertTrue(errors)
        self.assertTrue(
            any("only correctness or aggregate results" in error for error in errors)
        )


class VerificationSufficiencyEvidenceTests(unittest.TestCase):
    """#53: `verification_sufficiency_evidence` records whether a claimed test
    or command actually exercises the specific triggering condition a change
    addresses, not merely whether it passes. Modeled on a baseline
    verification-sufficiency miss, where the added test exercised an
    already-safe branch (a present, matching owner) instead of the actual risk
    (an absent snapshot owner paired with a not-yet-expired claim)."""

    def setUp(self):
        self.packet = load(
            ROOT / "fixtures" / "verification-sufficiency-guard" / "packet.json"
        )
        self.result = load(
            ROOT / "fixtures" / "verification-sufficiency-guard" / "expected.json"
        )

    def test_test_exercising_the_triggering_condition_is_valid_clean(self):
        # Required fixture: the claimed test sets the snapshot owner absent
        # and the claim unexpired -- the actual triggering condition -- and
        # `verification_sufficiency_evidence` records `exercises_material_risk:
        # yes`.
        self.assertEqual([], VALIDATOR.validate_pair(self.packet, self.result))

    def test_no_risk_exercised_cannot_pair_with_a_silent_clean(self):
        # Required fixture: the same guard clause, but the claimed test only
        # exercises the already-safe owned-entry branch, so
        # `verification_sufficiency_evidence` correctly records
        # `exercises_material_risk: no`. That fact must gate the verdict, not
        # disappear into a silent `clean`.
        entry = self.result["verification_sufficiency_evidence"][0]
        entry["claimed_test_or_command"] = (
            "tests/test_claims.py::test_release_denied_for_mismatched_owner"
        )
        entry["exercises_material_risk"] = "no"
        entry["reasoning"] = (
            "Only sets a mismatched present owner; no test sets the snapshot "
            "owner absent, so the new `owner is None and not "
            "claim.is_expired()` guard clause is never exercised."
        )
        errors = VALIDATOR.validate_result(self.result)
        self.assertTrue(errors)
        self.assertTrue(
            any(
                "exercises_material_risk 'no' contradicts a clean verdict" in error
                for error in errors
            )
        )

    def test_no_risk_exercised_is_valid_as_a_gating_finding(self):
        # The same unexercised-risk evidence is valid once paired with a
        # gating verdict and finding, proving the rule targets the silent
        # `clean`, not the evidence shape itself.
        entry = self.result["verification_sufficiency_evidence"][0]
        entry["claimed_test_or_command"] = (
            "tests/test_claims.py::test_release_denied_for_mismatched_owner"
        )
        entry["exercises_material_risk"] = "no"
        entry["reasoning"] = (
            "Only sets a mismatched present owner; no test sets the snapshot "
            "owner absent, so the new `owner is None and not "
            "claim.is_expired()` guard clause is never exercised."
        )
        self.result["verdict"] = "changes_required"
        self.result["findings"] = [
            {
                "id": "correctness.claim-release-guard-unverified",
                "lens": "correctness",
                "severity": "blocking",
                "confidence": "high",
                "rule": "A claimed test covering a materially risky change must exercise the actual triggering condition it addresses.",
                "evidence": [
                    {
                        "location": "lib/claims.py:5",
                        "detail": "The new guard clause only applies when `owner is None`, but no test constructs a snapshot with an absent owner.",
                    }
                ],
                "concern": "The added test exercises the pre-existing owner-mismatch branch, not the new owner-absent interleaving.",
                "impact": "A claim could be released while its snapshot owner is transiently absent and the claim has not expired, with no test proving the guard denies it.",
                "proposed_change": "Add a test that sets the snapshot owner absent and the claim unexpired, and assert release_if_stale still denies release.",
                "expected_effect": "The guard clause addressing the owner-absent interleaving is proven by a test that actually exercises it.",
                "location": "lib/claims.py:5",
            }
        ]
        self.assertEqual([], VALIDATOR.validate_pair(self.packet, self.result))

    def test_not_applicable_risk_may_pair_with_clean(self):
        entry = self.result["verification_sufficiency_evidence"][0]
        entry["exercises_material_risk"] = "not_applicable"
        entry["reasoning"] = (
            "This claimed command does not touch the materially risky branch."
        )
        self.assertEqual([], VALIDATOR.validate_result(self.result))

    def test_an_omitted_evidence_array_is_a_lens_judgment_gap_not_a_schema_gap(self):
        del self.result["verification_sufficiency_evidence"]
        self.assertEqual([], VALIDATOR.validate_result(self.result))

    def test_only_correctness_or_aggregate_results_may_include_the_evidence(self):
        self.result["lens"] = "code_simplicity"
        errors = VALIDATOR.validate_result(self.result)
        self.assertTrue(errors)
        self.assertTrue(
            any(
                "only correctness or aggregate results may include "
                "verification-sufficiency evidence" in error
                for error in errors
            )
        )


if __name__ == "__main__":
    unittest.main()
