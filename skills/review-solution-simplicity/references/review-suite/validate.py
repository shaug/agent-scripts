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

REQUIRED_AGGREGATE_LENSES = ("solution_simplicity", "correctness", "code_simplicity")

CONSUMER_IMPACT_DISPOSITIONS_IMPLYING_OTHER_CONSUMERS = (
    "all_consumers_consistent",
    "inconsistency_found",
)

# Maps each stale result schema version to the current version it must be
# migrated to. Extend this mapping, never overwrite it, on the next additive
# schema bump so every prior stale version keeps failing with its own useful
# migration error.
STALE_RESULT_SCHEMA_VERSIONS = {"1.0": "1.1", "1.1": "1.2", "1.2": "1.3"}

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

    if "const" in schema:
        const = schema["const"]
        # `1 == True` in Python; a boolean constant must reject numeric 1/1.0.
        if value != const or isinstance(const, bool) != isinstance(value, bool):
            errors.append(f"{at}: expected constant {const!r}")
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
    if isinstance(result, dict):
        stale_version = result.get("schema_version")
        current_version = STALE_RESULT_SCHEMA_VERSIONS.get(stale_version)
        if current_version is not None:
            return [
                f"$.schema_version: stale v{stale_version} result rejected; "
                f"v{stale_version} results are not accepted as v{current_version} "
                f"evidence, rebuild review evidence at schema {current_version}"
            ]
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

    errors.extend(_check_consumer_impact_evidence(result))
    errors.extend(_check_verification_sufficiency_evidence(result))

    if result.get("lens") == "aggregate" and verdict == "clean":
        errors.extend(_check_aggregate_clean_lens_executions(result))
    return errors


def _check_consumer_impact_evidence(result: dict[str, Any]) -> list[str]:
    """Check consumer/impact evidence structure and disposition consistency.

    #52: `consumer_impact_evidence` records a reviewer's traversal to other
    call sites/consumers of a changed shared symbol, so that traversal is
    machine-checkable instead of an unenforced expectation. The validator does
    not determine which changed symbols require an entry — that judgment
    belongs to the correctness lens's own traversal pass (a later child). It
    only enforces that whatever is supplied is structurally trustworthy: a
    disposition that claims other consumers exist must be backed by evidence
    covering more than the changed symbol's own location, and every entry
    (including `no_other_consumers`) must cite at least one concrete search.

    This function deliberately never inspects `packet["candidate"]["diff"]` to
    decide whether a changed symbol *should* have an entry: this validator
    receives only a packet and a result, with no repository checkout to
    search, so it cannot itself determine whether a changed symbol has other
    call sites (the baseline miss this evidence exists to surface involved a
    sibling call site the diff never touched, which only live repository
    access can find). Adding that determination here would be exactly the
    independent correctness explorer and static call-graph tooling #52's
    non-goals rule out; an omitted `consumer_impact_evidence` array is
    schema-valid by design, and its completeness is judged by forward-testing
    the populating lens's actual output, not by this structural check.
    """
    errors: list[str] = []
    entries = result.get("consumer_impact_evidence")
    if not isinstance(entries, list):
        return errors
    if entries and result.get("lens") not in {"correctness", "aggregate"}:
        errors.append(
            "$.consumer_impact_evidence: only correctness or aggregate results "
            "may include consumer/impact evidence"
        )
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        disposition = entry.get("disposition")
        evidence = entry.get("consumer_search_evidence")
        evidence_count = len(evidence) if isinstance(evidence, list) else 0
        if (
            disposition in CONSUMER_IMPACT_DISPOSITIONS_IMPLYING_OTHER_CONSUMERS
            and evidence_count < 2
        ):
            errors.append(
                f"$.consumer_impact_evidence[{index}]: disposition {disposition!r} "
                "claims other consumers were found and requires search evidence "
                "covering more than the changed symbol's own location"
            )
    return errors


