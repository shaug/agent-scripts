#!/usr/bin/env python3
"""Re-grade already-captured raw attempts with the currently shipped grader.

`runner.py` couples execution (spawning a fresh executor process, which costs
real money) and grading (pure, free, deterministic) into one pass. When the
grader changes - fixing a real defect, or any other reason - every stratum's
already-retained raw output (`--artifact-dir`) can be re-graded for free,
without spending anything on new model calls, by replaying each retained
`<case>.run-<n>.stdout.json` artifact through the current
`grader.grade`/`report.aggregate` and rebuilding the report from it.

This is deliberately a separate, narrow tool rather than a `runner.py` flag:
it never launches a process, never talks to an executor, and takes its
attempts from `--attempts-in` (a prior run's `--attempts-out` file) plus the
raw artifacts that run retained, rather than from a live corpus replay.

Usage:
    python3 regrade.py --corpus review-suite/evals/strata/<stratum> \\
        --attempts-in <prior>.attempts.jsonl \\
        --artifact-dir <prior-artifact-dir> \\
        --report-out <path>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):  # direct `python3 regrade.py` invocation
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from evals import corpus, grader, protocol, report
else:
    from . import corpus, grader, protocol, report


class RegradeError(ValueError):
    """Raised when a prior attempt cannot be re-graded from what is on disk."""


def _artifact_stem(case_id: str, run_number: int) -> str:
    return f"{case_id}.run-{run_number}"


def regrade_attempts(
    *, corpus_root: Path | None, attempts_in: Path, artifact_dir: Path
) -> tuple[list[dict[str, Any]], corpus.Corpus]:
    """Rebuild every gradable attempt's `grade` from its retained raw artifact.

    Every other attempt field (status, usage, latency, executor identity, ...)
    is carried over unchanged from `attempts_in`: none of that describes
    grading, so none of it can be stale just because the grader changed.
    """
    loaded = corpus.load_corpus(corpus_root)
    expectations = {case.case_id: case.expectation for case in loaded.cases}

    attempts: list[dict[str, Any]] = []
    for line_number, line in enumerate(attempts_in.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        attempt = dict(json.loads(line))
        if attempt["status"] in protocol.GRADABLE_STATUSES:
            case_id = attempt["case_id"]
            if case_id not in expectations:
                raise RegradeError(
                    f"{attempts_in}:{line_number}: {case_id!r} is not a case in "
                    f"{corpus_root or corpus.DEFAULT_CORPUS}"
                )
            stem = _artifact_stem(case_id, attempt["run_number"])
            raw_path = artifact_dir / f"{stem}.stdout.json"
            if not raw_path.is_file():
                raise RegradeError(f"missing retained raw artifact {raw_path}")
            response = json.loads(raw_path.read_text())
            attempt["grade"] = grader.grade(expectations[case_id], response["result"])
        attempts.append(attempt)
    return attempts, loaded


def _configuration(
    attempts: list[dict[str, Any]],
    loaded: corpus.Corpus,
    *,
    attempts_in: Path,
    artifact_dir: Path,
) -> dict[str, Any]:
    sample = attempts[0] if attempts else {}
    return {
        "executor": None,
        "corpus_version": loaded.corpus_version,
        "grader_version": grader.GRADER_VERSION,
        "target_skill": loaded.target_skill,
        "target_skill_dependencies": list(loaded.target_skill_dependencies),
        "stratum": loaded.stratum,
        "suite_commit": sample.get("suite_commit"),
        "runs_per_case": max((a["run_number"] for a in attempts), default=0),
        "cases": len(loaded.cases),
        "regraded": True,
        "regraded_from_attempts": str(attempts_in),
        "regraded_from_artifact_dir": str(artifact_dir),
        "regraded_grader_version": grader.GRADER_VERSION,
        "regrade_note": (
            "No executor process ran in this pass. Every non-grading attempt "
            "field is carried over unchanged from the source attempts file; "
            "only `grade` was recomputed, from the retained raw artifact, "
            "using the grader version above."
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=None)
    parser.add_argument("--attempts-in", type=Path, required=True)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--report-out", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        attempts, loaded = regrade_attempts(
            corpus_root=args.corpus,
            attempts_in=args.attempts_in,
            artifact_dir=args.artifact_dir,
        )
    except (RegradeError, corpus.CorpusError, grader.GradingError) as error:
        print(f"regrade rejected: {error}", file=sys.stderr)
        return 2

    configuration = _configuration(
        attempts,
        loaded,
        attempts_in=args.attempts_in,
        artifact_dir=args.artifact_dir,
    )
    aggregate = report.aggregate(attempts, configuration=configuration)

    if args.report_out:
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_out.write_text(
            json.dumps(aggregate, indent=2, sort_keys=True) + "\n"
        )

    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
