#!/usr/bin/env python3
"""Deterministic grader for prepare-changesets eval runs."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from chain import compare_chain, create_chain, validate_chain  # noqa: E402
from common import (  # noqa: E402
    DEFAULT_PLAN_PATH,
    CommandError,
    ensure_clean_tree,
    git,
    load_plan,
    validate_plan,
)


def branch_name_for(source_branch: str, index: int) -> str:
    return f"{source_branch}-{index}"


@dataclass
class GradeResult:
    ok: bool
    checks: List[str]
    failures: List[str]


def _require_clean_tree(checks: List[str], failures: List[str]) -> None:
    try:
        ensure_clean_tree()
        checks.append("clean_tree")
    except CommandError as exc:
        failures.append(f"clean_tree: {exc}")


def _validate_plan(plan: Dict, checks: List[str], failures: List[str]) -> None:
    valid, errors = validate_plan(plan)
    if valid:
        checks.append("plan_valid")
    else:
        failures.append("plan_valid: " + "; ".join(errors))


def _check_source_hash(
    source_branch: str, expected: str, checks: List[str], failures: List[str]
) -> None:
    current = git("rev-parse", source_branch).stdout.strip()
    if current == expected:
        checks.append("source_hash_unchanged")
    else:
        failures.append(f"source_hash_unchanged: expected {expected}, got {current}")


def _check_chain_exists(plan: Dict, checks: List[str], failures: List[str]) -> None:
    source = plan["source_branch"]
    total = len(plan["changesets"])
    missing: List[str] = []
    for i in range(1, total + 1):
        name = branch_name_for(source, i)
        if git("rev-parse", "--verify", name, check=False).returncode != 0:
            missing.append(name)
    if missing:
        failures.append("chain_exists: missing " + ", ".join(missing))
    else:
        checks.append("chain_exists")


def _check_equivalence(plan: Dict, checks: List[str], failures: List[str]) -> None:
    try:
        diffstat, namestatus = compare_chain(plan)
    except CommandError as exc:
        failures.append(f"compare_chain: {exc}")
        return

    if diffstat.strip() or namestatus.strip():
        failures.append("equivalence: differences detected")
    else:
        checks.append("equivalence")


def _check_validate_chain(
    plan: Dict, test_cmd: str, checks: List[str], failures: List[str]
) -> None:
    try:
        validate_chain(plan, test_cmd=test_cmd)
        checks.append("validate_chain")
    except CommandError as exc:
        failures.append(f"validate_chain: {exc}")


def grade_repo(
    *,
    plan_path: Path,
    expected_source_hash: str,
    test_cmd: str,
    auto_create_chain: bool,
) -> GradeResult:
    checks: List[str] = []
    failures: List[str] = []

    _require_clean_tree(checks, failures)

    try:
        plan = load_plan(plan_path)
    except CommandError as exc:
        failures.append(f"load_plan: {exc}")
        return GradeResult(ok=False, checks=checks, failures=failures)

    _validate_plan(plan, checks, failures)
    _check_source_hash(plan["source_branch"], expected_source_hash, checks, failures)

    if auto_create_chain:
        try:
            create_chain(plan)
            checks.append("create_chain")
        except CommandError as exc:
            failures.append(f"create_chain: {exc}")

    _check_chain_exists(plan, checks, failures)
    _check_equivalence(plan, checks, failures)
    _check_validate_chain(plan, test_cmd=test_cmd, checks=checks, failures=failures)

    return GradeResult(ok=not failures, checks=checks, failures=failures)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Grade a repo against prepare-changesets invariants."
    )
    parser.add_argument("--plan", default=str(DEFAULT_PLAN_PATH), help="Plan path")
    parser.add_argument(
        "--expected-source-hash",
        required=True,
        help="Expected source branch hash before the run",
    )
    parser.add_argument(
        "--test-cmd",
        default="python3 -c \"print('ok')\"",
        help="Test command for validate-chain",
    )
    parser.add_argument(
        "--auto-create-chain",
        action="store_true",
        help="Create the chain before grading (useful for deterministic baselines).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON result to stdout.",
    )
    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    result = grade_repo(
        plan_path=Path(args.plan),
        expected_source_hash=args.expected_source_hash,
        test_cmd=args.test_cmd,
        auto_create_chain=args.auto_create_chain,
    )

    if args.json:
        print(json.dumps(asdict(result), indent=2))
    else:
        print("OK" if result.ok else "FAIL")
        if result.checks:
            print("checks: " + ", ".join(result.checks))
        if result.failures:
            print("failures: " + "; ".join(result.failures))

    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
