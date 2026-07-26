#!/usr/bin/env python3
"""Versioned, result-blind corpus contract for review replay evaluation.

The layout physically separates the three kinds of data so a reviewer-visible
read can never reach grading evidence:

    <corpus>/corpus.json                        version metadata, case ids
    <corpus>/reviewer/PROMPT.md                 shared reviewer instructions
    <corpus>/reviewer/<case>/packet.json        reviewer-visible artifacts
    <corpus>/private/expectations/<case>.json   expected material root causes
    <corpus>/private/provenance/<case>.json     origin and retention authority

Loading fails closed. A missing expectation, a malformed schema, an orphaned
file, or an outcome-revealing identifier is an error before any executor
process is started.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import protocol

DEFAULT_CORPUS = protocol.REVIEW_SUITE / "evals" / "corpus"
REVIEWER_PROMPT = "PROMPT.md"

#: Filenames permitted inside a reviewer-visible case directory. Anything else
#: risks shipping grading evidence to the target reviewer.
REVIEWER_CASE_FILES = frozenset({"packet.json"})

#: Substrings that would reveal a verdict, severity, failure class, connector
#: disposition, or target finding through a case id or reviewer-visible
#: filename. Case names must describe the subject matter, never the answer.
OUTCOME_REVEALING_TOKENS = (
    "accept",
    "blocked",
    "blocking",
    "broken",
    "bug",
    "changes",
    "clean",
    "control",
    "defect",
    "defer",
    "duplicate",
    "escape",
    "expected",
    "fail",
    "false",
    "flaw",
    "insecure",
    "invalid",
    "miss",
    "negative",
    "overengineered",
    "polish",
    "positive",
    "regression",
    "reject",
    "severity",
    "simplif",
    "speculative",
    "unsafe",
    "verdict",
    "vulnerab",
)


@dataclass(frozen=True)
class Case:
    """One corpus case with its three separately validated parts."""

    case_id: str
    packet: dict[str, Any]
    instructions: str
    expectation: dict[str, Any]
    provenance: dict[str, Any]

    @property
    def case_ref(self) -> str:
        return protocol.case_ref(self.case_id)


@dataclass(frozen=True)
class Corpus:
    root: Path
    corpus_version: str
    grader_version: str
    target_skill: str
    cases: tuple[Case, ...]


class CorpusError(ValueError):
    """Raised when the corpus cannot be trusted for a blind evaluation."""


def _load_json(path: Path) -> Any:
    if not path.is_file():
        raise CorpusError(f"missing {path}")
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as error:
        raise CorpusError(f"invalid JSON in {path}: {error}") from error


def revealing_tokens(name: str) -> list[str]:
    """Return the outcome-revealing substrings present in one name."""
    lowered = name.lower()
    return [token for token in OUTCOME_REVEALING_TOKENS if token in lowered]


def _expectation_semantics(expectation: dict[str, Any]) -> list[str]:
    """Cross-field expectation rules JSON Schema cannot express clearly."""
    errors = []
    verdict = expectation.get("expected_verdict")
    root_causes = expectation.get("material_root_causes") or []
    packet_valid = expectation.get("packet_valid")

    if verdict == "changes_required" and not root_causes:
        errors.append("changes_required requires at least one material root cause")
    if verdict == "clean" and root_causes:
        errors.append("clean cannot expect a material root cause")
    if verdict == "blocked":
        if root_causes:
            errors.append("blocked cannot expect a material root cause")
        if packet_valid is not False:
            errors.append("blocked requires packet_valid false")
    elif packet_valid is not True:
        errors.append(f"{verdict} requires packet_valid true")

    for field, prefix in (
        ("material_root_causes", "rc"),
        ("accepted_non_findings", "anf"),
    ):
        identifiers = [item.get("id") for item in expectation.get(field) or []]
        duplicates = sorted({i for i in identifiers if identifiers.count(i) > 1})
        if duplicates:
            errors.append(f"duplicate {prefix} id(s): " + ", ".join(duplicates))
    return errors


def load_case(root: Path, case_id: str) -> Case:
    """Load and validate one case's reviewer-visible and private parts."""
    errors: list[str] = []

    tokens = revealing_tokens(case_id)
    if tokens:
        errors.append(
            f"case id reveals outcome via {', '.join(tokens)}; "
            "name cases after their subject matter"
        )

    reviewer_dir = root / "reviewer" / case_id
    if not reviewer_dir.is_dir():
        raise CorpusError(f"missing reviewer directory {reviewer_dir}")
    for path in sorted(reviewer_dir.iterdir()):
        if path.name not in REVIEWER_CASE_FILES:
            errors.append(f"unpermitted reviewer-visible file {path}")
        file_tokens = revealing_tokens(path.name)
        if file_tokens:
            errors.append(
                f"reviewer-visible filename {path.name} reveals outcome via "
                + ", ".join(file_tokens)
            )

    packet = _load_json(reviewer_dir / "packet.json")
    expectation = _load_json(root / "private" / "expectations" / f"{case_id}.json")
    provenance = _load_json(root / "private" / "provenance" / f"{case_id}.json")

    for name, document, schema in (
        ("expectation", expectation, "expectation.schema.json"),
        ("provenance", provenance, "provenance.schema.json"),
    ):
        errors.extend(
            f"{name}: {error}" for error in protocol.validate_against(schema, document)
        )
        if document.get("case_id") != case_id:
            errors.append(f"{name}: case_id does not match {case_id}")

    errors.extend(
        f"expectation: {error}" for error in _expectation_semantics(expectation)
    )

    packet_errors = protocol.VALIDATOR.validate_packet(packet)
    if expectation.get("packet_valid") and packet_errors:
        errors.extend(f"packet: {error}" for error in packet_errors)
    elif expectation.get("packet_valid") is False and not packet_errors:
        errors.append("packet: packet_valid false but the packet validates")

    if errors:
        raise CorpusError(f"{case_id}: " + "; ".join(errors))

    instructions = (root / "reviewer" / REVIEWER_PROMPT).read_text()
    return Case(
        case_id=case_id,
        packet=packet,
        instructions=instructions,
        expectation=expectation,
        provenance=provenance,
    )