def _check_verification_sufficiency_evidence(result: dict[str, Any]) -> list[str]:
    """Check verification-sufficiency evidence structure and clean consistency.

    #53: `verification_sufficiency_evidence` records, per claimed validation
    command or test touching a materially risky change, whether it actually
    exercises the specific triggering condition the change addresses
    (`exercises_material_risk`) rather than merely whether it passes. This
    closes a baseline verification-sufficiency miss, where the added test
    exercised an already-safe branch instead of the actual risk.

    Unlike `consumer_impact_evidence`, this validator does enforce one
    cross-field rule: an entry only exists because a claimed test or command
    touches a materially risky change, so `exercises_material_risk: "no"` is
    itself the gating fact — the claimed validation does not prove the risk
    is handled. A `clean` verdict paired with such an entry would silently
    hide exactly the gap this evidence exists to surface, so it is rejected
    here rather than left to lens judgment alone.
    """
    errors: list[str] = []
    entries = result.get("verification_sufficiency_evidence")
    if not isinstance(entries, list):
        return errors
    if entries and result.get("lens") not in {"correctness", "aggregate"}:
        errors.append(
            "$.verification_sufficiency_evidence: only correctness or aggregate "
            "results may include verification-sufficiency evidence"
        )
    if result.get("verdict") == "clean":
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                continue
            if entry.get("exercises_material_risk") == "no":
                errors.append(
                    f"$.verification_sufficiency_evidence[{index}]: "
                    "exercises_material_risk 'no' contradicts a clean verdict; "
                    "the claimed test or command does not exercise the material "
                    "risk the change addresses"
                )
    return errors


def _check_aggregate_clean_lens_executions(result: dict[str, Any]) -> list[str]:
    """Require one fresh current-head/current-base clean execution per lens.

    An aggregate `clean` is only trustworthy when every required lens actually
    completed against the exact aggregate candidate. This closes the gap where
    a new-head aggregate could be reached without a fresh solution-simplicity,
    correctness, or code-simplicity execution for that exact head, and rejects
    any old-head or old-base execution smuggled into a new aggregate.
    """
    errors: list[str] = []
    candidate = result.get("candidate")
    head = candidate.get("head_sha") if isinstance(candidate, dict) else None
    base = candidate.get("comparison_base_sha") if isinstance(candidate, dict) else None
    executions = result.get("lens_executions")
    if not isinstance(executions, list) or not executions:
        return ["$.lens_executions: aggregate clean requires lens execution evidence"]

    seen: list[str] = []
    for index, execution in enumerate(executions):
        if not isinstance(execution, dict):
            continue
        lens_name = execution.get("lens")
        seen.append(lens_name)
        at = f"$.lens_executions[{index}]"
        if (
            execution.get("head_sha") != head
            or execution.get("comparison_base_sha") != base
        ):
            errors.append(
                f"{at}: stale head or base cannot contribute to a new-head "
                "aggregate clean"
            )
        if execution.get("verdict") != "clean":
            errors.append(f"{at}: aggregate clean requires a clean lens execution")
        if execution.get("freshly_executed") is not True:
            errors.append(
                f"{at}: aggregate clean requires a freshly executed lens result"
            )

    missing = [lens for lens in REQUIRED_AGGREGATE_LENSES if lens not in seen]
    if missing:
        errors.append(
            "$.lens_executions: aggregate clean is missing required lens "
            "execution(s): " + ", ".join(missing)
        )
    duplicates = sorted({lens for lens in seen if lens and seen.count(lens) > 1})
    if duplicates:
        errors.append(
            "$.lens_executions: aggregate clean has duplicate lens execution(s): "
            + ", ".join(duplicates)
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
    errors.extend(_check_clean_requires_passing_validation(packet, result))
    return errors


def _check_clean_requires_passing_validation(
    packet: dict[str, Any], result: dict[str, Any]
) -> list[str]:
    """Reject a `clean` verdict paired with failed or unavailable validation.

    A schema-valid `clean` result previously did not prove that the packet's
    own required focused and full validation actually passed: every entry
    could be `failed` and pair validation raised no error. `clean` must not
    hide a failed or unavailable required command.
    """
    if result.get("verdict") != "clean":
        return []
    validations = packet.get("validation")
    if not isinstance(validations, list):
        return []
    errors: list[str] = []
    for index, validation in enumerate(validations):
        if not isinstance(validation, dict):
            continue
        status = validation.get("status")
        if status in {"failed", "unavailable"}:
            errors.append(
                f"validation[{index}]: clean cannot pair with {status} "
                "required validation"
            )
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
