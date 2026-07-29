#!/usr/bin/env python3
"""Connector-outcome curation and promotion-decision contract.

This module operationalizes future learning from adjudicated connector
findings, kept strictly separate from the result-blind replay corpus that
`corpus.py` owns:

    curation record   one adjudicated connector claim, its disposition, its
                      public and private evidence, and (for a duplicate) why
                      it is still retained.
    promotion decision the narrowest-owner decision a group of curation
                      records supports: a corpus case only, a global rubric
                      change, a repository-instruction change, or nothing.

A curation record is never itself an executor payload and never becomes a
corpus case by this module alone - #56's own non-goals forbid recreating or
re-adjudicating the #58 corpus here. This module only proves the intake and
promotion tooling is real, tested, and fails closed; populating it with real
adjudicated connector history is separate, later work with its own evidence.

## The disclosure guardrail

When a curation record's `public.provenance.source_class` is
`private_authorized`, its `source_description` must be one of the generic
phrases in `disclosure-guardrail.json`'s `allowed_source_descriptions`, and
must not contain a path-like token (`/`), a bare hostname, or any string
matching that file's `denylisted_identifiers`. This is a cheap, mechanical
backstop for the disclosure boundary this workflow depends on: curation
discipline alone (choosing a generic description) has already been shown,
elsewhere in this repository, not to reliably catch every leak on its own.
The guardrail is scoped to `private_authorized` records specifically, because
that is the one disclosure risk a generic public description exists to
guard - a `synthetic` or `repository_history` record's description is
already whatever this repository's own history actually is.

## Reviewer/private separation

A curation record keeps `public` and `private` in one file rather than three
directories the way a replay-corpus case does, because a curation record is
reviewed by a human curator through an ordinary pull request, not shipped to
an executor. Separation is still enforced, not merely conventional:
`reviewer_private_separation_errors` rejects a record whose private
administrative or grading text (retention authority, owner, source
identity, expected root cause, accepted non-finding) appears verbatim inside
its own public section.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import protocol

DEFAULT_RECORDS = protocol.REVIEW_SUITE / "evals" / "curation" / "records"
DEFAULT_PROMOTIONS = protocol.REVIEW_SUITE / "evals" / "curation" / "promotions"
INVALID_FIXTURES = protocol.REVIEW_SUITE / "evals" / "curation" / "fixtures" / "invalid"
GUARDRAIL_CONFIG = protocol.EVAL_CONTRACTS / "disclosure-guardrail.json"

#: Dispositions an accepted material outcome may declare. These, and only
#: these, may support a promotion decision's `positive_case_ids`.
ACCEPTED_DISPOSITIONS = (
    "accepted_material_defect",
    "accepted_acceptance_miss",
    "accepted_validation_gap",
)

#: Dispositions whose rejected/deferred tuning evidence may support a
#: promotion decision's `negative_control_case_ids`.
REJECTED_TUNING_DISPOSITIONS = (
    "rejected_false_positive",
    "rejected_non_causal",
    "deferred_hardening",
)

REPOSITORY_INSTRUCTION_BASENAMES = frozenset({"AGENTS.md", "CLAUDE.md"})

#: A generic "word.tld"-shaped token. Deliberately permissive: a hostname
#: guardrail exists to fail closed on a plausible leak, not to guess exactly
#: which strings are real hostnames. Requires a two-letter-or-longer final
#: label so short numeric or single-letter abbreviations (e.g. "e.g.", "v1.0")
#: do not trip it.
HOSTNAME_PATTERN = re.compile(
    r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.[a-zA-Z]{2,}"
)


class CurationError(ValueError):
    """Raised when a curation record or promotion decision cannot be trusted."""


def _load_json(path: Path) -> Any:
    if not path.is_file():
        raise CurationError(f"missing {path}")
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as error:
        raise CurationError(f"invalid JSON in {path}: {error}") from error


def load_guardrail_config(path: Path | None = None) -> dict[str, Any]:
    """Load the disclosure guardrail's allow-list and deny-list."""
    return _load_json(Path(path) if path else GUARDRAIL_CONFIG)


