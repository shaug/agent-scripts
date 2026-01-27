#!/usr/bin/env python3
"""Local eval runner that optionally invokes codex exec, then grades deterministically."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

THIS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = THIS_DIR.parents[0]
SKILL_DIR = THIS_DIR.parents[2]
DEFAULT_PROMPTS_PATH = SKILL_DIR / "evals" / "prompts.csv"
DEFAULT_OUT_DIR = SKILL_DIR / "evals" / "out"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from common import DEFAULT_PLAN_PATH  # noqa: E402

from evals.grader import GradeResult, grade_repo  # noqa: E402
from evals.helpers import cleanup_repo, init_eval_repo  # noqa: E402


def codex_available(codex_bin: str) -> bool:
    return shutil.which(codex_bin) is not None


def run_codex(prompt: str, *, codex_bin: str, cwd: Path) -> subprocess.CompletedProcess:
    cmd = [codex_bin, "exec", "--full-auto", "--json", prompt]
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)


def load_prompts(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        return [row for row in reader]


def run_eval_case(
    *,
    case_id: str,
    prompt: str,
    codex_bin: str,
    skip_codex: bool,
    test_cmd: str,
    out_dir: Path,
) -> Dict:
    repo_dir, plan, source_hash = init_eval_repo()
    plan_path = repo_dir / DEFAULT_PLAN_PATH

    codex_result: Dict[str, str] = {}
    original_cwd = Path.cwd()
    try:
        os.chdir(repo_dir)
        if not skip_codex:
            if not codex_available(codex_bin):
                raise RuntimeError(f"codex binary not found on PATH: {codex_bin}")
            result = run_codex(prompt, codex_bin=codex_bin, cwd=repo_dir)
            codex_result = {
                "returncode": str(result.returncode),
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        else:
            codex_result = {"skipped": "true"}

        grade: GradeResult = grade_repo(
            plan_path=plan_path,
            expected_source_hash=source_hash,
            test_cmd=test_cmd,
            auto_create_chain=skip_codex,
        )

        case_out = {
            "id": case_id,
            "ok": grade.ok,
            "checks": grade.checks,
            "failures": grade.failures,
            "codex": codex_result,
        }
        return case_out
    finally:
        os.chdir(original_cwd)
        cleanup_repo(repo_dir)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run local evals for prepare-changesets."
    )
    parser.add_argument(
        "--prompts",
        default=str(DEFAULT_PROMPTS_PATH),
        help="Prompts CSV path",
    )
    parser.add_argument(
        "--out-dir",
        default=str(DEFAULT_OUT_DIR),
        help="Directory to write eval results",
    )
    parser.add_argument("--codex-bin", default="codex", help="codex executable name")
    parser.add_argument(
        "--skip-codex",
        action="store_true",
        help="Skip invoking codex and grade a deterministic baseline instead.",
    )
    parser.add_argument(
        "--test-cmd",
        default="python3 -c \"print('ok')\"",
        help="Test command used by the grader's validate-chain step.",
    )
    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    prompts_path = Path(args.prompts)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cases = load_prompts(prompts_path)
    results: List[Dict] = []

    for row in cases:
        case_id = row.get("id", "case")
        prompt = row.get("prompt", "").strip()
        if not prompt:
            results.append(
                {"id": case_id, "ok": False, "failures": ["empty prompt"], "checks": []}
            )
            continue
        try:
            result = run_eval_case(
                case_id=case_id,
                prompt=prompt,
                codex_bin=args.codex_bin,
                skip_codex=args.skip_codex,
                test_cmd=args.test_cmd,
                out_dir=out_dir,
            )
        except Exception as exc:  # defensive guard for eval runs
            result = {
                "id": case_id,
                "ok": False,
                "checks": [],
                "failures": [f"exception: {exc}"],
            }
        results.append(result)

        (out_dir / f"{case_id}.json").write_text(json.dumps(result, indent=2) + "\n")

    summary = {
        "total": len(results),
        "passed": sum(1 for r in results if r.get("ok")),
        "failed": sum(1 for r in results if not r.get("ok")),
        "results": results,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    print(json.dumps(summary, indent=2))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
