#!/usr/bin/env python3
"""Validate repository-owned review packets and results."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent


def _schema_file(name: str) -> Path:
    """Locate a schema in either supported layout.

    Canonical layout: review-suite/scripts/validate.py with schemas under
    review-suite/contracts/. Bundled layout (installed review skills):
    references/review-suite/validate.py with the schemas beside it.
    """
    for candidate in (HERE / name, HERE.parent / "contracts" / name):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"Cannot locate {name} beside {HERE} or in {HERE.parent / 'contracts'}"
    )


SCHEMAS = {
    "packet": _schema_file("review-packet.schema.json"),
    "result": _schema_file("review-result.schema.json"),
}

BLOCKABLE_PACKET_ERROR_PATTERNS = (
    re.compile(
        r"^\$: missing required property "
        r"'(repository|candidate|change_contract|sources|validation)'$"
    ),
    re.compile(r"^\$\.repository: missing required property '(identity|base_branch)'$"),
    re.compile(
        r"^\$\.candidate: missing required property "
        r"'(head_sha|comparison_base_sha|diff)'$"
    ),
    re.compile(
        r"^\$\.candidate\.diff: missing required property "
        r"'(format|complete|content)'$"
    ),
    re.compile(r"^\$\.candidate\.diff\.complete: expected constant True$"),
    re.compile(r"^\$\.candidate\.diff\.content: string is too short$"),
    re.compile(
        r"^\$\.change_contract: missing required property "
        r"'(goal|acceptance_criteria|non_goals|preserved_behaviors)'$"
    ),
    re.compile(r"^\$\.change_contract\.goal: string is too short$"),
    re.compile(
        r"^\$\.change_contract\.acceptance_criteria: "
        r"expected at least 1 item\(s\)$"
    ),
    re.compile(r"^\$\.sources: missing required property "),
    re.compile(r"^\$\.validation: expected at least 1 item\(s\)$"),
    re.compile(r"^\$\.validation\[\d+\]: (passed|failed) requires result$"),
    re.compile(r"^\$\.validation\[\d+\]: unavailable requires reason$"),
    re.compile(r"^\$\.validation: missing (focused|full) validation$"),
)


def _path(parent: str, key: object) -> str:
    if isinstance(key, int):
        return f"{parent}[{key}]"
    return f"{parent}.{key}" if parent else str(key)


def _is_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    return False


def validate_schema(value: Any, schema: dict[str, Any], at: str = "$") -> list[str]:
    """Validate the JSON Schema subset used by this repository."""
    errors: list[str] = []
    expected_type = schema.get("type")
    if expected_type and not _is_type(value, expected_type):
        return [f"{at}: expected {expected_type}"]

    if "const" in schema and value != schema["const"]:
        errors.append(f"{at}: expected constant {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{at}: expected one of {schema['enum']!r}")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{at}: string is too short")
        if pattern := schema.get("pattern"):
            if re.fullmatch(pattern, value) is None:
                errors.append(f"{at}: does not match {pattern!r}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{at}: expected at least {schema['minItems']} item(s)")
        if item_schema := schema.get("items"):
            for index, item in enumerate(value):
                errors.extend(validate_schema(item, item_schema, _path(at, index)))
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{at}: missing required property {key!r}")
        if schema.get("additionalProperties") is False:
            for key in value.keys() - properties.keys():
                errors.append(f"{_path(at, key)}: unknown property")
        for key, child in value.items():
            if key in properties:
                errors.extend(validate_schema(child, properties[key], _path(at, key)))
    return errors


def validate_packet(packet: dict[str, Any]) -> list[str]:
    schema = json.loads(SCHEMAS["packet"].read_text())
    errors = validate_schema(packet, schema)
    if errors:
        return errors

    for index, validation in enumerate(packet.get("validation", [])):
        status = validation.get("status")
        if status in {"passed", "failed"} and not validation.get("result"):
            errors.append(f"$.validation[{index}]: {status} requires result")
        if status == "unavailable" and not validation.get("reason"):
            errors.append(f"$.validation[{index}]: unavailable requires reason")

    scopes = {validation["scope"] for validation in packet["validation"]}
    for required_scope in ("focused", "full"):
        if required_scope not in scopes:
            errors.append(f"$.validation: missing {required_scope} validation")

    drift = packet.get("base_drift")
    if drift and drift.get("decision") == "retain":
        invalidators = (
            "effective_diff_changed",
            "resulting_tree_changed",
            "conflict",
            "relevant_overlap",
            "repository_requires_reset",
        )
        active = [name for name in invalidators if drift.get(name) is True]
        if active:
            errors.append(
                "$.base_drift: retain contradicts active invalidator(s): "
                + ", ".join(active)
            )
    return errors


def validate_result(result: dict[str, Any]) -> list[str]:
    schema = json.loads(SCHEMAS["result"].read_text())
    errors = validate_schema(result, schema)
    if errors:
        return errors
    verdict = result.get("verdict")
    findings = result.get("findings", [])
    reasons = result.get("blocking_reasons", [])
    gating = [
        finding
        for finding in findings
        if finding.get("severity") in {"blocking", "strong_recommendation"}
    ]

    if verdict == "clean" and gating:
        errors.append("$.verdict: clean contradicts gating findings")
    if verdict == "changes_required" and not gating:
        errors.append("$.verdict: changes_required requires a gating finding")
    if verdict == "blocked" and not reasons:
        errors.append("$.verdict: blocked requires at least one blocking reason")
    if verdict in {"clean", "changes_required"} and reasons:
        errors.append(f"$.blocking_reasons: must be empty for {verdict}")
    if verdict in {"clean", "changes_required"}:
        candidate = result["candidate"]
        for field in ("head_sha", "comparison_base_sha"):
            if field not in candidate:
                errors.append(f"$.candidate: {verdict} requires {field}")

    identifiers = [finding.get("id") for finding in findings]
    duplicates = sorted({item for item in identifiers if identifiers.count(item) > 1})
    if duplicates:
        errors.append("$.findings: duplicate finding id(s): " + ", ".join(duplicates))

    if result.get("lens") != "aggregate":
        foreign = [
            finding.get("id", "<missing>")
            for finding in findings
            if finding.get("lens") != result.get("lens")
        ]
        if foreign:
            errors.append("$.findings: lens mismatch for " + ", ".join(foreign))

    dispositions = result.get("proposal_dispositions", [])
    if dispositions and result.get("lens") not in {"correctness", "aggregate"}:
        errors.append(
            "$.proposal_dispositions: only correctness or aggregate results may "
            "disposition simplification proposals"
        )
    disposition_ids = [item.get("finding_id") for item in dispositions]
    duplicate_dispositions = sorted(
        {item for item in disposition_ids if disposition_ids.count(item) > 1}
    )
    if duplicate_dispositions:
        errors.append(
            "$.proposal_dispositions: duplicate finding id(s): "
            + ", ".join(duplicate_dispositions)
        )
    return errors


def is_blockable_packet_error(error: str) -> bool:
    """Return whether a packet error represents absent review evidence."""
    return any(pattern.search(error) for pattern in BLOCKABLE_PACKET_ERROR_PATTERNS)


def validate_document(kind: str, document: dict[str, Any]) -> list[str]:
    if kind == "packet":
        return validate_packet(document)
    return validate_result(document)


def validate_pair(packet: dict[str, Any], result: dict[str, Any]) -> list[str]:
    packet_errors = validate_packet(packet)
    result_errors = validate_result(result)
    errors = [f"result: {error}" for error in result_errors]
    for error in packet_errors:
        if result.get("verdict") != "blocked" or not is_blockable_packet_error(error):
            errors.append(f"packet: {error}")
    packet_candidate = packet.get("candidate", {})
    result_candidate = result.get("candidate", {})
    if not isinstance(packet_candidate, dict) or not isinstance(result_candidate, dict):
        return errors
    for field in ("head_sha", "comparison_base_sha"):
        packet_has_field = field in packet_candidate
        result_has_field = field in result_candidate
        if result_has_field and not packet_has_field:
            errors.append(
                f"candidate.{field}: result invents identity absent from packet"
            )
        elif packet_has_field and not result_has_field:
            errors.append(f"candidate.{field}: result omits identity present in packet")
        elif packet_has_field and packet_candidate[field] != result_candidate[field]:
            errors.append(f"candidate.{field}: result does not match packet")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=["packet", "result", "pair"])
    parser.add_argument("document", type=Path)
    parser.add_argument("result_document", type=Path, nargs="?")
    args = parser.parse_args()

    try:
        document = json.loads(args.document.read_text())
    except (OSError, json.JSONDecodeError) as error:
        print(f"{args.document}: {error}", file=sys.stderr)
        return 2
    if not isinstance(document, dict):
        print(
            f"{args.document}: top-level JSON value must be an object", file=sys.stderr
        )
        return 2

    if args.kind == "pair":
        if args.result_document is None:
            parser.error("pair requires a packet and result document")
        try:
            result_document = json.loads(args.result_document.read_text())
        except (OSError, json.JSONDecodeError) as error:
            print(f"{args.result_document}: {error}", file=sys.stderr)
            return 2
        if not isinstance(result_document, dict):
            print(
                f"{args.result_document}: top-level JSON value must be an object",
                file=sys.stderr,
            )
            return 2
        errors = validate_pair(document, result_document)
    else:
        if args.result_document is not None:
            parser.error(f"{args.kind} accepts exactly one document")
        errors = validate_document(args.kind, document)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"valid {args.kind}: {args.document}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