def disclosure_guardrail_errors(
    record: dict[str, Any], *, guardrail: dict[str, Any] | None = None
) -> list[str]:
    """Fail closed on a `private_authorized` record's disclosure risk.

    JSON Schema's `enum` could pin the allow-list, but only unconditionally -
    this repository's schema-subset validator has no conditional keyword (see
    `corpus._provenance_semantics` for the precedent), and the allow-list only
    applies when `source_class` is `private_authorized`. Checked here instead.
    """
    provenance = record.get("public", {}).get("provenance", {})
    if provenance.get("source_class") != "private_authorized":
        return []

    guardrail = guardrail if guardrail is not None else load_guardrail_config()
    description = provenance.get("source_description", "")
    errors: list[str] = []

    allowed = guardrail.get("allowed_source_descriptions", [])
    if description not in allowed:
        errors.append(
            "public.provenance.source_description must be one of the allow-listed "
            f"generic phrases for source_class private_authorized: {allowed!r}, got "
            f"{description!r}"
        )
    if "/" in description:
        errors.append(
            "public.provenance.source_description contains a path-like token ('/')"
        )
    if HOSTNAME_PATTERN.search(description):
        errors.append(
            "public.provenance.source_description contains a bare hostname-shaped token"
        )
    denylist = guardrail.get("denylisted_identifiers", [])
    hits = sorted(
        {token for token in denylist if token and token.lower() in description.lower()}
    )
    if hits:
        errors.append(
            "public.provenance.source_description matches a deny-listed identifier: "
            + ", ".join(hits)
        )
    return errors


def _private_text_fragments(record: dict[str, Any]) -> list[str]:
    private = record.get("private", {})
    provenance = private.get("provenance", {})
    fragments = [
        provenance.get("retention_authority"),
        provenance.get("owner"),
        provenance.get("source_identity"),
        private.get("expected_root_cause"),
        private.get("accepted_non_finding"),
    ]
    return [fragment for fragment in fragments if fragment]


def reviewer_private_separation_errors(record: dict[str, Any]) -> list[str]:
    """Reject private text that also appears verbatim in the public section."""
    public_text = json.dumps(record.get("public", {})).lower()
    errors = []
    for fragment in _private_text_fragments(record):
        normalized = fragment.strip().lower()
        if normalized and normalized in public_text:
            errors.append(
                f"private text appears verbatim in the public section: {fragment!r}"
            )
    return errors


def _disposition_semantics(record: dict[str, Any]) -> list[str]:
    """Cross-field disposition rules JSON Schema cannot express.

    Accepted/rejected/deferred, duplicate, and unresolved dispositions must
    validate distinctly: an accepted disposition requires the private root
    cause a future positive case needs; a rejected or deferred disposition
    requires the private accepted non-finding a future negative control needs;
    duplicate and unresolved must declare neither, because neither has settled
    what a positive or negative case would even record yet.
    """
    errors: list[str] = []
    disposition = record.get("disposition")
    duplicate_of = record.get("duplicate_of")
    distinct_contribution = record.get("distinct_contribution")
    private = record.get("private", {})

    if disposition == "duplicate":
        if not duplicate_of:
            errors.append("disposition duplicate requires duplicate_of")
        elif duplicate_of == record.get("record_id"):
            errors.append("duplicate_of cannot reference its own record_id")
    else:
        if duplicate_of:
            errors.append(
                f"duplicate_of is only valid when disposition is duplicate, not "
                f"{disposition!r}"
            )
        if distinct_contribution:
            errors.append(
                f"distinct_contribution is only valid when disposition is duplicate, "
                f"not {disposition!r}"
            )

    if disposition in ACCEPTED_DISPOSITIONS and not private.get("expected_root_cause"):
        errors.append(
            f"disposition {disposition!r} requires private.expected_root_cause"
        )
    if disposition in REJECTED_TUNING_DISPOSITIONS and not private.get(
        "accepted_non_finding"
    ):
        errors.append(
            f"disposition {disposition!r} requires private.accepted_non_finding"
        )
    if disposition in ("unresolved", "duplicate"):
        if private.get("expected_root_cause") or private.get("accepted_non_finding"):
            errors.append(
                f"disposition {disposition!r} must not declare a private root cause or "
                "accepted non-finding before adjudication settles it"
            )
    return errors


def validate_record(document: dict[str, Any]) -> list[str]:
    """Validate one curation record: schema, disclosure, separation, semantics."""
    errors = list(protocol.validate_against("curation-record.schema.json", document))
    if errors:
        return errors
    errors.extend(disclosure_guardrail_errors(document))
    errors.extend(reviewer_private_separation_errors(document))
    errors.extend(_disposition_semantics(document))
    return errors


@dataclass(frozen=True)
class RecordSet:
    root: Path
    records: dict[str, dict[str, Any]]


