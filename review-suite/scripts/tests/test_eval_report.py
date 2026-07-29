"""Reporting tests: every required metric must be representable and correct."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from evals import protocol, report  # noqa: E402

CONFIGURATION = {"executor": "test", "runs_per_case": 2}


def attempt(
    case_id,
    run_number,
    status="review_result",
    *,
    grade=None,
    simulation=False,
    duration=1.0,
    usage=None,
    verdict=None,
):
    if verdict is None:
        if status == "blocked":
            verdict = "blocked"
        elif grade:
            verdict = grade["observed_verdict"]
    return {
        "case_id": case_id,
        "case_ref": protocol.case_ref(case_id),
        "run_number": run_number,
        "status": status,
        "detail": "",
        "simulation": simulation,
        "duration_seconds": duration,
        "usage": usage,
        "verdict": verdict,
        "grade": grade,
    }


def grade(
    *,
    expected="changes_required",
    observed="changes_required",
    expected_ids=("rc.one",),
    matched_ids=("rc.one",),
    referred_ids=(),
    referred_relevant_ids=None,
    false_positives=(),
    adjudication=(),
):
    # Defaults to `referred_ids` so most callers, which are not exercising the
    # relevance guard itself, get relevance-guard-eligible referrals without
    # having to say so twice.
    if referred_relevant_ids is None:
        referred_relevant_ids = referred_ids
    combined_ids = set(matched_ids) | set(referred_relevant_ids)
    return {
        "grader_version": "1.0",
        "expected_verdict": expected,
        "observed_verdict": observed,
        "verdict_match": expected == observed,
        "false_clean": expected == "changes_required" and observed == "clean",
        "false_alarm": expected == "clean" and observed == "changes_required",
        "expected_root_cause_ids": list(expected_ids),
        "matched_root_cause_ids": list(matched_ids),
        "missed_root_cause_ids": [
            i for i in expected_ids if i not in matched_ids and i not in referred_ids
        ],
        "referred_root_cause_ids": list(referred_ids),
        "referred_relevant_root_cause_ids": list(referred_relevant_ids),
        "recall": (len(matched_ids) / len(expected_ids)) if expected_ids else None,
        "combined_recall": (
            (len(combined_ids) / len(expected_ids)) if expected_ids else None
        ),
        "findings": [],
        "false_positive_finding_ids": list(false_positives),
        "accepted_finding_ids": [],
        "duplicate_finding_ids": [],
        "adjudication_required": list(adjudication),
    }


class MetricTests(unittest.TestCase):
    def test_every_required_metric_is_present(self):
        aggregate = report.aggregate(
            [attempt("subject-one", 1, grade=grade())], configuration=CONFIGURATION
        )
        for key in (
            "material_finding_recall",
            "false_clean_rate",
            "false_positive_rate",
            "unique_finding_contribution",
        ):
            self.assertIn(key, aggregate["quality"])
        for key in ("mean_verdict_stability", "mean_finding_stability"):
            self.assertIn(key, aggregate["stability"])
        for status in protocol.ATTEMPT_STATUSES:
            if status != "review_result":
                self.assertIn(f"{status}_rate", aggregate["failures"])
        self.assertIn("mean_seconds", aggregate["latency"])
        self.assertIn("total_cost_usd", aggregate["usage"])
        self.assertEqual(report.REPORT_VERSION, aggregate["report_version"])

    def test_a_referred_root_cause_is_reported_separately_from_a_miss(self):
        """Three-way scoring, settled on #58: referred is neither match nor miss.

        Reported at both levels - the per-case union and the aggregate rate -
        so a reader never has to infer a referral from an unexplained gap
        between `matched_root_cause_ids` and `expected_root_cause_ids`.
        """
        aggregate = report.aggregate(
            [
                attempt(
                    "subject-one",
                    1,
                    grade=grade(
                        expected_ids=("rc.one", "rc.two"),
                        matched_ids=("rc.one",),
                        referred_ids=("rc.two",),
                    ),
                )
            ],
            configuration=CONFIGURATION,
        )
        self.assertIn("referred_rate", aggregate["quality"])
        self.assertEqual(1.0, aggregate["quality"]["referred_rate"])
        self.assertEqual(1, aggregate["quality"]["referred_denominator"])
        per_case = aggregate["per_case"][0]
        self.assertEqual(["rc.two"], per_case["ever_referred_root_cause_ids"])

    def test_referred_path_relevance_guard_is_reported_per_case(self):
        """The preregistered v2 scoring gate's combined matched+referred path.

        A referral that never named the actual surface must not inflate the
        combined rate, even though it still shows up in the plain referred
        union above.
        """
        aggregate = report.aggregate(
            [
                attempt(
                    "subject-one",
                    1,
                    grade=grade(
                        expected_ids=("rc.one",),
                        matched_ids=(),
                        referred_ids=("rc.one",),
                        referred_relevant_ids=(),
                    ),
                ),
                attempt(
                    "subject-one",
                    2,
                    grade=grade(
                        expected_ids=("rc.one",),
                        matched_ids=(),
                        referred_ids=("rc.one",),
                        referred_relevant_ids=("rc.one",),
                    ),
                ),
            ],
            configuration=CONFIGURATION,
        )
        per_case = aggregate["per_case"][0]
        self.assertEqual(["rc.one"], per_case["ever_referred_root_cause_ids"])
        # `ever_referred_relevant_root_cause_ids` is a union across attempts,
        # like `ever_referred_root_cause_ids` above, so it still names rc.one
        # (attempt 2 was relevant) - the guard's effect shows up in the rate
        # below, not by hiding rc.one from this union.
        self.assertEqual(["rc.one"], per_case["ever_referred_relevant_root_cause_ids"])
        # attempt 1: 0/1 relevant; attempt 2: 1/1 relevant -> mean 0.5
        self.assertEqual(0.5, per_case["mean_combined_recall"])

    def test_combined_recall_gracefully_handles_grades_predating_the_guard(self):
        """A grade dict without the new fields must not crash the report."""
        legacy_grade = grade(matched_ids=("rc.one",))
        del legacy_grade["referred_relevant_root_cause_ids"]
        del legacy_grade["combined_recall"]
        aggregate = report.aggregate(
            [attempt("subject-one", 1, grade=legacy_grade)],
            configuration=CONFIGURATION,
        )
        per_case = aggregate["per_case"][0]
        self.assertEqual([], per_case["ever_referred_relevant_root_cause_ids"])
        self.assertIsNone(per_case["mean_combined_recall"])

    def test_recall_averages_only_graded_attempts(self):
        aggregate = report.aggregate(
            [
                attempt("subject-one", 1, grade=grade(matched_ids=("rc.one",))),
                attempt("subject-one", 2, grade=grade(matched_ids=())),
                attempt("subject-two", 1, status="timeout"),
            ],
            configuration=CONFIGURATION,
        )
        self.assertEqual(0.5, aggregate["quality"]["material_finding_recall"])
        self.assertEqual(2, aggregate["quality"]["recall_attempts"])
        self.assertEqual(2, aggregate["graded_attempts"])

    def test_a_failed_attempt_is_never_scored_as_clean(self):
        aggregate = report.aggregate(
            [
                attempt("subject-one", 1, status="timeout"),
                attempt("subject-one", 2, status="runtime_failure"),
            ],
            configuration=CONFIGURATION,
        )
        self.assertEqual(0, aggregate["graded_attempts"])
        self.assertIsNone(aggregate["quality"]["material_finding_recall"])
        self.assertIsNone(aggregate["quality"]["false_clean_rate"])
        self.assertEqual(0.5, aggregate["failures"]["timeout_rate"])
        self.assertEqual(0.5, aggregate["failures"]["runtime_failure_rate"])

    def test_false_clean_and_false_positive_rates(self):
        aggregate = report.aggregate(
            [
                attempt(
                    "subject-one",
                    1,
                    grade=grade(observed="clean", matched_ids=()),
                ),
                attempt("subject-one", 2, grade=grade()),
                attempt(
                    "subject-two",
                    1,
                    grade=grade(false_positives=("correctness.invented",)),
                ),
            ],
            configuration=CONFIGURATION,
        )
        self.assertAlmostEqual(1 / 3, aggregate["quality"]["false_clean_rate"])
        self.assertEqual(3, aggregate["quality"]["false_clean_denominator"])
        self.assertAlmostEqual(1 / 3, aggregate["quality"]["false_positive_rate"])

    def test_unstable_verdicts_and_findings_are_reported(self):
        aggregate = report.aggregate(
            [
                attempt("subject-one", 1, grade=grade()),
                attempt(
                    "subject-one", 2, grade=grade(observed="clean", matched_ids=())
                ),
            ],
            configuration=CONFIGURATION,
        )
        self.assertEqual(0.5, aggregate["stability"]["mean_verdict_stability"])
        self.assertEqual(0.5, aggregate["stability"]["mean_finding_stability"])

    def test_a_reviewer_that_alternates_blocking_is_not_reported_as_stable(self):
        """Refusing a verdict on one run and giving one on the next is unstable."""
        aggregate = report.aggregate(
            [
                attempt("subject-one", 1, status="blocked"),
                attempt("subject-one", 2, grade=grade()),
            ],
            configuration=CONFIGURATION,
        )
        self.assertEqual(0.5, aggregate["stability"]["mean_verdict_stability"])
        self.assertEqual(0.5, aggregate["stability"]["mean_finding_stability"])
        self.assertEqual(
            {"subject-one": 2}, aggregate["stability"]["per_case_stability_denominator"]
        )

    def test_blocking_is_not_agreement_with_answering_and_finding_nothing(self):
        """A refused verdict and a zero-match answer are different behaviours.

        Both contribute no matched root causes, so collapsing them to the same
        empty set would report the pair as perfectly stable on findings even
        though verdict stability correctly reports 0.5.
        """
        aggregate = report.aggregate(
            [
                attempt("subject-one", 1, status="blocked"),
                attempt("subject-one", 2, grade=grade(matched_ids=())),
            ],
            configuration=CONFIGURATION,
        )
        self.assertEqual(0.5, aggregate["stability"]["mean_verdict_stability"])
        self.assertEqual(0.5, aggregate["stability"]["mean_finding_stability"])
        self.assertEqual(2, aggregate["stability"]["stability_denominator"])

    def test_every_stability_figure_publishes_its_denominator(self):
        aggregate = report.aggregate(
            [
                attempt("subject-one", 1, grade=grade()),
                attempt("subject-one", 2, status="timeout"),
                attempt("subject-two", 1, status="blocked"),
            ],
            configuration=CONFIGURATION,
        )
        # The timed-out attempt produced no review, so it is outside stability;
        # the blocked one produced a valid review, so it is inside it.
        self.assertEqual(2, aggregate["stability"]["stability_denominator"])
        self.assertEqual(
            {"subject-one": 1, "subject-two": 1},
            aggregate["stability"]["per_case_stability_denominator"],
        )

    def test_a_consistently_blocking_reviewer_is_reported_as_stable(self):
        aggregate = report.aggregate(
            [
                attempt("subject-one", 1, status="blocked"),
                attempt("subject-one", 2, status="blocked"),
            ],
            configuration=CONFIGURATION,
        )
        self.assertEqual(1.0, aggregate["stability"]["mean_verdict_stability"])
        self.assertEqual(2, aggregate["stability"]["stability_denominator"])
        self.assertEqual(0, aggregate["graded_attempts"])

    def test_unique_finding_contribution_names_root_causes_only_some_runs_found(self):
        aggregate = report.aggregate(
            [
                attempt(
                    "subject-one",
                    1,
                    grade=grade(
                        expected_ids=("rc.one", "rc.two"), matched_ids=("rc.one",)
                    ),
                ),
                attempt(
                    "subject-one",
                    2,
                    grade=grade(
                        expected_ids=("rc.one", "rc.two"),
                        matched_ids=("rc.one", "rc.two"),
                    ),
                ),
            ],
            configuration=CONFIGURATION,
        )
        self.assertEqual(
            [{"case_id": "subject-one", "only_some_attempts": ["rc.two"]}],
            aggregate["quality"]["unique_finding_contribution"],
        )

    def test_latency_is_summarized(self):
        aggregate = report.aggregate(
            [
                attempt("subject-one", 1, grade=grade(), duration=1.0),
                attempt("subject-one", 2, grade=grade(), duration=3.0),
            ],
            configuration=CONFIGURATION,
        )
        self.assertEqual(
            {
                "count": 2,
                "mean_seconds": 2.0,
                "p50_seconds": 2.0,
                "min_seconds": 1.0,
                "max_seconds": 3.0,
            },
            aggregate["latency"],
        )

    def test_absent_usage_is_reported_as_unavailable(self):
        aggregate = report.aggregate(
            [attempt("subject-one", 1, grade=grade())], configuration=CONFIGURATION
        )
        self.assertFalse(aggregate["usage"]["available"])
        self.assertIsNone(aggregate["usage"]["total_cost_usd"])

    def test_reported_usage_is_totalled_with_its_denominator(self):
        aggregate = report.aggregate(
            [
                attempt(
                    "subject-one",
                    1,
                    grade=grade(),
                    usage={"cost_usd": 0.25, "input_tokens": 10},
                ),
                attempt("subject-one", 2, grade=grade()),
            ],
            configuration=CONFIGURATION,
        )
        self.assertTrue(aggregate["usage"]["available"])
        self.assertEqual(0.25, aggregate["usage"]["total_cost_usd"])
        self.assertEqual(1, aggregate["usage"]["reporting_attempts_cost_usd"])
        self.assertIsNone(aggregate["usage"]["total_output_tokens"])

    def test_adjudication_requests_carry_their_case_and_run(self):
        aggregate = report.aggregate(
            [
                attempt(
                    "subject-one",
                    1,
                    grade=grade(
                        adjudication=[
                            {
                                "finding_id": "correctness.one",
                                "reason": "ambiguous",
                                "candidate_root_cause_ids": ["rc.one", "rc.two"],
                            }
                        ]
                    ),
                )
            ],
            configuration=CONFIGURATION,
        )
        self.assertEqual(
            [
                {
                    "case_id": "subject-one",
                    "run_number": 1,
                    "finding_id": "correctness.one",
                    "reason": "ambiguous",
                    "candidate_root_cause_ids": ["rc.one", "rc.two"],
                }
            ],
            aggregate["adjudication_required"],
        )


class BaselineEligibilityTests(unittest.TestCase):
    def test_one_simulated_attempt_disqualifies_the_whole_report(self):
        aggregate = report.aggregate(
            [
                attempt("subject-one", 1, grade=grade()),
                attempt("subject-one", 2, grade=grade(), simulation=True),
            ],
            configuration=CONFIGURATION,
        )
        self.assertTrue(aggregate["simulation"])
        self.assertFalse(aggregate["baseline_eligible"])

    def test_a_fully_real_run_is_baseline_eligible(self):
        aggregate = report.aggregate(
            [attempt("subject-one", 1, grade=grade())], configuration=CONFIGURATION
        )
        self.assertFalse(aggregate["simulation"])
        self.assertTrue(aggregate["baseline_eligible"])

    def test_the_report_encodes_no_success_threshold(self):
        """Interpretation belongs to a later ticket, not to the evaluator."""
        aggregate = report.aggregate(
            [attempt("subject-one", 1, grade=grade(matched_ids=()))],
            configuration=CONFIGURATION,
        )
        forbidden = {"passed", "failed", "threshold", "target", "gate", "ok"}
        self.assertEqual(set(), forbidden & set(aggregate))
        self.assertEqual(set(), forbidden & set(aggregate["quality"]))


if __name__ == "__main__":
    unittest.main()
