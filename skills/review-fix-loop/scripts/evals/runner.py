#!/usr/bin/env python3
"""Run the review-fix-loop cross-cutting evaluation corpus (issue #101).

Every scenario in `corpus.py` drives the real `local_commit`/`update_pr`
engine against a real disposable Git repository (and, for `update_pr`, a
real disposable bare remote) — no subprocess boundary and no model call is
involved, matching `eval-carve-changesets`'
`--integration-self-test` convention: this is an objective, deterministic
replay, not an agent-judgment evaluation. Because the three genuinely
host-boundary actions (`reviewer`, `decide`, `apply_fix`) are supplied here as
small deterministic fixtures (`helpers.py`), the whole corpus is free to run
and safe for repository CI, satisfying this ticket's "deterministic enough
for repository CI" acceptance criterion.

Grading is result-blind: `grader.grade_case` never trusts a scenario's
returned terminal-result document by itself. Each scenario computes its own
`checks` mapping against live Git state (see `corpus.py`'s module docstring),
and this runner's job is only to execute every scenario, grade it, and print
one JSON report that identifies the exact fixture, the mismatched evidence,
and the failure reason for every failing check.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import corpus as CORPUS  # noqa: E402
import grader as GRADER  # noqa: E402


def run_scenario(name: str) -> dict:
    scenario = CORPUS.SCENARIOS_BY_ID[name]
    with tempfile.TemporaryDirectory(prefix=f"review-fix-loop-eval-{name}-") as tmp:
        return scenario(Path(tmp))


def run_all(ids: list[str] | None = None) -> tuple[dict[str, dict], list[str]]:
    names = ids or list(CORPUS.SCENARIOS_BY_ID)
    cases: dict[str, dict] = {}
    failures: list[str] = []
    for name in names:
        case = run_scenario(name)
        cases[case["id"]] = case
        failures.extend(GRADER.grade_case(case))
    return cases, failures


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario",
        action="append",
        dest="scenarios",
        help=(
            "Run only this scenario function name (repeatable). Defaults to "
            "the complete corpus."
        ),
    )
    parser.add_argument(
        "--list", action="store_true", help="List every scenario id and exit."
    )
    parser.add_argument("--output-dir", type=Path)
    return parser


def write_outputs(output_dir: Path | None, cases: dict[str, dict]) -> None:
    if output_dir is None:
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    for case_id, case in cases.items():
        report = {
            "id": case["id"],
            "category": case["category"],
            "policy": case["policy"],
            "checks": {
                name: {"expected": expected, "observed": observed}
                for name, (expected, observed) in case["checks"].items()
            },
        }
        (output_dir / f"{case_id}.json").write_text(
            json.dumps(report, indent=2, sort_keys=True, default=str) + "\n"
        )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list:
        for name in CORPUS.SCENARIOS_BY_ID:
            print(name)
        return 0

    cases, failures = run_all(args.scenarios)
    write_outputs(args.output_dir, cases)

    failed_ids = {failure.split(":", 1)[0] for failure in failures}
    summary = {
        "total": len(cases),
        "passed": len(cases) - len(failed_ids),
        "failed": len(failed_ids),
        "failures": failures,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
