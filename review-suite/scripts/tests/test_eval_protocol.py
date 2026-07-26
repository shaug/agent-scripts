"""Protocol and contamination tests for the review replay evaluator."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from evals import corpus, protocol, runner  # noqa: E402


def build_request(case, **overrides):
    kwargs = {
        "case_id": case.case_id,
        "target_skill": "review-code-change",
        "skill_prompt": runner.target_skill_prompt("review-code-change"),
        "contract_documents": runner.contract_documents(),
        "instructions": case.instructions,
        "packet": case.packet,
        "run_number": 1,
        "suite_commit": "0" * 40,
        "corpus_version": "test",
        "started_at": "2026-07-26T00:00:00+00:00",
    }
    kwargs.update(overrides)
    return protocol.build_request(**kwargs)


class RequestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = corpus.load_corpus()
        cls.case = cls.corpus.cases[0]

    def test_request_matches_its_schema(self):
        request = build_request(self.case)
        self.assertEqual(
            [], protocol.validate_against("executor-request.schema.json", request)
        )

    def test_request_records_suite_candidate_and_run_identity(self):
        request = build_request(self.case, run_number=3, suite_commit="a" * 40)
        self.assertEqual(3, request["run"]["run_number"])
        self.assertEqual("a" * 40, request["run"]["suite_commit"])
        self.assertEqual(
            {
                "head_sha": self.case.packet["candidate"]["head_sha"],
                "comparison_base_sha": self.case.packet["candidate"][
                    "comparison_base_sha"
                ],
            },
            request["run"]["candidate"],
        )
        self.assertEqual(
            protocol.prompt_digest(request["skill_prompt"]),
            request["target_skill_digest"],
        )

    def test_case_reference_is_opaque(self):
        request = build_request(self.case)
        self.assertNotEqual(self.case.case_id, request["run"]["case_ref"])
        self.assertRegex(request["run"]["case_ref"], r"^c-[0-9a-f]{8}$")

    def test_packet_without_complete_identity_is_refused(self):
        packet = copy.deepcopy(self.case.packet)
        del packet["candidate"]["head_sha"]
        with self.assertRaises(ValueError):
            build_request(self.case, packet=packet)


class ContaminationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = corpus.load_corpus()

    def test_every_corpus_request_is_blind(self):
        for case in self.corpus.cases:
            with self.subTest(case=case.case_id):
                request = build_request(case)
                self.assertEqual(
                    [],
                    protocol.audit_request(
                        request,
                        case_id=case.case_id,
                        expectation=case.expectation,
                        provenance=case.provenance,
                    ),
                )

    def _case_with_root_causes(self):
        for case in self.corpus.cases:
            if case.expectation["material_root_causes"]:
                return case
        raise AssertionError("no corpus case declares a material root cause")

    def test_injected_expectation_object_is_rejected(self):
        case = self._case_with_root_causes()
        request = build_request(case)
        request["expectation"] = case.expectation
        errors = protocol.audit_request(
            request,
            case_id=case.case_id,
            expectation=case.expectation,
            provenance=case.provenance,
        )
        self.assertTrue(any("unpermitted key" in error for error in errors))

    def test_injected_root_cause_text_is_rejected(self):
        case = self._case_with_root_causes()
        root_cause = case.expectation["material_root_causes"][0]
        for field in ("id", "consequence", "trigger"):
            with self.subTest(field=field):
                request = build_request(case)
                request["instructions"] += f"\nHint: {root_cause[field]}\n"
                errors = protocol.audit_request(
                    request,
                    case_id=case.case_id,
                    expectation=case.expectation,
                    provenance=case.provenance,
                )
                self.assertTrue(
                    any("private expectation text" in error for error in errors),
                    errors,
                )

    def test_injected_accepted_non_finding_text_is_rejected(self):
        case = next(
            item
            for item in self.corpus.cases
            if item.expectation["accepted_non_findings"]
        )
        non_finding = case.expectation["accepted_non_findings"][0]
        request = build_request(case)
        request["instructions"] += "\n" + non_finding["description"]
        errors = protocol.audit_request(
            request,
            case_id=case.case_id,
            expectation=case.expectation,
            provenance=case.provenance,
        )
        self.assertTrue(any("private expectation text" in error for error in errors))

    def test_injected_provenance_text_is_rejected(self):
        case = self.corpus.cases[0]
        request = build_request(case)
        request["instructions"] += "\n" + case.provenance["retention_authority"]
        errors = protocol.audit_request(
            request,
            case_id=case.case_id,
            expectation=case.expectation,
            provenance=case.provenance,
        )
        self.assertTrue(any("private expectation text" in error for error in errors))

    def test_leaked_case_identifier_is_rejected(self):
        case = self.corpus.cases[0]
        request = build_request(case)
        request["run"]["case_ref"] = case.case_id
        errors = protocol.audit_request(
            request,
            case_id=case.case_id,
            expectation=case.expectation,
            provenance=case.provenance,
        )
        self.assertTrue(
            any("case_ref exposes the case identifier" in e for e in errors)
        )

    def test_audit_inspects_nested_payload_text(self):
        """A leak buried inside the packet must be caught, not just top level."""
        case = self._case_with_root_causes()
        request = build_request(case)
        request["packet"] = copy.deepcopy(case.packet)
        request["packet"]["change_contract"]["non_goals"].append(
            case.expectation["material_root_causes"][0]["consequence"]
        )
        errors = protocol.audit_request(
            request,
            case_id=case.case_id,
            expectation=case.expectation,
            provenance=case.provenance,
        )
        self.assertTrue(any("private expectation text" in error for error in errors))


class ResponseClassificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = corpus.load_corpus()
        cls.case = next(
            item
            for item in cls.corpus.cases
            if item.expectation["packet_valid"]
            and item.expectation["material_root_causes"]
        )

    def _valid_response(self, verdict="changes_required"):
        candidate = {
            "head_sha": self.case.packet["candidate"]["head_sha"],
            "comparison_base_sha": self.case.packet["candidate"]["comparison_base_sha"],
        }
        finding = {
            "id": "correctness.example",
            "lens": "correctness",
            "severity": "blocking",
            "confidence": "high",
            "rule": "A stated requirement is not met.",
            "evidence": [{"location": "example.py:1", "detail": "Demonstrated."}],
            "concern": "The requirement is not met.",
            "impact": "Users see the wrong result.",
            "proposed_change": "Meet the requirement.",
            "expected_effect": "The requirement is met.",
        }
        return {
            "protocol_version": protocol.PROTOCOL_VERSION,
            "outcome": "review_result",
            "simulation": False,
            "executor": {"name": "test"},
            "result": {
                "schema_version": "1.0",
                "lens": "aggregate",
                "candidate": candidate,
                "verdict": verdict,
                "findings": [finding] if verdict == "changes_required" else [],
                "blocking_reasons": [],
            },
        }

    def classify(self, response):
        return protocol.classify_response(self.case.packet, json.dumps(response))

    def test_valid_review_result(self):
        status, _, detail = self.classify(self._valid_response())
        self.assertEqual(("review_result", ""), (status, detail))

    def test_non_json_output_is_malformed(self):
        status, response, _ = protocol.classify_response(self.case.packet, "nope")
        self.assertEqual("malformed_output", status)
        self.assertIsNone(response)

    def test_non_object_output_is_malformed(self):
        status, _, _ = protocol.classify_response(self.case.packet, "[1, 2]")
        self.assertEqual("malformed_output", status)

    def test_protocol_version_mismatch_is_reported_separately(self):
        response = self._valid_response()
        response["protocol_version"] = "0.9"
        status, _, _ = self.classify(response)
        self.assertEqual("protocol_mismatch", status)

    def test_unknown_response_key_is_malformed(self):
        response = self._valid_response()
        response["expectation"] = {"expected_verdict": "clean"}
        status, _, _ = self.classify(response)
        self.assertEqual("malformed_output", status)

    def test_runtime_failure_requires_a_reason(self):
        response = self._valid_response()
        response["outcome"] = "runtime_failure"
        del response["result"]
        status, _, _ = self.classify(response)
        self.assertEqual("malformed_output", status)

        response["failure"] = {"reason": "the runtime died"}
        status, _, detail = self.classify(response)
        self.assertEqual(("runtime_failure", "the runtime died"), (status, detail))

    def test_blocked_outcome_requires_a_blocked_verdict(self):
        response = self._valid_response()
        response["outcome"] = "blocked"
        status, _, _ = self.classify(response)
        self.assertEqual("malformed_output", status)

    def test_review_result_cannot_carry_a_blocked_verdict(self):
        response = self._valid_response()
        response["result"]["verdict"] = "blocked"
        status, _, _ = self.classify(response)
        self.assertEqual("malformed_output", status)

    def test_valid_blocked_result_is_its_own_status(self):
        blocked_case = next(
            item
            for item in self.corpus.cases
            if item.expectation["expected_verdict"] == "blocked"
        )
        response = {
            "protocol_version": protocol.PROTOCOL_VERSION,
            "outcome": "blocked",
            "simulation": False,
            "executor": {"name": "test"},
            "result": {
                "schema_version": "1.0",
                "lens": "aggregate",
                "candidate": {
                    "head_sha": blocked_case.packet["candidate"]["head_sha"],
                    "comparison_base_sha": blocked_case.packet["candidate"][
                        "comparison_base_sha"
                    ],
                },
                "verdict": "blocked",
                "findings": [],
                "blocking_reasons": ["Required validation evidence is absent."],
            },
        }
        status, _, detail = protocol.classify_response(
            blocked_case.packet, json.dumps(response)
        )
        self.assertEqual(("blocked", ""), (status, detail))

    def test_result_bound_to_another_candidate_is_malformed(self):
        response = self._valid_response()
        response["result"]["candidate"]["head_sha"] = "9" * 40
        status, _, detail = self.classify(response)
        self.assertEqual("malformed_output", status)
        self.assertIn("head_sha", detail)

    def test_schema_invalid_review_result_is_malformed_not_a_finding_miss(self):
        response = self._valid_response()
        del response["result"]["findings"][0]["impact"]
        status, _, _ = self.classify(response)
        self.assertEqual("malformed_output", status)

    def test_non_numeric_usage_is_malformed(self):
        response = self._valid_response()
        response["usage"] = {"cost_usd": "free"}
        status, _, detail = self.classify(response)
        self.assertEqual("malformed_output", status)
        self.assertIn("usage", detail)

    def test_failure_statuses_are_disjoint_from_gradable_statuses(self):
        self.assertEqual(
            set(),
            set(protocol.EVALUATION_FAILURE_STATUSES) & set(protocol.GRADABLE_STATUSES),
        )
        self.assertEqual(
            set(protocol.ATTEMPT_STATUSES),
            set(protocol.EVALUATION_FAILURE_STATUSES)
            | set(protocol.GRADABLE_STATUSES)
            | {"blocked"},
        )


if __name__ == "__main__":
    unittest.main()
