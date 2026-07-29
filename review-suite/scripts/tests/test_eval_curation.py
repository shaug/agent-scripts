"""Curation-record and promotion-decision contract tests for #56.

Covers the intake schema, disposition vocabulary, duplicate/unresolved
handling, provenance/retention fields, reviewer/private separation, the
mechanical disclosure guardrail, and promotion-decision evidence and target
rules - all against synthetic fixtures only. None of this data resembles or
is derived from any real private source.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from evals import audit_curation, curation  # noqa: E402

INVALID_DIR = curation.INVALID_FIXTURES
AUDIT_SCRIPT = SCRIPTS_DIR / "evals" / "audit_curation.py"


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


class RecordSetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record_set = curation.load_records()

    def test_the_shipped_records_load_and_cover_every_disposition_family(self):
        dispositions = {
            record["disposition"] for record in self.record_set.records.values()
        }
        self.assertIn("accepted_material_defect", dispositions)
        self.assertIn("accepted_acceptance_miss", dispositions)
        self.assertIn("rejected_false_positive", dispositions)
        self.assertIn("duplicate", dispositions)
        self.assertIn("unresolved", dispositions)

    def test_a_duplicate_declares_the_record_it_restates(self):
        duplicate = self.record_set.records["webhook-retry-duplicate-claim"]
        self.assertEqual("retry-jitter-defect", duplicate["duplicate_of"])
        self.assertNotIn("distinct_contribution", duplicate)

    def test_a_distinct_duplicate_declares_its_contribution(self):
        duplicate = self.record_set.records["retry-jitter-duplicate-with-new-surface"]
        self.assertEqual("retry-jitter-defect", duplicate["duplicate_of"])
        self.assertTrue(duplicate["distinct_contribution"])


class RecordSchemaAndSemanticsTests(unittest.TestCase):
    def setUp(self):
        self.record = _load(
            curation.DEFAULT_RECORDS / "stale-config-schema-defect.json"
        )

    def test_a_valid_record_has_no_errors(self):
        self.assertEqual([], curation.validate_record(self.record))

    def test_an_unknown_disposition_fails_schema(self):
        self.record["disposition"] = "probably_fine"
        errors = curation.validate_record(self.record)
        self.assertTrue(any("disposition" in error for error in errors))

    def test_duplicate_without_duplicate_of_fails(self):
        self.record["disposition"] = "duplicate"
        del self.record["private"]["expected_root_cause"]
        errors = curation.validate_record(self.record)
        self.assertTrue(any("duplicate_of" in error for error in errors))

    def test_duplicate_of_on_a_non_duplicate_disposition_fails(self):
        self.record["duplicate_of"] = "some-other-record"
        errors = curation.validate_record(self.record)
        self.assertTrue(
            any("only valid when disposition is duplicate" in error for error in errors)
        )

    def test_accepted_disposition_without_expected_root_cause_fails(self):
        del self.record["private"]["expected_root_cause"]
        errors = curation.validate_record(self.record)
        self.assertTrue(any("expected_root_cause" in error for error in errors))

    def test_rejected_disposition_without_accepted_non_finding_fails(self):
        self.record["disposition"] = "rejected_false_positive"
        errors = curation.validate_record(self.record)
        self.assertTrue(any("accepted_non_finding" in error for error in errors))

    def test_unresolved_disposition_with_a_private_root_cause_fails(self):
        self.record["disposition"] = "unresolved"
        errors = curation.validate_record(self.record)
        self.assertTrue(
            any("must not declare a private root cause" in error for error in errors)
        )

    def test_private_text_echoed_into_the_public_section_fails(self):
        leak = self.record["private"]["expected_root_cause"]
        self.record["public"]["adjudication_evidence"] = leak
        errors = curation.validate_record(self.record)
        self.assertTrue(
            any("appears verbatim in the public section" in error for error in errors)
        )


class DisclosureGuardrailTests(unittest.TestCase):
    """The one piece of code #56 exists to guarantee is real and fails closed."""

    def test_the_allow_listed_phrase_passes(self):
        record = _load(curation.DEFAULT_RECORDS / "stale-config-schema-defect.json")
        self.assertEqual([], curation.disclosure_guardrail_errors(record))

    def test_non_private_authorized_records_are_not_checked(self):
        record = _load(curation.DEFAULT_RECORDS / "retry-jitter-defect.json")
        record["public"]["provenance"]["source_description"] = (
            "path/like/but/irrelevant"
        )
        self.assertEqual([], curation.disclosure_guardrail_errors(record))

    def test_a_disallowed_generic_phrase_fails_even_without_a_leak_shape(self):
        record = _load(curation.DEFAULT_RECORDS / "stale-config-schema-defect.json")
        record["public"]["provenance"]["source_description"] = (
            "our usual connector feed"
        )
        errors = curation.disclosure_guardrail_errors(record)
        self.assertTrue(any("allow-listed" in error for error in errors))

    def test_path_like_token_fails_closed(self):
        record = _load(INVALID_DIR / "disclosure-path-token.json")
        errors = curation.disclosure_guardrail_errors(record)
        self.assertTrue(any("path-like token" in error for error in errors))

    def test_bare_hostname_fails_closed(self):
        record = _load(INVALID_DIR / "disclosure-bare-hostname.json")
        errors = curation.disclosure_guardrail_errors(record)
        self.assertTrue(any("hostname" in error for error in errors))

    def test_denylisted_identifier_fails_closed(self):
        record = _load(INVALID_DIR / "disclosure-denylisted-identifier.json")
        # The shipped default deny-list is empty by design; this test supplies
        # its own synthetic, clearly-fictional entry to prove the mechanism
        # without the shipped config ever naming anything real.
        guardrail = curation.load_guardrail_config()
        guardrail = {
            **guardrail,
            "denylisted_identifiers": ["widgetcorp-shadow-connector-history"],
        }
        errors = curation.disclosure_guardrail_errors(record, guardrail=guardrail)
        self.assertTrue(any("deny-listed identifier" in error for error in errors))

    def test_the_shipped_denylist_is_empty_by_default(self):
        guardrail = curation.load_guardrail_config()
        self.assertEqual([], guardrail["denylisted_identifiers"])

    def test_record_load_rejects_every_disclosure_fixture(self):
        for name in (
            "disclosure-path-token",
            "disclosure-bare-hostname",
            "disclosure-denylisted-identifier",
        ):
            with self.subTest(fixture=name):
                record = _load(INVALID_DIR / f"{name}.json")
                self.assertTrue(curation.validate_record(record))