def _orphan_errors(root: Path, declared: set[str]) -> list[str]:
    """Report corpus files that no declared case owns, in both directions."""
    errors = []
    reviewer_root = root / "reviewer"
    present = {path.name for path in reviewer_root.iterdir() if path.is_dir()}
    for extra in sorted(present - declared):
        errors.append(f"reviewer/{extra} is not declared in corpus.json")
    for subdir, suffix in (("expectations", ".json"), ("provenance", ".json")):
        directory = root / "private" / subdir
        if not directory.is_dir():
            errors.append(f"missing {directory}")
            continue
        names = {path.name[: -len(suffix)] for path in directory.glob(f"*{suffix}")}
        for extra in sorted(names - declared):
            errors.append(f"private/{subdir}/{extra}{suffix} is not declared")
    return errors


def load_corpus(root: Path | None = None) -> Corpus:
    """Load the whole corpus, failing closed on any integrity problem."""
    root = Path(root) if root else DEFAULT_CORPUS
    if not root.is_dir():
        raise CorpusError(f"missing corpus directory {root}")
    index = _load_json(root / "corpus.json")
    schema_errors = protocol.validate_against("corpus.schema.json", index)
    if schema_errors:
        raise CorpusError("corpus.json: " + "; ".join(schema_errors))
    if not (root / "reviewer" / REVIEWER_PROMPT).is_file():
        raise CorpusError(f"missing {root / 'reviewer' / REVIEWER_PROMPT}")

    declared = list(index["cases"])
    if len(set(declared)) != len(declared):
        raise CorpusError("corpus.json: duplicate case id(s)")
    orphans = _orphan_errors(root, set(declared))
    if orphans:
        raise CorpusError("corpus.json: " + "; ".join(orphans))

    return Corpus(
        root=root,
        corpus_version=index["corpus_version"],
        grader_version=index["grader_version"],
        target_skill=index["target_skill"],
        cases=tuple(load_case(root, case_id) for case_id in declared),
    )


#: Verdict and severity names the shared reviewer prompt must not mention.
PROMPT_FORBIDDEN_WORDS = frozenset(
    {
        "blocked",
        "blocking",
        "changes_required",
        "clean",
        "defer",
        "strong_recommendation",
    }
)


def prompt_errors(root: Path | None = None) -> list[str]:
    """Reject shared reviewer instructions that hint at an expected outcome."""
    root = Path(root) if root else DEFAULT_CORPUS
    text = (root / "reviewer" / REVIEWER_PROMPT).read_text()
    words = set(re.findall(r"[a-z_]+", text.lower()))
    hits = sorted(words & PROMPT_FORBIDDEN_WORDS)
    if not hits:
        return []
    return ["reviewer prompt names verdict or severity word(s): " + ", ".join(hits)]