def load_records(root: Path | None = None) -> RecordSet:
    """Load and validate every curation record in a directory, failing closed.

    Cross-record referential integrity (a `duplicate_of` must actually exist)
    can only be checked once every record is loaded, so it happens here rather
    than in `validate_record`.
    """
    root = Path(root) if root else DEFAULT_RECORDS
    if not root.is_dir():
        raise CurationError(f"missing curation records directory {root}")

    records: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for path in sorted(root.glob("*.json")):
        document = _load_json(path)
        record_id = document.get("record_id")
        if record_id != path.stem:
            errors.append(
                f"{path.name}: record_id {record_id!r} does not match filename"
            )
        record_errors = validate_record(document)
        if record_errors:
            errors.append(f"{path.name}: " + "; ".join(record_errors))
            continue
        if record_id in records:
            errors.append(f"duplicate record_id {record_id!r}")
            continue
        records[record_id] = document

    if errors:
        raise CurationError("; ".join(errors))

    for record_id, document in records.items():
        duplicate_of = document.get("duplicate_of")
        if duplicate_of and duplicate_of not in records:
            errors.append(f"{record_id}: duplicate_of {duplicate_of!r} does not exist")
    if errors:
        raise CurationError("; ".join(errors))

    return RecordSet(root=root, records=records)


def _resolve_duplicate_disposition(
    record_id: str, records: dict[str, dict[str, Any]]
) -> tuple[str | None, str | None]:
    """Follow `duplicate_of` to the disposition a duplicate's role must match.

    A `duplicate` record carries no `expected_root_cause` or
    `accepted_non_finding` of its own - the schema forbids both - so whether it
    may fill a positive or negative promotion slot depends entirely on the
    disposition of the record it actually restates, followed through however
    many `duplicate` hops it takes to reach one. Returns `(None, None)` when
    the chain is missing a record or cycles back on itself; callers must treat
    that as a validation error rather than silently permitting the duplicate.
    """
    seen: set[str] = set()
    current = record_id
    while True:
        record = records.get(current)
        if record is None or current in seen:
            return None, None
        disposition = record.get("disposition")
        if disposition != "duplicate":
            return current, disposition
        seen.add(current)
        duplicate_of = record.get("duplicate_of")
        if not duplicate_of:
            return None, None
        current = duplicate_of


def _promotable_errors(
    record_id: str,
    record: dict[str, Any],
    records: dict[str, dict[str, Any]],
    *,
    as_positive: bool,
) -> list[str]:
    """Whether one record may support a positive or negative promotion slot.

    Unresolved claims can never enter grading expectations or modify active
    review guidance. A duplicate without a recorded distinct contribution can
    never be promoted either - promoting it would double-count the root cause
    it shares with the record it duplicates. A duplicate *with* a distinct
    contribution may only fill the positive/negative role its resolved
    root-cause record actually supports - a distinct duplicate of a rejected
    claim is still evidence the claim was rejected, not a second accepted
    outcome, and vice versa. Once resolved, a direct record and a resolved
    duplicate share exactly one disposition-membership check below; only the
    error message's phrasing differs, selected by whether the resolved id is
    the record's own id.
    """
    disposition = record.get("disposition")
    if disposition == "unresolved":
        return [
            f"{record_id}: unresolved claims cannot enter grading expectations or "
            "modify active review guidance"
        ]

    if disposition == "duplicate":
        if not record.get("distinct_contribution"):
            return [
                f"{record_id}: a duplicate without a distinct trigger, surface, or "
                "negative control cannot be promoted without double-counting its root "
                "cause"
            ]
        effective_id, effective_disposition = _resolve_duplicate_disposition(
            record_id, records
        )
        if effective_disposition is None:
            return [
                f"{record_id}: duplicate_of chain could not be resolved to a "
                "non-duplicate disposition (a missing record or a cycle)"
            ]
        if effective_disposition == "unresolved":
            return [
                f"{record_id}: duplicates an unresolved claim ({effective_id!r}), "
                "which cannot enter grading expectations or modify active review "
                "guidance either"
            ]
    else:
        effective_id, effective_disposition = record_id, disposition

    if as_positive and effective_disposition not in ACCEPTED_DISPOSITIONS:
        if effective_id == record_id:
            return [
                f"{record_id}: disposition {effective_disposition!r} is not an "
                "accepted material outcome and cannot support a positive regression "
                "case"
            ]
        return [
            f"{record_id}: duplicates {effective_id!r} whose disposition "
            f"{effective_disposition!r} is not an accepted material outcome, so it "
            "cannot support a positive regression case"
        ]
    if not as_positive and effective_disposition not in REJECTED_TUNING_DISPOSITIONS:
        if effective_id == record_id:
            return [
                f"{record_id}: disposition {effective_disposition!r} is not "
                "rejected/deferred tuning evidence and cannot support a negative "
                "control"
            ]
        return [
            f"{record_id}: duplicates {effective_id!r} whose disposition "
            f"{effective_disposition!r} is not rejected/deferred tuning evidence, "
            "so it cannot support a negative control"
        ]
    return []


