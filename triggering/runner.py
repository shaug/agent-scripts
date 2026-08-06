#!/usr/bin/env python3
"""Run the result-blind triggering corpus through a fresh-process executor.

Each case asks one question: given a prompt, which compris skill (if any)
should trigger? The executor never sees the expected answer, the case's `kind`,
or which skill the case was filed under — only the prompt and the catalog of
skill descriptions a router would actually have.

Executors declare the tier that produced their answers, and the runner records
that provenance per case and in the aggregate, because the two model tiers and
the deterministic simulation answer different questions and must never be
confused in committed evidence.

Usage:
    python3 triggering/runner.py
    python3 triggering/runner.py --executor "python3 triggering/executors/description_executor.py"
    python3 triggering/runner.py --skill implement-ticket --output-dir out/
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

TRIGGERING_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = TRIGGERING_ROOT.parent
DEFAULT_CORPUS = TRIGGERING_ROOT / "corpus.json"
DEFAULT_EXPECTATIONS = TRIGGERING_ROOT / "expectations.json"
DEFAULT_EXECUTOR = TRIGGERING_ROOT / "executors" / "fixture_executor.py"

TIERS = ("headless", "description", "fixture")


class CorpusError(Exception):
    """The corpus and its answer key do not agree."""


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def skill_catalog() -> list[dict]:
    """Every skill's name and trigger description, as a router would see them.

    Read from the live `SKILL.md` files rather than copied into the corpus, so
    the corpus cannot drift out of agreement with the descriptions it tests.
    """
    catalog = []
    for skill_md in sorted((REPOSITORY_ROOT / "skills").glob("*/SKILL.md")):
        text = skill_md.read_text(encoding="utf-8")
        if not text.startswith("---"):
            continue
        front_matter = text.split("---", 2)[1]
        description = extract_description(front_matter)
        if description:
            catalog.append({"skill": skill_md.parent.name, "description": description})
    return catalog


def extract_description(front_matter: str) -> str | None:
    """Pull `description:` out of YAML front matter without a YAML dependency."""
    lines = front_matter.splitlines()
    collected: list[str] = []
    for index, line in enumerate(lines):
        if not line.startswith("description:"):
            continue
        collected.append(line.split(":", 1)[1].strip())
        for continuation in lines[index + 1 :]:
            if continuation and not continuation[0].isspace():
                break
            collected.append(continuation.strip())
        break
    if not collected:
        return None
    joined = " ".join(part for part in collected if part)
    # Descriptions are written as quoted or bare scalars; both reach the router
    # as plain prose, and `allowed-tools` is a sibling key rather than part of
    # the description.
    joined = joined.split("allowed-tools:")[0].strip()
    return joined.strip("'\"").strip()


def build_payload(case: dict, catalog: list[dict]) -> dict:
    """The result-blind packet: the prompt and the catalog, nothing else."""
    return {
        "prompt": case["prompt"],
        "catalog": catalog,
    }


def run_executor(command: list[str], payload: dict) -> dict:
    completed = subprocess.run(
        command,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        cwd=REPOSITORY_ROOT,
    )
    if completed.returncode:
        raise RuntimeError(
            f"executor exited {completed.returncode}: {completed.stderr.strip()}"
        )
    try:
        observed = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("executor did not return one JSON result") from error
    if not isinstance(observed, dict):
        raise RuntimeError("executor result was not a JSON object")
    return observed


def normalize(observed: dict) -> dict:
    """Keep only the fields the grader and the evidence record are defined on."""
    tier = observed.get("tier")
    return {
        "selected_skill": observed.get("selected_skill"),
        "tier": tier if tier in TIERS else None,
        "repetitions": observed.get("repetitions"),
        "agreement": observed.get("agreement"),
        "votes": observed.get("votes"),
    }


def grade(case_id: str, observed: dict, expected: dict) -> list[str]:
    failures = []
    if observed.get("tier") is None:
        failures.append(
            "tier: executor declared no recognised tier, so the result has no provenance"
        )
    selected = observed.get("selected_skill")
    wanted = expected["expected_skill"]
    if selected != wanted:
        failures.append(
            f"selected_skill: expected {wanted!r}, got {selected!r}",
        )
    return [f"{case_id}: {failure}" for failure in failures]


def evaluate(
    corpus_path: Path,
    expectations_path: Path,
    command: list[str],
    skill: str | None = None,
):
    corpus = load_json(corpus_path)
    answer_key = {
        item["case_id"]: item for item in load_json(expectations_path)["expectations"]
    }
    cases = corpus["cases"]
    if {case["id"] for case in cases} != set(answer_key):
        raise CorpusError("corpus and expectation case IDs differ")

    uncovered = set(corpus["skills"]) - {case["skill"] for case in cases}
    if uncovered:
        raise CorpusError(
            f"no cases for declared skills: {', '.join(sorted(uncovered))}"
        )

    if skill:
        cases = [case for case in cases if case["skill"] == skill]
        if not cases:
            raise CorpusError(f"no cases filed under {skill}")

    catalog = skill_catalog()
    observations = {}
    failures: list[str] = []
    for case in cases:
        observed = normalize(run_executor(command, build_payload(case, catalog)))
        observations[case["id"]] = observed
        failures.extend(grade(case["id"], observed, answer_key[case["id"]]))
    return observations, failures


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--expectations", type=Path, default=DEFAULT_EXPECTATIONS)
    parser.add_argument(
        "--executor",
        default=f"{shlex.quote(sys.executable)} {shlex.quote(str(DEFAULT_EXECUTOR))}",
        help="Fresh-process executor; receives one result-blind JSON packet on stdin",
    )
    parser.add_argument("--skill", help="Run only cases filed under this skill")
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        observations, failures = evaluate(
            args.corpus, args.expectations, shlex.split(args.executor), args.skill
        )
    except CorpusError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for case_id, observed in observations.items():
            (args.output_dir / f"{case_id}.json").write_text(
                json.dumps(observed, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )

    failed_ids = {failure.split(":", 1)[0] for failure in failures}
    tiers = sorted(
        {observed["tier"] for observed in observations.values() if observed["tier"]}
    )
    summary = {
        "total": len(observations),
        "passed": len(observations) - len(failed_ids),
        "failed": len(failed_ids),
        "failures": failures,
        "tiers": tiers,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