class RestrictedDataTests(unittest.TestCase):
    def test_a_forbidden_field_fails_closed_as_an_unknown_property(self):
        record = _load(INVALID_DIR / "restricted-data-forbidden-field.json")
        errors = curation.validate_record(record)
        self.assertTrue(any("unknown property" in error for error in errors))


class PromotionDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = curation.load_records().records

    def _promotion(self, name: str) -> dict:
        return _load(curation.DEFAULT_PROMOTIONS / f"{name}.json")

    def test_every_shipped_promotion_decision_validates_cleanly(self):
        for path in sorted(curation.DEFAULT_PROMOTIONS.glob("*.json")):
            with self.subTest(promotion=path.name):
                document = _load(path)
                self.assertEqual(
                    [], curation.validate_promotion_decision(document, self.records)
                )

    def test_an_unresolved_record_cannot_be_promoted(self):
        document = self._promotion("no-promotion-example")
        document["positive_case_ids"] = ["unpatched-token-scope-claim"]
        errors = curation.validate_promotion_decision(document, self.records)
        self.assertTrue(
            any("unresolved claims cannot enter" in error for error in errors)
        )

    def test_a_plain_duplicate_cannot_be_promoted(self):
        document = self._promotion("no-promotion-example")
        document["negative_control_case_ids"] = ["webhook-retry-duplicate-claim"]
        errors = curation.validate_promotion_decision(document, self.records)
        self.assertTrue(
            any("double-counting its root cause" in error for error in errors)
        )

    def test_a_distinct_duplicate_may_be_promoted(self):
        document = self._promotion("corpus-case-only-example")
        self.assertEqual(
            [], curation.validate_promotion_decision(document, self.records)
        )

    def test_a_distinct_duplicate_of_an_accepted_record_cannot_be_a_negative_control(
        self,
    ):
        """A duplicate's promotion role must match what it actually duplicates.

        `retry-jitter-duplicate-with-new-surface` duplicates
        `retry-jitter-defect`, whose disposition is `accepted_acceptance_miss`.
        Restating an accepted defect on a second surface is still evidence the
        defect was accepted, never evidence it was rejected, so it must not be
        usable as a negative control even though it declares a distinct
        contribution.
        """
        document = self._promotion("no-promotion-example")
        document["negative_control_case_ids"] = [
            "retry-jitter-duplicate-with-new-surface"
        ]
        errors = curation.validate_promotion_decision(document, self.records)
        self.assertTrue(
            any("cannot support a negative control" in error for error in errors)
        )

    def test_a_distinct_duplicate_of_a_rejected_record_cannot_be_a_positive_case(self):
        """The symmetric case: a duplicate of a rejected false positive.

        `cache-ttl-duplicate-with-new-surface` duplicates
        `cache-ttl-false-positive` (`rejected_false_positive`) on a distinct
        surface. It must not be usable as a positive case even with a distinct
        contribution declared, or a rejected non-finding could feed a global
        rubric or repository-instruction change as if it were a real defect.
        """
        document = self._promotion("no-promotion-example")
        document["positive_case_ids"] = ["cache-ttl-duplicate-with-new-surface"]
        errors = curation.validate_promotion_decision(document, self.records)
        self.assertTrue(
            any(
                "cannot support a positive regression case" in error for error in errors
            )
        )

    def test_a_distinct_duplicate_of_a_rejected_record_may_be_a_negative_control(self):
        document = self._promotion("no-promotion-example")
        document["negative_control_case_ids"] = ["cache-ttl-duplicate-with-new-surface"]
        self.assertEqual(
            [], curation.validate_promotion_decision(document, self.records)
        )

    def test_a_duplicate_of_an_unresolved_claim_cannot_be_promoted_either(self):
        document = self._promotion("no-promotion-example")
        document["negative_control_case_ids"] = ["unresolved-duplicate-claim"]
        errors = curation.validate_promotion_decision(document, self.records)
        self.assertTrue(
            any("duplicates an unresolved claim" in error for error in errors)
        )

    def test_a_duplicate_chain_resolves_through_more_than_one_hop(self):
        """`_resolve_duplicate_disposition` must follow a duplicate-of-a-duplicate."""
        chained = copy.deepcopy(self.records["retry-jitter-duplicate-with-new-surface"])
        chained["record_id"] = "retry-jitter-duplicate-chain"
        chained["duplicate_of"] = "retry-jitter-duplicate-with-new-surface"
        chained["distinct_contribution"] = "A third surface, one more hop away."
        records = {**self.records, "retry-jitter-duplicate-chain": chained}
        document = self._promotion("no-promotion-example")
        document["positive_case_ids"] = ["retry-jitter-duplicate-chain"]
        document["negative_control_case_ids"] = []
        self.assertEqual([], curation.validate_promotion_decision(document, records))

    def test_a_duplicate_cycle_cannot_be_resolved_and_is_rejected(self):
        first = copy.deepcopy(self.records["retry-jitter-duplicate-with-new-surface"])
        first["record_id"] = "cycle-a"
        first["duplicate_of"] = "cycle-b"
        second = copy.deepcopy(first)
        second["record_id"] = "cycle-b"
        second["duplicate_of"] = "cycle-a"
        records = {**self.records, "cycle-a": first, "cycle-b": second}
        document = self._promotion("no-promotion-example")
        document["positive_case_ids"] = ["cycle-a"]
        document["negative_control_case_ids"] = []
        errors = curation.validate_promotion_decision(document, records)
        self.assertTrue(any("could not be resolved" in error for error in errors))

    def test_a_rejected_record_cannot_support_a_positive_case(self):
        document = self._promotion("no-promotion-example")
        document["positive_case_ids"] = ["cache-ttl-false-positive"]
        errors = curation.validate_promotion_decision(document, self.records)
        self.assertTrue(
            any(
                "cannot support a positive regression case" in error for error in errors
            )
        )

    def test_an_accepted_record_cannot_support_a_negative_control(self):
        document = self._promotion("no-promotion-example")
        document["negative_control_case_ids"] = ["stale-config-schema-defect"]
        errors = curation.validate_promotion_decision(document, self.records)
        self.assertTrue(
            any("cannot support a negative control" in error for error in errors)
        )

    def test_global_rubric_update_requires_two_distinct_surfaces(self):
        document = self._promotion("global-rubric-promotion-example")
        document["positive_case_ids"] = ["stale-config-schema-defect"]
        errors = curation.validate_promotion_decision(document, self.records)
        self.assertTrue(
            any("representative positive cases" in error for error in errors)
        )

    def test_global_rubric_update_requires_a_negative_control(self):
        document = self._promotion("global-rubric-promotion-example")
        document["negative_control_case_ids"] = []
        errors = curation.validate_promotion_decision(document, self.records)
        self.assertTrue(any("negative control" in error for error in errors))

    def test_repository_instruction_update_rejects_a_new_subsystem_path(self):
        document = self._promotion("repository-instruction-promotion-example")
        document["target"]["path"] = "review-suite/evals/curation/PATH-RULES.json"
        errors = curation.validate_promotion_decision(document, self.records)
        self.assertTrue(any("not a new one" in error for error in errors))

    def test_repository_instruction_update_rejects_a_nonexistent_instruction_file(self):
        document = self._promotion("repository-instruction-promotion-example")
        document["target"]["path"] = "skills/nonexistent-skill/AGENTS.md"
        errors = curation.validate_promotion_decision(document, self.records)
        self.assertTrue(any("does not exist" in error for error in errors))

    def test_no_promotion_must_not_declare_a_target(self):
        document = self._promotion("no-promotion-example")
        document["target"] = {
            "kind": "global_rubric",
            "path": "review-suite/CONTRACT.md",
            "summary": "should not be permitted",
        }
        errors = curation.validate_promotion_decision(document, self.records)
        self.assertTrue(any("must not declare a target" in error for error in errors))

    def test_a_record_cannot_be_both_positive_and_negative(self):
        document = self._promotion("no-promotion-example")
        document["positive_case_ids"] = ["cache-ttl-false-positive"]
        document["negative_control_case_ids"] = ["cache-ttl-false-positive"]
        errors = curation.validate_promotion_decision(document, self.records)
        self.assertTrue(any("both positive and negative" in error for error in errors))

    def test_missing_cost_evidence_fails_closed(self):
        document = self._promotion("no-promotion-example")
        del document["evidence"]["before"]["cost"]["reason"]
        errors = curation.validate_promotion_decision(document, self.records)
        self.assertTrue(
            any("cost.unavailable requires a reason" in error for error in errors)
        )

    def test_reported_and_unavailable_cost_together_fails_closed(self):
        document = self._promotion("global-rubric-promotion-example")
        document["evidence"]["before"]["cost"]["unavailable"] = True
        errors = curation.validate_promotion_decision(document, self.records)
        self.assertTrue(
            any("both reported and unavailable" in error for error in errors)
        )

    def test_a_non_numeric_recall_fails_closed(self):
        document = self._promotion("global-rubric-promotion-example")
        document["evidence"]["before"]["recall"] = "high"
        errors = curation.validate_promotion_decision(document, self.records)
        self.assertTrue(any("recall must be a number" in error for error in errors))