def _metric_semantics(metric: dict[str, Any], label: str) -> list[str]:
    errors = []
    for field in ("recall", "false_positive_rate", "stability", "latency_seconds"):
        value = metric.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            errors.append(f"evidence.{label}.{field} must be a number")

    cost = metric.get("cost", {})
    has_usd = "usd" in cost
    unavailable = cost.get("unavailable")
    if has_usd and unavailable:
        errors.append(f"evidence.{label}.cost cannot be both reported and unavailable")
    elif not has_usd and not unavailable:
        errors.append(
            f"evidence.{label}.cost must report usd or an explicit unavailable reason"
        )
    elif unavailable and not cost.get("reason"):
        errors.append(f"evidence.{label}.cost.unavailable requires a reason")
    elif has_usd and (
        isinstance(cost.get("usd"), bool)
        or not isinstance(cost.get("usd"), (int, float))
    ):
        errors.append(f"evidence.{label}.cost.usd must be a number")
    return errors


def _evidence_semantics(evidence: dict[str, Any]) -> list[str]:
    errors = []
    for label in ("before", "after"):
        metric = evidence.get(label)
        if not isinstance(metric, dict):
            errors.append(f"evidence.{label} is required")
            continue
        errors.extend(_metric_semantics(metric, label))
    return errors


def validate_promotion_decision(
    document: dict[str, Any], records: dict[str, dict[str, Any]]
) -> list[str]:
    """Validate one promotion decision against the loaded curation records."""
    errors = list(protocol.validate_against("promotion-decision.schema.json", document))
    if errors:
        return errors

    decision = document["decision"]
    target = document.get("target")
    positive_ids = document.get("positive_case_ids", [])
    negative_ids = document.get("negative_control_case_ids", [])

    for record_id in positive_ids:
        if record_id not in records:
            errors.append(f"positive_case_ids: unknown record {record_id!r}")
            continue
        errors.extend(
            _promotable_errors(record_id, records[record_id], records, as_positive=True)
        )
    for record_id in negative_ids:
        if record_id not in records:
            errors.append(f"negative_control_case_ids: unknown record {record_id!r}")
            continue
        errors.extend(
            _promotable_errors(
                record_id, records[record_id], records, as_positive=False
            )
        )
    overlap = sorted(set(positive_ids) & set(negative_ids))
    if overlap:
        errors.append(
            "record(s) listed as both positive and negative: " + ", ".join(overlap)
        )

    requires_target = decision in (
        "global_rubric_update",
        "repository_instruction_update",
    )
    if requires_target and not target:
        errors.append(f"decision {decision!r} requires a target")
    if not requires_target and target:
        errors.append(f"decision {decision!r} must not declare a target")

    if target:
        if decision == "global_rubric_update" and target["kind"] != "global_rubric":
            errors.append("global_rubric_update requires target.kind global_rubric")
        if (
            decision == "repository_instruction_update"
            and target["kind"] != "repository_instruction"
        ):
            errors.append(
                "repository_instruction_update requires target.kind "
                "repository_instruction"
            )

    if decision == "global_rubric_update":
        valid_positive = [
            record_id for record_id in positive_ids if record_id in records
        ]
        surfaces = {
            records[record_id]["public"]["affected_surface"]
            for record_id in valid_positive
        }
        if len(valid_positive) < 2 or len(surfaces) < 2:
            errors.append(
                "global_rubric_update requires at least two representative positive "
                "cases across distinct affected surfaces, supported by more than one "
                "positive plus relevant negative controls"
            )
        if not negative_ids:
            errors.append("global_rubric_update requires at least one negative control")

    if decision == "repository_instruction_update" and target:
        path = target["path"]
        if Path(path).name not in REPOSITORY_INSTRUCTION_BASENAMES:
            errors.append(
                "repository_instruction_update must target an existing "
                "repository-owned instruction mechanism (AGENTS.md or CLAUDE.md), not "
                f"a new one: {path!r}"
            )
        elif not (protocol.REPOSITORY_ROOT / path).is_file():
            errors.append(
                f"repository_instruction_update target does not exist: {path!r}"
            )

    errors.extend(_evidence_semantics(document.get("evidence", {})))
    return errors
