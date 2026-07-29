#!/usr/bin/env python3
"""Grader calibration sets: probe reviews and the classification each must get.

A grader that has never been shown real reviewer prose is not calibrated, it is
guessed. The reference grader matches an observed finding against a private root
cause by containment on normalised text, so a formulation written before any run
existed can be a perfectly reasonable sentence and still recognise nothing.
Calibration closes that gap from the only honest direction: run the unscored
pilot, read what the reviewer actually wrote, and pin the formulations to that
prose.

Because tightening formulations makes recall go up, calibration is also the
easiest place to accidentally manufacture a good score. Two rules keep it
honest, and both are enforced here rather than left to intent:

- a calibration set states where its probe prose came from, and an `observed`
  probe must be prose a real reviewer returned; and
- calibration is derived from pilot output only. Tuning a formulation after
  seeing scored output would be fitting the grader to the answer, which is why
  the pilot corpus is disjoint from every scored stratum.

A calibration set is private grading evidence. It lives outside every corpus's
`reviewer/` tree and cannot reach an executor payload.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import corpus, protocol

CALIBRATION_ROOT = protocol.REVIEW_SUITE / "evals" / "calibration"

#: The grading boundaries a calibration set must probe. Recognising real prose
#: is only half of calibration: a formulation loose enough to match anything
#: would score an overlapping symptom, a partial claim, or a plausible false
#: positive as a correct answer.
REQUIRED_PROBE_KINDS = frozenset(
    {
        "observed",
        "paraphrase",
        "overlapping_symptom",
        "duplicate_report",
        "partial_claim",
        "plausible_false_positive",
    }
)

#: What each kind must actually demonstrate, as (classifications, must charge a
#: false positive). Coverage alone is not calibration: a set could ship a
#: `plausible_false_positive` probe whose own expectation declares `partial` with
#: no false positive charged, and pass a test that only checks the kind exists.
#: Given that a surface hit needs one shared token, that is the path of least
#: resistance for any wrong finding inside the changed file, so the required
#: outcome is asserted here rather than left to the set's own claim.
PROBE_KIND_CONTRACT: dict[str, tuple[frozenset[str], bool]] = {
    "observed": (frozenset({"matched"}), False),
    "paraphrase": (frozenset({"matched"}), False),
    "overlapping_symptom": (frozenset({"partial"}), False),
    "duplicate_report": (frozenset({"matched", "duplicate"}), False),
    "partial_claim": (frozenset({"partial"}), False),
    "plausible_false_positive": (frozenset({"unexpected"}), True),
    "surface_token_collision": (frozenset({"partial"}), False),
    "accepted_non_finding": (frozenset({"accepted"}), False),
}


class CalibrationError(ValueError):
    """Raised when a calibration set cannot be trusted to calibrate anything."""


@dataclass(frozen=True)
class CalibrationSet:
    path: Path
    case_id: str
    grader_version: str
    source: str
    probes: tuple[dict[str, Any], ...]

    @property
    def kinds(self) -> frozenset[str]:
        return frozenset(probe["kind"] for probe in self.probes)


def probe_result(probe: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    """Render one probe as a review result bound to the case's candidate."""
    return {
        "schema_version": "1.1",
        "lens": "aggregate",
        "candidate": candidate,
        "verdict": probe["verdict"],
        "findings": probe["findings"],
        "blocking_reasons": [],
    }


def load_set(path: Path) -> CalibrationSet:
    """Load and validate one calibration set, failing closed on any problem."""
    document = json.loads(path.read_text())
    errors = protocol.validate_against("calibration.schema.json", document)
    if document.get("case_id") != path.stem:
        errors.append(f"case_id does not match the filename {path.stem!r}")
    identifiers = [probe.get("id") for probe in document.get("probes") or []]
    duplicates = sorted({i for i in identifiers if identifiers.count(i) > 1})
    if duplicates:
        errors.append("duplicate probe id(s): " + ", ".join(duplicates))
    if errors:
        raise CalibrationError(f"{path.name}: " + "; ".join(errors))
    return CalibrationSet(
        path=path,
        case_id=document["case_id"],
        grader_version=document["grader_version"],
        source=document["source"],
        probes=tuple(document["probes"]),
    )


def load_sets() -> dict[str, CalibrationSet]:
    """Load every shipped calibration set, keyed by case identifier."""
    if not CALIBRATION_ROOT.is_dir():
        return {}
    return {
        path.stem: load_set(path) for path in sorted(CALIBRATION_ROOT.glob("*.json"))
    }


def cases_by_id() -> dict[str, list[tuple[str, corpus.Case]]]:
    """Index every case in every shipped corpus by identifier.

    A case identifier may appear in more than one corpus: the pilot strata carry
    one identical case so that the declared skill closure is the only difference
    between them. Calibration is a property of the case and its expectation, not
    of the corpus that happens to hold it, so the index keeps every occurrence
    and callers assert the expectations agree.
    """
    index: dict[str, list[tuple[str, corpus.Case]]] = {}
    for root in corpus.corpus_roots():
        loaded = corpus.load_corpus(root)
        for case in loaded.cases:
            index.setdefault(case.case_id, []).append((root.name, case))
    return index
