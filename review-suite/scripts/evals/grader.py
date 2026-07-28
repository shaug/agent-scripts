#!/usr/bin/env python3
"""Root-cause grading interface and the deterministic reference grader.

A reviewer is graded on *material root causes*, never on prose. Each private
expectation describes a root cause as a requirement, a triggering condition, an
affected surface, a material consequence, and the formulations a competent
reviewer may use for it. An observed finding matches when it points at the
affected surface *and* uses one of the accepted formulations.

The reference grader is protocol proof, not a calibrated grader and not a v1
score. #58 owns calibration; this module owns the interface and its behaviour
on paraphrases, duplicate symptoms, partial matches, unexpected findings,
accepted non-findings, and ambiguous matches that need adjudication.
"""

from __future__ import annotations

import re
from typing import Any

GRADER_VERSION = "1.0"

#: How one observed finding relates to the private expectation.
CLASSIFICATIONS = (
    "matched",
    "duplicate",
    "partial",
    "ambiguous",
    "accepted",
    "unexpected",
)

#: Severities that make an observed finding gate a merge.
GATING_SEVERITIES = frozenset({"blocking", "strong_recommendation"})

#: File-extension and filler tokens that would make surface matching vacuous.
SURFACE_STOPWORDS = frozenset(
    {
        "diff",
        "go",
        "java",
        "js",
        "json",
        "jsx",
        "md",
        "mjs",
        "py",
        "rb",
        "rs",
        "sql",
        "ts",
        "tsx",
        "yaml",
        "yml",
    }
)

#: Finding fields whose prose may carry an accepted formulation.
FINDING_TEXT_FIELDS = (
    "rule",
    "concern",
    "impact",
    "proposed_change",
    "expected_effect",
)


class GradingError(ValueError):
    """Raised when grading cannot proceed, for example without expectations."""


def normalize(text: str) -> str:
    """Collapse prose to lowercase alphanumeric words for stable matching."""
    return re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()


def _surface_tokens(text: str) -> set[str]:
    return {
        token
        for token in normalize(text).split()
        if token and token not in SURFACE_STOPWORDS
    }


def finding_surfaces(finding: dict[str, Any]) -> set[str]:
    """Return the surface tokens a finding points at."""
    locations = [finding.get("location") or ""]
    locations.extend(
        item.get("location") or "" for item in finding.get("evidence") or []
    )
    tokens: set[str] = set()
    for location in locations:
        tokens |= _surface_tokens(location)
    return tokens


def finding_text(finding: dict[str, Any]) -> str:
    """Return the normalized prose a formulation may be found in."""
    parts = [str(finding.get(field) or "") for field in FINDING_TEXT_FIELDS]
    parts.extend(
        str(item.get("detail") or "") for item in finding.get("evidence") or []
    )
    return normalize(" ".join(parts))


def _signal_match(formulations: list[str], text: str) -> bool:
    return any(normalize(item) and normalize(item) in text for item in formulations)


def match_strength(expected: dict[str, Any], finding: dict[str, Any]) -> str:
    """Return `full`, `partial`, or `none` for one expectation/finding pair.

    `full` needs both signals: the finding names the affected surface and
    describes the root cause in an accepted way. One signal alone is `partial`
    and is reported for adjudication rather than silently scored either way.
    """
    surface = _surface_tokens(expected.get("surface", ""))
    surface_hit = bool(surface & finding_surfaces(finding))
    signal_hit = _signal_match(
        expected.get("equivalent_formulations") or [], finding_text(finding)
    )
    if surface_hit and signal_hit:
        return "full"
    if surface_hit or signal_hit:
        return "partial"
    return "none"


