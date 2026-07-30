#!/usr/bin/env python3
"""Validate review-fix-loop invocation, checkpoint, and terminal-result documents.

This module intentionally has no third-party dependencies, matching the
convention used by the repository's review-suite contract
(`skills/review-code-change/references/review-suite/validate.py`): a skill
folder is the unit of distribution, so its validator must work standalone
wherever the skill is installed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SCHEMA_DIR = HERE.parent / "references"

SCHEMAS = {
    "invocation": SCHEMA_DIR / "invocation.schema.json",
    "checkpoint": SCHEMA_DIR / "checkpoint.schema.json",
    "terminal-result": SCHEMA_DIR / "terminal-result.schema.json",
}

CHANGES_REMAINING_REASONS = {
    "cycle_budget_exhausted",
    "repeated_finding",
    "oscillation",
    "expanding_findings",
    "repeated_failed_attempt",
    "current_candidate_validation_failure",
}

BLOCKED_REASONS = {
    "candidate_busy",
    "candidate_integrity_failure",
    "checkpoint_mismatch",
    "missing_capability",
    "missing_authority",
    "insufficient_change_contract",
    "reviewer_integrity_failure",
    "validation_unavailable",
    "base_drift",
    "remote_advanced",
    "publication_failed",
    "scope_decision_required",
    "operator_input_required",
}

# Blocked reasons whose publication status is `failed` rather than `withheld`
# under `update_pr`: only these observed a publication attempt that did not
# land cleanly.
BLOCKED_REASONS_IMPLYING_PUBLICATION_FAILED = {"remote_advanced", "publication_failed"}


# ---------------------------------------------------------------------------
# Minimal JSON Schema subset (shared shape with the review-suite validator)
# ---------------------------------------------------------------------------


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
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
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
    if isinstance(value, int) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{at}: must be >= {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{at}: must be <= {schema['maximum']}")
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


def _load_schema(name: str) -> dict[str, Any]:
    return json.loads(SCHEMAS[name].read_text())


# ---------------------------------------------------------------------------
# Invocation
# ---------------------------------------------------------------------------


def validate_invocation(document: dict[str, Any]) -> list[str]:
    errors = validate_schema(document, _load_schema("invocation"))
    if errors:
        return errors

    review_execution = document.get("review_execution", {})
    mode = review_execution.get("mode")
    override = review_execution.get("override_authorization")
    if mode == "in_agent_override" and not override:
        errors.append(
            "$.review_execution: in_agent_override requires override_authorization"
        )
    if mode == "fresh_subagent" and override:
        errors.append(
            "$.review_execution: fresh_subagent must not carry override_authorization"
        )

    candidate = document.get("candidate", {})
    has_binding = "source_binding" in candidate
    has_unavailable = "source_unavailable_reason" in candidate
    if has_binding and has_unavailable:
        errors.append(
            "$.candidate: source_binding and source_unavailable_reason are "
            "mutually exclusive"
        )
    elif not has_binding and not has_unavailable:
        errors.append(
            "$.candidate: requires source_binding or an explicit "
            "source_unavailable_reason"
        )

    publication = document.get("publication", {})
    policy = publication.get("policy")
    grants = publication.get("remote_iteration_grants", [])
    if policy == "update_pr":
        if "pull_request" not in publication:
            errors.append("$.publication: update_pr requires pull_request")
        if not has_binding:
            errors.append("$.publication: update_pr requires candidate.source_binding")
    elif policy == "local_commit":
        if "pull_request" in publication:
            errors.append(
                "$.publication: local_commit must not carry a pull_request target"
            )
        if grants:
            errors.append(
                "$.publication.remote_iteration_grants: local_commit never "
                "performs a remote write and cannot carry a grant"
            )

    scopes = {entry.get("scope") for entry in document.get("validation", [])}
    for required_scope in ("focused", "full"):
        if required_scope not in scopes:
            errors.append(f"$.validation: missing {required_scope} validation")

    return errors


# ---------------------------------------------------------------------------
# Checkpoint
# ---------------------------------------------------------------------------


def reconstruct_cycle_accounting(checkpoint: dict[str, Any]) -> dict[str, int]:
    """Reconstruct cycle consumption from checkpoint history alone.

    A cycle is reserved and consumed the moment a remediation attempt starts,
    whatever its outcome (`committed`, `failed`, or `interrupted`). Consumed
    and remaining counts are therefore never stored directly; they are always
    derived from `cycle_attempts` so they cannot drift from the history that
    produced them.
    """
    original = checkpoint.get("original_cycle_budget", 0)
    consumed = len(checkpoint.get("cycle_attempts", []))
    return {
        "original_max_fix_cycles": original,
        "consumed_cycles": consumed,
        "remaining_cycles": original - consumed,
    }


def validate_checkpoint(document: dict[str, Any]) -> list[str]:
    errors = validate_schema(document, _load_schema("checkpoint"))
    if errors:
        return errors

    initial_head = document.get("initial_head")
    current_head = document.get("current_head")
    head_history = document.get("head_history", [])
    if head_history and head_history[0] != initial_head:
        errors.append("$.head_history[0]: must equal initial_head")
    if head_history and head_history[-1] != current_head:
        errors.append("$.head_history[-1]: must equal current_head")

    attempts = document.get("cycle_attempts", [])
    budget = document.get("original_cycle_budget", 0)
    if len(attempts) > budget:
        errors.append(
            "$.cycle_attempts: consumed more cycles than original_cycle_budget "
            f"({len(attempts)} > {budget})"
        )

    committed_heads = [
        attempt.get("resulting_head")
        for attempt in attempts
        if attempt.get("outcome") == "committed"
    ]
    for index, attempt in enumerate(attempts):
        if attempt.get("outcome") == "committed" and not attempt.get("resulting_head"):
            errors.append(
                f"$.cycle_attempts[{index}]: committed outcome requires resulting_head"
            )
    if len(committed_heads) != max(len(head_history) - 1, 0):
        errors.append(
            "$.cycle_attempts: committed attempt count "
            f"({len(committed_heads)}) does not match head_history advances "
            f"({max(len(head_history) - 1, 0)})"
        )
    elif committed_heads != head_history[1:]:
        errors.append(
            "$.cycle_attempts: committed resulting_head sequence does not "
            "match head_history"
        )

    base_history = document.get("base_revision_history", [])
    current_base = document.get("comparison_base", {}).get("sha")
    if base_history and base_history[-1].get("sha") != current_base:
        errors.append(
            "$.base_revision_history[-1]: must equal the current comparison_base"
        )

    source = document.get("source", {})
    if source.get("status") == "unavailable" and not source.get("unavailable_reason"):
        errors.append("$.source: unavailable status requires unavailable_reason")
    if source.get("status") == "bound" and "last_verified_head" not in source:
        errors.append("$.source: bound status requires last_verified_head")

    return errors


# ---------------------------------------------------------------------------
# Terminal result
# ---------------------------------------------------------------------------


def validate_terminal_result(document: dict[str, Any]) -> list[str]:
    errors = validate_schema(document, _load_schema("terminal-result"))
    if errors:
        return errors

    state = document.get("terminal_state")
    reason = document.get("reason")

    if state == "converged" and reason is not None:
        errors.append("$.reason: converged must not carry a reason")
    if state == "changes_remaining" and reason not in CHANGES_REMAINING_REASONS:
        errors.append(
            "$.reason: changes_remaining requires one of "
            + ", ".join(sorted(CHANGES_REMAINING_REASONS))
        )
    if state == "blocked" and reason not in BLOCKED_REASONS:
        errors.append(
            "$.reason: blocked requires one of " + ", ".join(sorted(BLOCKED_REASONS))
        )

    budget = document.get("budget", {})
    original = budget.get("original_max_fix_cycles", 0)
    consumed = budget.get("consumed_cycles", 0)
    remaining = budget.get("remaining_cycles", 0)
    if consumed + remaining != original:
        errors.append(
            "$.budget: consumed_cycles + remaining_cycles must equal "
            "original_max_fix_cycles"
        )

    publication = document.get("publication", {})
    policy = publication.get("policy")
    status = publication.get("status")
    if policy == "local_commit" and status != "not_applicable":
        errors.append(
            "$.publication.status: local_commit never publishes; must be not_applicable"
        )
    elif policy == "update_pr":
        if state == "converged" and status != "published":
            errors.append(
                "$.publication.status: a converged update_pr result must be published"
            )
        elif state == "changes_remaining" and status != "withheld":
            errors.append(
                "$.publication.status: changes_remaining must withhold publication"
            )
        elif state == "blocked":
            expected = (
                "failed"
                if reason in BLOCKED_REASONS_IMPLYING_PUBLICATION_FAILED
                else "withheld"
            )
            if status != expected:
                errors.append(
                    f"$.publication.status: blocked/{reason} must be {expected!r}"
                )

    head = document.get("head", {})
    unpushed = document.get("unpushed_commits", [])
    if (
        head.get("initial") != head.get("final")
        and status != "published"
        and not unpushed
    ):
        errors.append(
            "$.unpushed_commits: candidate changed but no unpushed commits were "
            "reported for a non-published result"
        )
    if status == "published" and unpushed:
        errors.append(
            "$.unpushed_commits: must be empty once publication.status is published"
        )

    base = document.get("comparison_base", {})
    identity_changed = head.get("initial") != head.get("final") or base.get(
        "initial"
    ) != base.get("final")
    if (
        identity_changed
        and document.get("acceptance_reconciliation_required") is not True
    ):
        errors.append(
            "$.acceptance_reconciliation_required: must be true when head or "
            "comparison_base identity changed"
        )

    head_history = document.get("head_history", [])
    if head_history and head_history[0] != head.get("initial"):
        errors.append("$.head_history[0]: must equal head.initial")
    if head_history and head_history[-1] != head.get("final"):
        errors.append("$.head_history[-1]: must equal head.final")

    base_history = document.get("base_revision_history", [])
    if base_history and base_history[0].get("sha") != base.get("initial", {}).get(
        "sha"
    ):
        errors.append("$.base_revision_history[0]: must equal comparison_base.initial")
    if base_history and base_history[-1].get("sha") != base.get("final", {}).get("sha"):
        errors.append("$.base_revision_history[-1]: must equal comparison_base.final")

    source = document.get("source", {})
    if source.get("status") == "unavailable" and not source.get("unavailable_reason"):
        errors.append("$.source: unavailable status requires unavailable_reason")
    if source.get("status") == "bound" and (
        "initial_head" not in source or "final_head" not in source
    ):
        errors.append("$.source: bound status requires initial_head and final_head")

    return errors


def validate_terminal_against_checkpoint(
    checkpoint: dict[str, Any], terminal_result: dict[str, Any]
) -> list[str]:
    """Cross-check that a terminal result matches the checkpoint it derives from."""
    errors: list[str] = []
    accounting = reconstruct_cycle_accounting(checkpoint)
    budget = terminal_result.get("budget", {})
    for field in ("original_max_fix_cycles", "consumed_cycles", "remaining_cycles"):
        if budget.get(field) != accounting[field]:
            errors.append(
                f"$.budget.{field}: {budget.get(field)!r} does not match "
                f"checkpoint-reconstructed value {accounting[field]!r}"
            )
    if checkpoint.get("invocation_id") != terminal_result.get("invocation_id"):
        errors.append("$.invocation_id: does not match checkpoint invocation_id")
    if checkpoint.get("initial_head") != terminal_result.get("head", {}).get("initial"):
        errors.append("$.head.initial: does not match checkpoint initial_head")
    if checkpoint.get("current_head") != terminal_result.get("head", {}).get("final"):
        errors.append("$.head.final: does not match checkpoint current_head")
    return errors


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def canonical_json(document: dict[str, Any]) -> str:
    """Serialize a document deterministically: sorted keys, trailing newline."""
    return json.dumps(document, sort_keys=True, indent=2) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def validate_document(kind: str, document: dict[str, Any]) -> list[str]:
    if kind == "invocation":
        return validate_invocation(document)
    if kind == "checkpoint":
        return validate_checkpoint(document)
    return validate_terminal_result(document)


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        document = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        print(f"{path}: {error}", file=sys.stderr)
        return None
    if not isinstance(document, dict):
        print(f"{path}: top-level JSON value must be an object", file=sys.stderr)
        return None
    return document


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=["invocation", "checkpoint", "terminal-result"])
    parser.add_argument("document", type=Path)
    args = parser.parse_args()

    document = _load_json(args.document)
    if document is None:
        return 2

    errors = validate_document(args.kind, document)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"valid {args.kind}: {args.document}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