class AuditCommandTests(unittest.TestCase):
    def test_audit_passes_on_the_shipped_curation_set(self):
        self.assertEqual([], audit_curation.audit())

    def test_audit_script_exits_zero(self):
        completed = subprocess.run(
            [sys.executable, str(AUDIT_SCRIPT)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn("curation audit passed", completed.stdout)

    def test_audit_script_reports_a_missing_records_directory(self):
        completed = subprocess.run(
            [sys.executable, str(AUDIT_SCRIPT), "--records", "/nonexistent/records"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(1, completed.returncode)
        self.assertIn("missing curation records directory", completed.stderr)

    def test_audit_fails_on_a_mutated_promotion(self):
        with self.subTest("baseline is clean"):
            self.assertEqual([], audit_curation.audit())
        mutated = copy.deepcopy(
            _load(curation.DEFAULT_PROMOTIONS / "no-promotion-example.json")
        )
        mutated["positive_case_ids"] = ["unpatched-token-scope-claim"]
        tmp_dir = curation.DEFAULT_PROMOTIONS.parent / "promotions-mutated-tmp"
        tmp_dir.mkdir(exist_ok=True)
        self.addCleanup(tmp_dir.rmdir)
        self.addCleanup(lambda: [p.unlink() for p in tmp_dir.glob("*.json")])
        (tmp_dir / "mutated.json").write_text(json.dumps(mutated))
        errors = audit_curation.audit(promotions_root=tmp_dir)
        self.assertTrue(errors)
        self.assertTrue(
            any("unresolved claims cannot enter" in error for error in errors)
        )


if __name__ == "__main__":
    unittest.main()
