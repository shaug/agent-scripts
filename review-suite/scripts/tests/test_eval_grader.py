"""Grading-interface tests for the deterministic reference grader."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from evals import grader  # noqa: E402

CANDIDATE = {"head_sha": "a" * 40, "comparison_base_sha": "b" * 40}

ROOT_CAUSE = {
    "id": "rc.deadline",
    "requirement": "A refreshed session keeps working for a further window.",
    "trigger": "a refresh late in the original window",
    "surface": "session.py:refresh",
    "consequence": "an operator loses an active session",
    "severity": "blocking",
    "equivalent_formulations": [
        "stale expiry clock",
        "deadline is not recomputed",
    ],
}

SECOND_ROOT_CAUSE = {
    "id": "rc.record",
    "requirement": "Every refresh is recorded.",
    "trigger": "reading the log after several refreshes",
    "surface": "session.py:refresh",
    "consequence": "the history cannot be reconstructed",
    "severity": "strong_recommendation",
    "equivalent_formulations": ["no entry is written"],
}

NON_FINDING = {
    "id": "anf.naming",
    "description": "Remarking on the pre-existing helper name is tolerated.",
    "equivalent_formulations": ["the helper name predates this change"],
}


def finding(identifier, *, severity="blocking", location="session.py:31", **text):
    body = {
        "rule": "A stated requirement is not met.",
        "concern": "The requirement is not met.",
        "impact": "Users are affected.",
        "proposed_change": "Meet the requirement.",
        "expected_effect": "The requirement is met.",
        "detail": "Demonstrated in the diff.",
    }
    body.update(text)
    return {
        "id": identifier,
        "lens": "correctness",
        "severity": severity,
        "confidence": "high",
        "rule": body["rule"],
        "evidence": [{"location": location, "detail": body["detail"]}],
        "concern": body["concern"],
        "impact": body["impact"],
        "proposed_change": body["proposed_change"],
        "expected_effect": body["expected_effect"],
        "location": location,
    }


def result(verdict, findings):
    return {
        "schema_version": "1.0",
        "lens": "aggregate",
        "candidate": dict(CANDIDATE),
        "verdict": verdict,
        "findings": findings,
        "blocking_reasons": [],
    }


def expectation(verdict, root_causes, non_findings=()):
    return {
        "expectation_version": "1.0",
        "case_id": "subject-under-test",
        "packet_valid": True,
        "expected_verdict": verdict,
        "material_root_causes": list(root_causes),
        "accepted_non_findings": list(non_findings),
    }


def classification_of(grade, finding_id):
    return next(
        record["classification"]
        for record in grade["findings"]
        if record["finding_id"] == finding_id
    )


class MatchingTests(unittest.TestCase):
    def test_a_paraphrase_of_the_root_cause_matches(self):
        grade = grader.grade(
            expectation("changes_required", [ROOT_CAUSE]),
            result(
                "changes_required",
                [
                    finding(
                        "correctness.one",
                        concern="The refresh path keeps a stale expiry clock.",
                    )
                ],
            ),
        )
        self.assertEqual(["rc.deadline"], grade["matched_root_cause_ids"])
        self.assertEqual(1.0, grade["recall"])
        self.assertEqual("matched", classification_of(grade, "correctness.one"))

    def test_prose_that_never_names_the_root_cause_does_not_match(self):
        grade = grader.grade(
            expectation("changes_required", [ROOT_CAUSE]),
            result(
                "changes_required",
                [finding("correctness.one", location="unrelated_module.py:4")],
            ),
        )
        self.assertEqual([], grade["matched_root_cause_ids"])
        self.assertEqual(["rc.deadline"], grade["missed_root_cause_ids"])
        self.assertEqual(0.0, grade["recall"])

    def test_a_duplicate_symptom_is_not_counted_twice(self):
        grade = grader.grade(
            expectation("changes_required", [ROOT_CAUSE]),
            result(
                "changes_required",
                [
                    finding("correctness.one", concern="A stale expiry clock."),
                    finding(
                        "correctness.two",
                        severity="strong_recommendation",
                        concern="Sessions lapse early; a stale expiry clock.",
                    ),
                ],
            ),
        )
        self.assertEqual(["rc.deadline"], grade["matched_root_cause_ids"])
        self.assertEqual(1.0, grade["recall"])
        self.assertEqual(["correctness.two"], grade["duplicate_finding_ids"])
        self.assertEqual([], grade["false_positive_finding_ids"])

    def test_a_partial_match_is_referred_for_adjudication(self):
        """Right surface, unrecognized description: neither hit nor miss."""
        grade = grader.grade(
            expectation("changes_required", [ROOT_CAUSE]),
            result(
                "changes_required",
                [finding("correctness.one", concern="Something feels off here.")],
            ),
        )
        self.assertEqual("partial", classification_of(grade, "correctness.one"))
        self.assertEqual([], grade["matched_root_cause_ids"])
        self.assertEqual([], grade["false_positive_finding_ids"])
        self.assertEqual(
            [
                {
                    "finding_id": "correctness.one",
                    "reason": "partial",
                    "candidate_root_cause_ids": ["rc.deadline"],
                }
            ],
            grade["adjudication_required"],
        )
        # Three-way scoring: a partial match is referred, not a scored miss.
        # Collapsing it into `missed_root_cause_ids` would be exactly the
        # silent reviewer-miss the owner-settled grading method forbids.
        self.assertEqual([], grade["missed_root_cause_ids"])
        self.assertEqual(["rc.deadline"], grade["referred_root_cause_ids"])

    def test_a_finding_matching_two_root_causes_is_ambiguous(self):
        grade = grader.grade(
            expectation("changes_required", [ROOT_CAUSE, SECOND_ROOT_CAUSE]),
            result(
                "changes_required",
                [
                    finding(
                        "correctness.one",
                        concern="A stale expiry clock and no entry is written.",
                    )
                ],
            ),
        )
        self.assertEqual("ambiguous", classification_of(grade, "correctness.one"))
        self.assertEqual([], grade["matched_root_cause_ids"])
        self.assertEqual(
            ["rc.deadline", "rc.record"],
            grade["adjudication_required"][0]["candidate_root_cause_ids"],
        )
        # An ambiguous candidate is referred for both root causes, not a
        # scored miss for either.
        self.assertEqual([], grade["missed_root_cause_ids"])
        self.assertEqual(["rc.deadline", "rc.record"], grade["referred_root_cause_ids"])

    def test_a_root_cause_with_no_candidate_finding_is_a_genuine_miss(self):
        """Nothing pointed at it at all: this is the one case referral must not swallow."""
        grade = grader.grade(
            expectation("changes_required", [ROOT_CAUSE]),
            result("changes_required", []),
        )
        self.assertEqual(["rc.deadline"], grade["missed_root_cause_ids"])
        self.assertEqual([], grade["referred_root_cause_ids"])
        self.assertEqual(0.0, grade["recall"])

    def test_an_unexpected_gating_finding_is_a_false_positive(self):
        grade = grader.grade(
            expectation("changes_required", [ROOT_CAUSE]),
            result(
                "changes_required",
                [
                    finding("correctness.one", concern="A stale expiry clock."),
                    finding(
                        "correctness.invented",
                        location="theme.py:3",
                        concern="Colours should be configurable.",
                    ),
                ],
            ),
        )
        self.assertEqual("unexpected", classification_of(grade, "correctness.invented"))
        self.assertEqual(["correctness.invented"], grade["false_positive_finding_ids"])

    def test_a_deferred_unexpected_finding_is_not_a_false_positive(self):
        grade = grader.grade(
            expectation("changes_required", [ROOT_CAUSE]),
            result(
                "changes_required",
                [
                    finding("correctness.one", concern="A stale expiry clock."),
                    finding(
                        "correctness.noted",
                        severity="defer",
                        location="theme.py:3",
                        concern="An unrelated pre-existing smell.",
                    ),
                ],
            ),
        )
        self.assertEqual([], grade["false_positive_finding_ids"])

    def test_an_accepted_non_finding_is_tolerated(self):
        grade = grader.grade(
            expectation("clean", [], [NON_FINDING]),
            result(
                "clean",
                [
                    finding(
                        "correctness.naming",
                        severity="defer",
                        location="invoice.py:52",
                        concern="The helper name predates this change.",
                    )
                ],
            ),
        )
        self.assertEqual("accepted", classification_of(grade, "correctness.naming"))
        self.assertEqual(["correctness.naming"], grade["accepted_finding_ids"])
        self.assertEqual([], grade["false_positive_finding_ids"])
        self.assertFalse(grade["false_alarm"])


class VerdictTests(unittest.TestCase):
    def test_a_missed_root_cause_reported_as_no_change_is_a_false_clean(self):
        grade = grader.grade(
            expectation("changes_required", [ROOT_CAUSE]), result("clean", [])
        )
        self.assertTrue(grade["false_clean"])
        self.assertFalse(grade["verdict_match"])
        self.assertEqual(0.0, grade["recall"])

    def test_gating_a_correct_candidate_is_a_false_alarm(self):
        grade = grader.grade(
            expectation("clean", []),
            result(
                "changes_required",
                [finding("correctness.invented", location="theme.py:3")],
            ),
        )
        self.assertTrue(grade["false_alarm"])
        self.assertEqual(["correctness.invented"], grade["false_positive_finding_ids"])

    def test_recall_is_absent_when_nothing_material_is_expected(self):
        grade = grader.grade(expectation("clean", []), result("clean", []))
        self.assertIsNone(grade["recall"])
        self.assertTrue(grade["verdict_match"])

    def test_grading_without_an_expectation_fails_loudly(self):
        with self.assertRaises(grader.GradingError):
            grader.grade(None, result("clean", []))

    def test_the_grade_records_its_own_version(self):
        grade = grader.grade(expectation("clean", []), result("clean", []))
        self.assertEqual(grader.GRADER_VERSION, grade["grader_version"])


class NormalizationTests(unittest.TestCase):
    def test_punctuation_and_case_do_not_change_a_match(self):
        self.assertEqual(
            "full",
            grader.match_strength(
                ROOT_CAUSE,
                finding("correctness.one", concern="Stale-Expiry-Clock!"),
            ),
        )

    def test_a_file_extension_alone_is_not_a_surface_match(self):
        self.assertEqual(
            "none",
            grader.match_strength(
                ROOT_CAUSE, finding("correctness.one", location="other.py:9")
            ),
        )


if __name__ == "__main__":
    unittest.main()
