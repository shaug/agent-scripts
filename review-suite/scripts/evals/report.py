#!/usr/bin/env python3
"""Per-attempt records and the aggregate report for repeated replay runs.

The aggregate report is descriptive only. It deliberately encodes no success
threshold and returns no pass/fail judgement: #59 owns interpretation and any
future v2 gate. Metrics are reported with their denominators so a small run
count cannot be mistaken for a precise capability measurement.
"""

from __future__ import annotations

import statistics
from typing import Any

from . import grader, protocol

REPORT_VERSION = "1.0"


def _rate(numerator: int, denominator: int) -> float | None:
    return (numerator / denominator) if denominator else None


def _numbers(values: list[Any]) -> list[float]:
    return [
        float(value)
        for value in values
        if not isinstance(value, bool) and isinstance(value, (int, float))
    ]


def _latency(durations: list[float]) -> dict[str, Any]:
    if not durations:
        return {"count": 0}
    ordered = sorted(durations)
    return {
        "count": len(ordered),
        "mean_seconds": statistics.fmean(ordered),
        "p50_seconds": statistics.median(ordered),
        "min_seconds": ordered[0],
        "max_seconds": ordered[-1],
    }


def _usage(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate whatever usage the executor reported, and say what is absent."""
    reported = [attempt.get("usage") or {} for attempt in attempts]
    totals: dict[str, Any] = {}
    for field in ("input_tokens", "output_tokens", "cost_usd"):
        values = _numbers([usage.get(field) for usage in reported])
        totals[f"total_{field}"] = sum(values) if values else None
        totals[f"reporting_attempts_{field}"] = len(values)
    totals["available"] = any(
        totals[f"reporting_attempts_{field}"]
        for field in ("input_tokens", "output_tokens", "cost_usd")
    )
    return totals


def _mean_of(values: list[Any]) -> float | None:
    present = [value for value in values if value is not None]
    return statistics.fmean(present) if present else None


def _modal_share(values: list[Any]) -> float | None:
    """Return the share of attempts holding the most common value."""
    if not values:
        return None
    counts: dict[Any, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return max(counts.values()) / len(values)


def _case_summary(case_id: str, attempts: list[dict[str, Any]]) -> dict[str, Any]:
    graded = [a for a in attempts if a["status"] in protocol.GRADABLE_STATUSES]
    grades = [a["grade"] for a in graded if a.get("grade")]
    recalls = [g["recall"] for g in grades if g["recall"] is not None]

    # Stability spans every attempt that produced a valid review, including a
    # `blocked` one. Refusing a verdict on one run and issuing one on the next
    # is among the most consequential instabilities a reviewer can show, so it
    # must not be excluded just because a blocked review is not graded.
    answered = [a for a in attempts if a["status"] in protocol.VALID_OUTCOME_STATUSES]
    # A blocked attempt is ungraded, and `None` keeps it distinguishable from a
    # graded attempt that matched nothing. Collapsing both to the empty set
    # would report a run that refused a verdict and a run that answered and
    # found nothing as being in perfect agreement.
    matched_sets = [
        tuple(sorted(a["grade"]["matched_root_cause_ids"])) if a.get("grade") else None
        for a in answered
    ]

    union: set[str] = set()
    intersection: set[str] | None = None
    referred_union: set[str] = set()
    referred_relevant_union: set[str] = set()
    combined_recalls: list[float] = []
    for grade_record in grades:
        found = set(grade_record["matched_root_cause_ids"])
        union |= found
        intersection = found if intersection is None else (intersection & found)
        referred_union |= set(grade_record["referred_root_cause_ids"])
        # `.get(..., [])` keeps this readable against a grade dict built before
        # the referred-path relevance guard existed (e.g. hand-built test
        # fixtures), which never claims the combined path passes.
        referred_relevant_union |= set(
            grade_record.get("referred_relevant_root_cause_ids", [])
        )
        combined_recall = grade_record.get("combined_recall")
        if combined_recall is not None:
            combined_recalls.append(combined_recall)
    expected = grades[0]["expected_root_cause_ids"] if grades else []

    return {
        "case_id": case_id,
        "attempts": len(attempts),
        "graded_attempts": len(grades),
        "expected_root_cause_ids": expected,
        "mean_recall": statistics.fmean(recalls) if recalls else None,
        "union_root_cause_ids": sorted(union),
        "intersection_root_cause_ids": sorted(intersection or set()),
        # Three-way scoring: a root cause ever referred for adjudication on
        # any attempt is neither a confirmed match nor a scored miss for this
        # case. Reported separately so a reader never has to infer a referral
        # from the absence of a match.
        "ever_referred_root_cause_ids": sorted(referred_union),
        # Referred-path relevance guard: the subset of the line above where a
        # referring finding concretely named the root cause's actual surface,
        # not merely prose the grader could not fully resolve either way.
        "ever_referred_relevant_root_cause_ids": sorted(referred_relevant_union),
        # The preregistered v2 scoring gate's alternative pass path: mean, per
        # attempt, of (matched + relevance-guarded referred) / expected. A
        # case may pass on `mean_recall` alone, on this alone, or on neither.
        "mean_combined_recall": (
            statistics.fmean(combined_recalls) if combined_recalls else None
        ),
        "verdict_stability": _modal_share([a["verdict"] for a in answered]),
        "finding_stability": _modal_share(matched_sets),
        "stability_denominator": len(answered),
        "false_clean_attempts": sum(1 for g in grades if g["false_clean"]),
        "false_alarm_attempts": sum(1 for g in grades if g["false_alarm"]),
        "false_positive_attempts": sum(
            1 for g in grades if g["false_positive_finding_ids"]
        ),
        "statuses": {
            status: sum(1 for a in attempts if a["status"] == status)
            for status in protocol.ATTEMPT_STATUSES
            if any(a["status"] == status for a in attempts)
        },
    }


def aggregate(
    attempts: list[dict[str, Any]], *, configuration: dict[str, Any]
) -> dict[str, Any]:
    """Build the machine-readable aggregate report for one evaluation run."""
    by_case: dict[str, list[dict[str, Any]]] = {}
    for attempt in attempts:
        by_case.setdefault(attempt["case_id"], []).append(attempt)

    graded = [a for a in attempts if a["status"] in protocol.GRADABLE_STATUSES]
    grades = [a["grade"] for a in graded if a.get("grade")]
    recalls = [g["recall"] for g in grades if g["recall"] is not None]
    gating_expected = [g for g in grades if g["expected_root_cause_ids"]]
    clean_expected = [g for g in grades if g["expected_verdict"] == "clean"]

    per_case = [
        _case_summary(case_id, items) for case_id, items in sorted(by_case.items())
    ]
    unique_contribution = [
        {
            "case_id": summary["case_id"],
            "only_some_attempts": sorted(
                set(summary["union_root_cause_ids"])
                - set(summary["intersection_root_cause_ids"])
            ),
        }
        for summary in per_case
        if set(summary["union_root_cause_ids"])
        != set(summary["intersection_root_cause_ids"])
    ]

    simulation = any(attempt["simulation"] for attempt in attempts)
    failures = {
        f"{status}_rate": _rate(
            sum(1 for a in attempts if a["status"] == status), len(attempts)
        )
        for status in protocol.ATTEMPT_STATUSES
        if status != "review_result"
    }

    return {
        "report_version": REPORT_VERSION,
        "protocol_version": protocol.PROTOCOL_VERSION,
        "grader_version": grader.GRADER_VERSION,
        "configuration": configuration,
        "simulation": simulation,
        # A simulated run describes the harness, not a model. It can never be
        # promoted into a behavioural baseline.
        "baseline_eligible": not simulation,
        "attempts": len(attempts),
        "graded_attempts": len(graded),
        "quality": {
            "material_finding_recall": statistics.fmean(recalls) if recalls else None,
            "recall_attempts": len(recalls),
            "false_clean_rate": _rate(
                sum(1 for g in gating_expected if g["false_clean"]),
                len(gating_expected),
            ),
            "false_clean_denominator": len(gating_expected),
            "false_positive_rate": _rate(
                sum(1 for g in grades if g["false_positive_finding_ids"]), len(grades)
            ),
            "false_positive_denominator": len(grades),
            "false_alarm_rate": _rate(
                sum(1 for g in clean_expected if g["false_alarm"]), len(clean_expected)
            ),
            "false_alarm_denominator": len(clean_expected),
            # Three-way scoring, settled on #58: a root cause referred for
            # adjudication is neither a confirmed match nor a scored miss.
            # Reported as its own rate over the same attempts recall is
            # measured over, so a reader can see how much of the
            # not-matched remainder is a genuine miss versus a referral
            # awaiting the owner, rather than inferring it from a gap.
            "referred_rate": _rate(
                sum(1 for g in grades if g["referred_root_cause_ids"]), len(grades)
            ),
            "referred_denominator": len(grades),
            "unique_finding_contribution": unique_contribution,
        },
        "stability": {
            # Averaged over cases: pooling verdicts across unlike cases would
            # report disagreement between cases as instability within one.
            "mean_verdict_stability": _mean_of(
                [summary["verdict_stability"] for summary in per_case]
            ),
            "mean_finding_stability": _mean_of(
                [summary["finding_stability"] for summary in per_case]
            ),
            # Published beside every value, as the quality rates are, so a
            # consumer can see how many attempts each figure rests on.
            "stability_denominator": sum(
                summary["stability_denominator"] for summary in per_case
            ),
            "per_case_verdict_stability": {
                summary["case_id"]: summary["verdict_stability"] for summary in per_case
            },
            "per_case_finding_stability": {
                summary["case_id"]: summary["finding_stability"] for summary in per_case
            },
            "per_case_stability_denominator": {
                summary["case_id"]: summary["stability_denominator"]
                for summary in per_case
            },
        },
        "failures": failures,
        "latency": _latency([a["duration_seconds"] for a in attempts]),
        "usage": _usage(attempts),
        "adjudication_required": [
            {"case_id": a["case_id"], "run_number": a["run_number"], **item}
            for a in graded
            if a.get("grade")
            for item in a["grade"]["adjudication_required"]
        ],
        "per_case": per_case,
    }
