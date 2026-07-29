#!/usr/bin/env python3
"""Reject an untrustworthy `review-code-change` aggregate result.

The bundled `references/review-suite/validate.py` enforces the shared review
result schema and cross-field semantics (stale/unsupported schema versions,
malformed shape, verdict/evidence consistency, and aggregate-clean lens
execution completeness). This module adds the one check that schema alone
cannot make: binding the result to *this* run's exact current candidate.

This is deliberately a thin consumption check, not a reviewer. It never
sequences lenses, explores evidence, or decides what a clean review means —
those stay owned by repository-owned `review-code-change`. It only refuses to
let this caller treat a stale, malformed, non-aggregate, non-clean, or
wrongly-bound result as publishable evidence.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


def _validate_module_path() -> Path:
    """Locate the bundled `validate.py` in either supported layout.

    Installed layout (each consuming skill): `scripts/review_gate.py` beside
    `references/review-suite/validate.py`. Canonical layout (this monorepo):
    `review-suite/scripts/review_gate.py` beside `review-suite/scripts/
    validate.py`, in the same directory as this file.
    """
    here = Path(__file__).resolve().parent
    for candidate in (
        here.parent / "references" / "review-suite" / "validate.py",
        here / "validate.py",
    ):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"Cannot locate validate.py near {here}")


VALIDATE_SPEC = importlib.util.spec_from_file_location(
    "caller_review_suite_validate", _validate_module_path()
)
assert VALIDATE_SPEC and VALIDATE_SPEC.loader
VALIDATE = importlib.util.module_from_spec(VALIDATE_SPEC)
VALIDATE_SPEC.loader.exec_module(VALIDATE)


def evaluate_aggregate(
    result: dict[str, Any], expected_head: str, expected_base: str
) -> list[str]:
    """Return rejection reasons for `result`; empty means accept as evidence.

    `result` must be a schema-valid aggregate `clean` result whose candidate
    and every fresh lens execution are bound to `expected_head`/
    `expected_base` — the exact head and comparison base this caller captured
    for its current candidate.
    """
    errors = [f"schema: {error}" for error in VALIDATE.validate_result(result)]
    if errors:
        # A schema-level rejection (stale version, malformed shape, verdict
        # contradictions, incomplete lens executions) already explains why
        # the result is untrustworthy; do not layer confusing candidate-binding
        # errors on top of a document that isn't even shape-valid.
        return errors

    if result.get("lens") != "aggregate":
        errors.append(f"lens: expected an aggregate result, got {result.get('lens')!r}")
    if result.get("verdict") != "clean":
        errors.append(
            f"verdict: expected clean, got {result.get('verdict')!r}; "
            "changes_required and blocked results cannot be consumed as "
            "publishable evidence"
        )

    candidate = result.get("candidate") or {}
    if (
        candidate.get("head_sha") != expected_head
        or candidate.get("comparison_base_sha") != expected_base
    ):
        errors.append(
            "candidate: result is not bound to the current candidate "
            f"(expected head {expected_head} / base {expected_base}, got "
            f"head {candidate.get('head_sha')!r} / "
            f"base {candidate.get('comparison_base_sha')!r})"
        )

    for execution in result.get("lens_executions") or []:
        if not isinstance(execution, dict):
            continue
        if (
            execution.get("head_sha") != expected_head
            or execution.get("comparison_base_sha") != expected_base
        ):
            errors.append(
                f"lens_executions: {execution.get('lens')!r} execution is not "
                "bound to the current candidate"
            )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", type=Path, help="review-code-change result JSON")
    parser.add_argument("--head", required=True, help="current captured head SHA")
    parser.add_argument(
        "--base", required=True, help="current captured comparison-base SHA"
    )
    args = parser.parse_args()

    try:
        result = json.loads(args.result.read_text())
    except (OSError, json.JSONDecodeError) as error:
        print(f"{args.result}: {error}", file=sys.stderr)
        return 2
    if not isinstance(result, dict):
        print(f"{args.result}: top-level JSON value must be an object", file=sys.stderr)
        return 2

    errors = evaluate_aggregate(result, args.head, args.base)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"clean current-candidate aggregate: {args.result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
