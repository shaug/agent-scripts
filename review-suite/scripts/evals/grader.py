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

GRADER_VERSION = "1.1"

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


def finding_text(finding: dict[str, Any]) -> str:
    """Return the normalized prose a formulation may be found in."""
    parts = [str(finding.get(field) or "") for field in FINDING_TEXT_FIELDS]
    parts.extend(
        str(item.get("detail") or "") for item in finding.get("evidence") or []
    )
    return normalize(" ".join(parts))


def finding_surfaces(finding: dict[str, Any]) -> set[str]:
    """Return the surface tokens a finding's structured location points at."""
    locations = [finding.get("location") or ""]
    locations.extend(
        item.get("location") or "" for item in finding.get("evidence") or []
    )
    tokens: set[str] = set()
    for location in locations:
        tokens |= _surface_tokens(location)
    return tokens


def _signal_match(formulations: list[str], text: str) -> bool:
    return any(normalize(item) and normalize(item) in text for item in formulations)


def surface_named_in_prose(expected: dict[str, Any], finding: dict[str, Any]) -> bool:
    """True when the finding's own prose names the expected surface outright.

    Checks whether the expectation's whole `surface` string, normalized to a
    phrase (`dependency_finalized` -> `"dependency finalized"`), appears as a
    contiguous substring of the finding's prose (`finding_text`: `rule`,
    `concern`, `impact`, `proposed_change`, `expected_effect`,
    `evidence[].detail`) - the same substring-of-normalized-text test
    `_signal_match` already uses for formulations, applied to the surface
    field instead.

    This is deliberately a whole-phrase check, not a token-set union with
    `finding_surfaces`. A real-runtime reviewer routinely names the exact
    affected symbol only in prose ("`x` still calls `y` without the strict
    flag") while every structured `location` field carries a bare file path
    with no symbol in it - `finding_surfaces` alone then misses a
    concretely-correct finding entirely (discovered by reading raw attempts
    where 10/10 correctly-reasoned findings on two real cases were
    misclassified `unexpected` for exactly this reason). But a naive token-set
    union of prose into `finding_surfaces` is too loose: this repository's own
    `probe.partial-claim-wrong-surface` calibration case deliberately puts a
    finding at the wrong surface (`storectl/cli.py`, not
    `render_rollback_guidance`) whose prose incidentally contains the single
    common word "guidance" ("the guidance cannot run") - a token-set union
    would credit that coincidence as a surface hit and silently break a
    calibration boundary built to keep a partially-correct, wrong-surface
    claim referred rather than matched. Requiring the whole normalized surface
    phrase to appear keeps that boundary intact (a lone "guidance" is not
    "render rollback guidance") while still catching a real reviewer that
    plainly names the exact symbol.

    Implemented as `_signal_match` on a single-item formulations list rather
    than a second, separately-written normalize/substring check: it is the
    exact same rule (including the same falsy-formulation guard, so an
    empty or missing `surface` field correctly never matches), and reusing it
    keeps only one place that rule can drift.
    """
    return _signal_match([expected.get("surface", "")], finding_text(finding))


def match_signals(
    expected: dict[str, Any], finding: dict[str, Any]
) -> tuple[bool, bool]:
    """Return `(surface_hit, signal_hit)` for one expectation/finding pair.

    `surface_hit` is the concrete signal: the finding's location, evidence, or
    own prose names the expectation's `surface` - the actual file, function,
    or symbol the root cause turns on - via `finding_surfaces` (structured
    locations) or `surface_named_in_prose` (the whole surface phrase named
    outright in the finding's explanation). `signal_hit` is the
    accepted-formulation prose match alone, which vaguer commentary can
    satisfy without ever naming where the defect lives. Split out from
    `match_strength` so a referred (partial or ambiguous) candidate can be
    judged concrete or not, rather than only judged matched or not.
    """
    surface = _surface_tokens(expected.get("surface", ""))
    surface_hit = bool(surface & finding_surfaces(finding)) or surface_named_in_prose(
        expected, finding
    )
    signal_hit = _signal_match(
        expected.get("equivalent_formulations") or [], finding_text(finding)
    )
    return surface_hit, signal_hit