def _classify_finding(
    finding: dict[str, Any],
    root_causes: list[dict[str, Any]],
    accepted: list[dict[str, Any]],
    claimed: set[str],
) -> dict[str, Any]:
    strengths = [(rc, match_strength(rc, finding)) for rc in root_causes]
    full = [rc for rc, strength in strengths if strength == "full"]
    partial = [rc for rc, strength in strengths if strength == "partial"]

    record: dict[str, Any] = {
        "finding_id": finding.get("id"),
        "severity": finding.get("severity"),
        "root_cause_id": None,
        "candidate_root_cause_ids": [],
    }
    if len(full) > 1:
        record["classification"] = "ambiguous"
        record["candidate_root_cause_ids"] = [rc["id"] for rc in full]
        return record
    if len(full) == 1:
        root_cause_id = full[0]["id"]
        record["root_cause_id"] = root_cause_id
        record["classification"] = (
            "duplicate" if root_cause_id in claimed else "matched"
        )
        return record

    text = finding_text(finding)
    for non_finding in accepted:
        if _signal_match(non_finding.get("equivalent_formulations") or [], text):
            record["classification"] = "accepted"
            record["accepted_non_finding_id"] = non_finding["id"]
            return record

    if partial:
        record["classification"] = "partial"
        record["candidate_root_cause_ids"] = [rc["id"] for rc in partial]
        return record

    record["classification"] = "unexpected"
    return record


def grade(expectation: dict[str, Any] | None, result: dict[str, Any]) -> dict[str, Any]:
    """Grade one valid review result against its private expectation."""
    if not expectation:
        raise GradingError("grading requires a private expectation for the case")

    root_causes = list(expectation.get("material_root_causes") or [])
    accepted = list(expectation.get("accepted_non_findings") or [])
    findings = [item for item in result.get("findings") or [] if isinstance(item, dict)]

    claimed: set[str] = set()
    records: list[dict[str, Any]] = []
    for finding in findings:
        record = _classify_finding(finding, root_causes, accepted, claimed)
        if record["classification"] == "matched":
            claimed.add(record["root_cause_id"])
        records.append(record)

    # Three-way scoring, settled by the owner on #58: a root cause with a
    # partial or ambiguous candidate is referred for adjudication, not counted
    # as a miss. Collapsing "unmatched because the formulation didn't
    # recognise real prose" into "the reviewer missed this" is exactly the
    # false reviewer-miss the referral bucket exists to prevent - a case is
    # only a genuine miss when nothing pointed at it at all.
    referred_ids = {
        candidate_id
        for record in records
        if record["classification"] in {"partial", "ambiguous"}
        for candidate_id in record["candidate_root_cause_ids"]
    } - claimed

    expected_ids = [rc["id"] for rc in root_causes]
    matched_ids = sorted(claimed)
    missed_ids = [
        item
        for item in expected_ids
        if item not in claimed and item not in referred_ids
    ]
    expected_verdict = expectation["expected_verdict"]
    observed_verdict = result.get("verdict")
    gating = [
        record
        for record in records
        if record["severity"] in GATING_SEVERITIES
        and record["classification"] == "unexpected"
    ]

    return {
        "grader_version": GRADER_VERSION,
        "expected_verdict": expected_verdict,
        "observed_verdict": observed_verdict,
        "verdict_match": expected_verdict == observed_verdict,
        # A miss that also reports no gating finding is the failure mode the
        # epic cares about most, so it is named rather than inferred.
        "false_clean": bool(
            expected_verdict == "changes_required" and observed_verdict == "clean"
        ),
        "false_alarm": bool(
            expected_verdict == "clean" and observed_verdict == "changes_required"
        ),
        "expected_root_cause_ids": expected_ids,
        "matched_root_cause_ids": matched_ids,
        "missed_root_cause_ids": missed_ids,
        "referred_root_cause_ids": sorted(referred_ids),
        # Recall counts confirmed matches against the full expected set, never
        # crediting a referral - a referred root cause is neither a match nor
        # a scored miss, so it is absent from both the numerator and this
        # denominator's alternative reading. It stays a lower bound: a case
        # whose only unmatched root causes were all referred reports the same
        # recall as one with genuine misses, and the referral bucket is what
        # tells the two apart.
        "recall": (len(matched_ids) / len(expected_ids)) if expected_ids else None,
        "findings": records,
        "false_positive_finding_ids": [record["finding_id"] for record in gating],
        "accepted_finding_ids": [
            record["finding_id"]
            for record in records
            if record["classification"] == "accepted"
        ],
        "duplicate_finding_ids": [
            record["finding_id"]
            for record in records
            if record["classification"] == "duplicate"
        ],
        "adjudication_required": [
            {
                "finding_id": record["finding_id"],
                "reason": record["classification"],
                "candidate_root_cause_ids": record["candidate_root_cause_ids"],
            }
            for record in records
            if record["classification"] in {"ambiguous", "partial"}
        ],
    }