def match_strength(expected: dict[str, Any], finding: dict[str, Any]) -> str:
    """Return `full`, `partial`, or `none` for one expectation/finding pair.

    `full` needs both signals: the finding names the affected surface and
    describes the root cause in an accepted way. One signal alone is `partial`
    and is reported for adjudication rather than silently scored either way.
    """
    surface_hit, signal_hit = match_signals(expected, finding)
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
    # Referred-path relevance guard (settled by the repository owner in #53's
    # preregistered v2 scoring gate): a referred candidate only counts toward
    # the combined matched+referred rate if this finding concretely names the
    # candidate's actual surface, not merely if the grader marked it ambiguous
    # or partial. `full` always implies surface_hit by construction, so an
    # ambiguous candidate (two `full` matches) is always relevant; a `partial`
    # candidate is relevant only when its own surface signal fired.
    surface_relevant = {rc["id"] for rc in root_causes if match_signals(rc, finding)[0]}

    record: dict[str, Any] = {
        "finding_id": finding.get("id"),
        "severity": finding.get("severity"),
        "root_cause_id": None,
        "candidate_root_cause_ids": [],
        "candidate_surface_relevant_root_cause_ids": [],
    }
    if len(full) > 1:
        record["classification"] = "ambiguous"
        record["candidate_root_cause_ids"] = [rc["id"] for rc in full]
        record["candidate_surface_relevant_root_cause_ids"] = sorted(
            surface_relevant & {rc["id"] for rc in full}
        )
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
        record["candidate_surface_relevant_root_cause_ids"] = sorted(
            surface_relevant & {rc["id"] for rc in partial}
        )
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

    # Referred-path relevance guard: the subset of `referred_ids` where some
    # referring finding concretely named the candidate's surface, rather than
    # only matching on accepted-formulation prose or being marked ambiguous.
    # `claimed` is not re-subtracted here beyond what `referred_ids` already
    # excludes, since relevant ids are always a subset of referred ids.
    relevant_referred_ids = {
        candidate_id
        for record in records
        if record["classification"] in {"partial", "ambiguous"}
        for candidate_id in record.get("candidate_surface_relevant_root_cause_ids", [])
    } & referred_ids

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
        # Referred-path relevance guard, settled by the repository owner in
        # #53's preregistered v2 scoring gate: the subset of
        # `referred_root_cause_ids` where a referring finding concretely named
        # the candidate's actual surface. A referred candidate that only hit
        # on prose (vaguer commentary echoing an accepted formulation without
        # ever pointing at the right place) is excluded here even though it is
        # still reported under `referred_root_cause_ids` above.
        "referred_relevant_root_cause_ids": sorted(relevant_referred_ids),
        # Recall counts confirmed matches against the full expected set, never
        # crediting a referral - a referred root cause is neither a match nor
        # a scored miss, so it is absent from both the numerator and this
        # denominator's alternative reading. It stays a lower bound: a case
        # whose only unmatched root causes were all referred reports the same
        # recall as one with genuine misses, and the referral bucket is what
        # tells the two apart.
        "recall": (len(matched_ids) / len(expected_ids)) if expected_ids else None,
        # Combined matched+referred rate with the relevance guard applied:
        # the preregistered v2 scoring gate's alternative path to a passing
        # case when `recall` alone falls short. `matched_ids` and
        # `relevant_referred_ids` are disjoint by construction (the latter is
        # already `referred_ids - claimed`, and `referred_ids` itself excludes
        # `claimed`), so a plain sum is exact, not an overcount.
        "combined_recall": (
            (len(matched_ids) + len(relevant_referred_ids)) / len(expected_ids)
        )
        if expected_ids
        else None,
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
