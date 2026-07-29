#!/usr/bin/env python3
"""Run repeated, result-blind review replays through a fresh process each time.

Every attempt starts a new executor process, so no state leaks between runs of
the same case. The runner owns the failure taxonomy, the timeout and
output-size limits, and the artifact directory; the executor owns nothing but
the protocol.

Exit status reports evaluation integrity, never review quality:

    0  every attempt produced a valid review or a valid blocked result
    1  at least one attempt was an evaluation failure
    2  the configuration or the corpus was rejected before any launch

Usage:
    python3 runner.py --executor "python3 path/to/executor.py" --runs 3
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in (None, ""):  # direct `python3 runner.py` invocation
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from evals import corpus, grader, protocol, report
else:
    from . import corpus, grader, protocol, report

DEFAULT_TIMEOUT_SECONDS = 900.0
DEFAULT_MAX_OUTPUT_BYTES = 4_000_000
FIXTURE_EXECUTOR = Path(__file__).with_name("fixture_executor.py")
TARGET_SKILL_ROOT = protocol.REPOSITORY_ROOT / "skills"


class ConfigurationError(ValueError):
    """Raised for an unusable executor command, limit, or output location."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _skill_documents(skill: str, skill_root: Path) -> dict[str, str]:
    """One skill's reviewer-visible Markdown, namespaced by skill name.

    The bundled `references/review-suite/` mirror is excluded: `contract_documents`
    already supplies those files from their canonical location.
    """
    root = skill_root / skill
    skill_md = root / "SKILL.md"
    if not skill_md.is_file():
        raise ConfigurationError(f"missing target skill prompt {skill_md}")
    documents = {f"{skill}/SKILL.md": skill_md.read_text()}
    references = root / "references"
    if references.is_dir():
        for path in sorted(references.rglob("*.md")):
            relative = path.relative_to(root)
            if "review-suite" in relative.parts:
                continue
            documents[f"{skill}/{relative.as_posix()}"] = path.read_text()
    return documents


def target_skill_documents(
    target_skill: str,
    dependencies: Sequence[str] = (),
    *,
    skill_root: Path = TARGET_SKILL_ROOT,
) -> dict[str, str]:
    """Return the target skill's declared dependency closure as text.

    A skill's `SKILL.md` is not the whole skill, in two distinct ways.

    It links references that it instructs the reviewer to read - for
    `review-code-change`, `references/orchestration-protocol.md`, which owns the
    lens decision table, deduplication, and verdict aggregation.

    It also declares sibling skills it cannot work without: `review-code-change`
    requires `review-solution-simplicity`, `review-correctness`, and
    `review-code-simplicity` to be available and readable, and mandates an
    aggregate `blocked` result naming any that are missing. An executor is told
    to reason only from what it is given, so a target whose contract requires
    siblings can only be evaluated when those siblings are in the payload.
    Omitting them inverts the measurement: a reviewer that correctly refuses for
    missing dependencies is scored wrong on every case that expects a merge
    verdict, so recall moves the wrong way as the reviewer becomes more
    compliant.

    The corpus declares the closure so a target can be swapped without changing
    this code. Which target a scored corpus should measure, and the cost envelope
    that follows from its closure, are corpus-composition decisions.

    `skill_root` defaults to the repository's real, shipped `skills/` tree.
    A caller may point it at an alternate directory that mirrors that tree with
    one skill's `SKILL.md` deliberately altered - the only supported way to run
    a mechanism ablation (for example, a pass disabled/no-op) without editing
    the shipped skill itself. The override is recorded verbatim in the report's
    `configuration.skill_root`, so an ablation run can never be mistaken for a
    standard-configuration one.
    """
    documents = _skill_documents(target_skill, skill_root)
    for dependency in dependencies:
        if dependency == target_skill:
            raise ConfigurationError(f"{target_skill} declares itself as a dependency")
        documents.update(_skill_documents(dependency, skill_root))
    return documents


def render_skill_prompt(target_skill: str, documents: Mapping[str, str]) -> str:
    """Lay out a skill closure as one prompt, target first and clearly named.

    Every section is labelled, including the target's own `SKILL.md`: once a
    payload carries several skills, a reviewer has to be able to tell which one
    it is being asked to execute and which are its dependencies.
    """
    remaining = dict(documents)
    lead = f"{target_skill}/SKILL.md"
    sections = [f"## Target skill: {lead}\n\n{remaining.pop(lead)}"]
    for name, text in sorted(remaining.items()):
        sections.append(f"\n\n## Skill reference: {name}\n\n{text}")
    return "".join(sections)


def target_skill_prompt(
    target_skill: str,
    dependencies: Sequence[str] = (),
    *,
    skill_root: Path = TARGET_SKILL_ROOT,
) -> str:
    """Render the target skill and its whole declared closure as one prompt.

    `prompt_digest` hashes this string, so the recorded `target_skill_digest`
    changes whenever any part of the evaluated skill text changes - which is the
    whole point of pinning it across baseline strata.
    """
    return render_skill_prompt(
        target_skill,
        target_skill_documents(target_skill, dependencies, skill_root=skill_root),
    )


def contract_documents() -> dict[str, str]:
    """Reviewer-visible contract text every attempt receives verbatim."""
    return {
        "CONTRACT.md": (protocol.REVIEW_SUITE / "CONTRACT.md").read_text(),
        "review-packet.schema.json": (
            protocol.REVIEW_SUITE / "contracts" / "review-packet.schema.json"
        ).read_text(),
        "review-result.schema.json": (
            protocol.REVIEW_SUITE / "contracts" / "review-result.schema.json"
        ).read_text(),
    }


def suite_commit() -> str:
    """Return the exact suite commit, or an explicit unavailable marker."""
    completed = subprocess.run(
        ["git", "-C", str(protocol.REPOSITORY_ROOT), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode:
        return "unavailable"
    return completed.stdout.strip() or "unavailable"


def is_bundled_fixture_executor(command: list[str]) -> bool:
    """Detect the deterministic executor regardless of what it self-reports."""
    return any(Path(part).name == FIXTURE_EXECUTOR.name for part in command)


def run_attempt(
    command: list[str],
    request: dict[str, Any],
    case: corpus.Case,
    *,
    timeout: float,
    max_output_bytes: int,
    forced_simulation: bool,
) -> tuple[dict[str, Any], dict[str, Any] | None, str, str]:
    """Execute one fresh process and classify exactly what came back."""
    payload = json.dumps(request)
    started_at = _now()
    start = time.monotonic()
    stdout = ""
    stderr = ""
    try:
        completed = subprocess.run(
            command,
            input=payload,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        stdout, stderr = completed.stdout, completed.stderr
        returncode: int | None = completed.returncode
        if returncode:
            status, response, detail = (
                "runtime_failure",
                None,
                f"executor exited {returncode}: {stderr.strip()[-500:]}",
            )
        elif len(stdout.encode("utf-8")) > max_output_bytes:
            status, response, detail = (
                "output_too_large",
                None,
                f"stdout exceeded {max_output_bytes} bytes",
            )
        else:
            status, response, detail = protocol.classify_response(case.packet, stdout)
    except subprocess.TimeoutExpired:
        returncode = None
        status, response, detail = (
            "timeout",
            None,
            f"executor exceeded {timeout} seconds",
        )
    except OSError as error:
        returncode = None
        status, response, detail = ("spawn_failure", None, str(error))

    duration = time.monotonic() - start
    executor_identity = (response or {}).get("executor") or {}
    attempt = {
        "case_id": case.case_id,
        "case_ref": request["run"]["case_ref"],
        "run_number": request["run"]["run_number"],
        "status": status,
        "detail": detail,
        "simulation": forced_simulation or bool((response or {}).get("simulation")),
        "protocol_version": protocol.PROTOCOL_VERSION,
        "suite_commit": request["run"]["suite_commit"],
        "corpus_version": request["run"]["corpus_version"],
        "target_skill_digest": request["target_skill_digest"],
        "candidate": request["run"]["candidate"],
        "executor": executor_identity,
        "usage": (response or {}).get("usage"),
        "verdict": ((response or {}).get("result") or {}).get("verdict"),
        "returncode": returncode,
        "started_at": started_at,
        "finished_at": _now(),
        "duration_seconds": duration,
        "grade": None,
    }
    return attempt, response, stdout, stderr


def _artifact_stem(case_id: str, run_number: int) -> str:
    return f"{case_id}.run-{run_number}"


def _write_artifacts(
    artifact_dir: Path, attempt: dict[str, Any], stdout: str, stderr: str
) -> None:
    name = _artifact_stem(attempt["case_id"], attempt["run_number"])
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / f"{name}.stdout.json").write_text(stdout)
    if stderr:
        (artifact_dir / f"{name}.stderr.txt").write_text(stderr)


def refuse_to_overwrite_artifacts(
    artifact_dir: Path, loaded: corpus.Corpus, runs: int
) -> None:
    """Fail before launch when a run would destroy retained raw output.

    Retained executor output is a controlled artifact: a calibrated formulation
    cites the raw attempt it was drawn from, and an aggregate report cites the
    attempts behind its figures. The artifact name carries the case and run
    number but not the corpus version, so re-running a stratum into the same
    directory silently replaced the very output an earlier record cited - which
    happened once, and cost a calibration source run.

    Checked here rather than at write time on purpose. Raising after the first
    attempt would already have spent money, and this is the one command that can.
    """
    collisions = [
        artifact_dir / f"{_artifact_stem(case.case_id, run_number)}.stdout.json"
        for case in loaded.cases
        for run_number in range(1, runs + 1)
    ]
    existing = [path for path in collisions if path.exists()]
    if existing:
        raise ConfigurationError(
            f"{len(existing)} retained artifact(s) would be overwritten, starting "
            f"with {existing[0]}. Retained output is evidence a committed record "
            f"may already cite. Pass a distinct --artifact-dir, for example one "
            f"scoped by corpus version ({loaded.corpus_version})."
        )


def evaluate(
    command: list[str],
    *,
    corpus_root: Path | None,
    runs: int,
    timeout: float,
    max_output_bytes: int,
    artifact_dir: Path | None,
    skill_root: Path = TARGET_SKILL_ROOT,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Audit the corpus, then replay every case the configured number of times.

    `skill_root` defaults to the repository's real `skills/` tree. Passing an
    alternate directory is the only supported way to run a mechanism ablation
    (a pass deliberately disabled/no-op in one skill's `SKILL.md`) without
    editing the shipped skill; see `target_skill_documents` for the full
    contract. The resolved root is always recorded in the returned
    `configuration`, so an ablation run is never indistinguishable from a
    standard-configuration one.
    """
    loaded = corpus.load_corpus(corpus_root)
    if loaded.grader_version != grader.GRADER_VERSION:
        raise corpus.CorpusError(
            f"corpus grader_version {loaded.grader_version!r} does not match the "
            f"shipped grader {grader.GRADER_VERSION!r}"
        )
    # Keep the closure's exact membership, not just its digest: a digest proves
    # two runs sent the same text but cannot say what that text was, and a
    # baseline stratum has to be able to state which skills it evaluated.
    closure = target_skill_documents(
        loaded.target_skill, loaded.target_skill_dependencies, skill_root=skill_root
    )
    skill_prompt = render_skill_prompt(loaded.target_skill, closure)
    documents = contract_documents()
    commit = suite_commit()
    forced_simulation = is_bundled_fixture_executor(command)

    def build(case: corpus.Case, run_number: int) -> dict[str, Any]:
        return protocol.build_request(
            case_id=case.case_id,
            target_skill=loaded.target_skill,
            skill_prompt=skill_prompt,
            contract_documents=documents,
            instructions=case.instructions,
            packet=case.packet,
            run_number=run_number,
            suite_commit=commit,
            corpus_version=loaded.corpus_version,
            started_at=_now(),
        )

    def refuse_if_contaminated(case: corpus.Case, request: dict[str, Any]) -> None:
        contamination = protocol.audit_request(
            request,
            case_id=case.case_id,
            expectation=case.expectation,
            provenance=case.provenance,
        )
        if contamination:
            raise corpus.CorpusError(
                f"{case.case_id}: contaminated request: " + "; ".join(contamination)
            )

    # Audit every case before launching anything. A per-request check alone
    # would let a contaminated last case bill a real review for every earlier
    # case and then discard the whole run, which contradicts the rule that a
    # contaminated case fails before executor launch. Nothing `audit_request`
    # inspects varies by run, so one request per case settles it.
    for case in loaded.cases:
        refuse_if_contaminated(case, build(case, 1))

    if artifact_dir is not None:
        refuse_to_overwrite_artifacts(artifact_dir, loaded, runs)

    attempts: list[dict[str, Any]] = []
    for case in loaded.cases:
        for run_number in range(1, runs + 1):
            request = build(case, run_number)
            # Kept as defence in depth: the pre-flight pass above is what
            # guarantees the ordering, this re-check guarantees that the exact
            # payload handed to a process was audited.
            refuse_if_contaminated(case, request)

            attempt, response, stdout, stderr = run_attempt(
                command,
                request,
                case,
                timeout=timeout,
                max_output_bytes=max_output_bytes,
                forced_simulation=forced_simulation,
            )
            attempt["target_skill"] = loaded.target_skill
            attempt["target_skill_dependencies"] = list(
                loaded.target_skill_dependencies
            )
            if attempt["status"] in protocol.GRADABLE_STATUSES:
                attempt["grade"] = grader.grade(
                    case.expectation, (response or {})["result"]
                )
            if artifact_dir is not None:
                _write_artifacts(artifact_dir, attempt, stdout, stderr)
            attempts.append(attempt)

    configuration = {
        "executor": shlex.join(command),
        "corpus_version": loaded.corpus_version,
        "grader_version": loaded.grader_version,
        "target_skill": loaded.target_skill,
        "target_skill_dependencies": list(loaded.target_skill_dependencies),
        "target_skill_documents": sorted(closure),
        "target_skill_digest": protocol.prompt_digest(skill_prompt),
        "skill_root": str(skill_root),
        "suite_commit": commit,
        # The stratum the corpus declares, carried verbatim. A report that names
        # its target and closure but not its stratum cannot say which ground
        # truth its expectations came from, whether it is scored, or whether its
        # grading is a signal at all - so those properties would survive only as
        # prose in some other file, and a report quoted on its own would silently
        # lose them. `None` on a corpus that predates stratum labelling.
        "stratum": loaded.stratum,
        # Derived from the attempts rather than declared, because a stratum
        # without a model identity is not comparable with any other. More than
        # one model in this list means the run spans strata.
        "executor_models": sorted(
            {
                model
                for attempt in attempts
                if (model := (attempt.get("executor") or {}).get("model"))
            }
        ),
        "runs_per_case": runs,
        "cases": len(loaded.cases),
        "timeout_seconds": timeout,
        "max_output_bytes": max_output_bytes,
        "artifacts_retained": artifact_dir is not None,
    }
    return attempts, configuration


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--executor",
        required=True,
        help="Fresh-process command receiving one result-blind JSON request on stdin",
    )
    parser.add_argument("--corpus", type=Path, default=None)
    parser.add_argument(
        "--skill-root",
        type=Path,
        default=None,
        help=(
            "Directory mirroring the repository's skills/ tree, used instead of "
            "it. The only supported way to run a mechanism ablation (a pass "
            "deliberately disabled/no-op in one skill's SKILL.md) without "
            "editing the shipped skill. Defaults to the real skills/ tree; "
            "always recorded verbatim in the report's configuration.skill_root."
        ),
    )
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument(
        "--max-output-bytes", type=int, default=DEFAULT_MAX_OUTPUT_BYTES
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help="Opt-in directory for captured raw executor output",
    )
    parser.add_argument("--attempts-out", type=Path, default=None)
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument(
        "--baseline-report",
        type=Path,
        default=None,
        help="Write a frozen baseline report; refused for a simulated run",
    )
    return parser


def _validated_command(raw: str) -> list[str]:
    command = shlex.split(raw)
    if not command:
        raise ConfigurationError("--executor is empty")
    return command


def _check_limits(args: argparse.Namespace) -> None:
    if args.runs < 1:
        raise ConfigurationError("--runs must be at least 1")
    if args.timeout <= 0:
        raise ConfigurationError("--timeout must be greater than 0")
    if args.max_output_bytes < 1:
        raise ConfigurationError("--max-output-bytes must be at least 1")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        command = _validated_command(args.executor)
        _check_limits(args)
        attempts, configuration = evaluate(
            command,
            corpus_root=args.corpus,
            runs=args.runs,
            timeout=args.timeout,
            max_output_bytes=args.max_output_bytes,
            artifact_dir=args.artifact_dir,
            skill_root=args.skill_root or TARGET_SKILL_ROOT,
        )
    except (ConfigurationError, corpus.CorpusError, grader.GradingError) as error:
        print(f"evaluation rejected: {error}", file=sys.stderr)
        return 2

    aggregate = report.aggregate(attempts, configuration=configuration)

    if args.attempts_out:
        args.attempts_out.parent.mkdir(parents=True, exist_ok=True)
        args.attempts_out.write_text(
            "".join(json.dumps(attempt, sort_keys=True) + "\n" for attempt in attempts)
        )
    if args.report_out:
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_out.write_text(
            json.dumps(aggregate, indent=2, sort_keys=True) + "\n"
        )
    if args.baseline_report:
        if not aggregate["baseline_eligible"]:
            print(
                "baseline refused: a simulated run cannot produce a baseline report",
                file=sys.stderr,
            )
            return 2
        args.baseline_report.parent.mkdir(parents=True, exist_ok=True)
        args.baseline_report.write_text(
            json.dumps(aggregate, indent=2, sort_keys=True) + "\n"
        )

    print(json.dumps(aggregate, indent=2, sort_keys=True))
    evaluation_failures = [
        f"{attempt['case_id']} run {attempt['run_number']}: "
        f"{attempt['status']}: {attempt['detail']}"
        for attempt in attempts
        if attempt["status"] in protocol.EVALUATION_FAILURE_STATUSES
    ]
    for failure in evaluation_failures:
        print(failure, file=sys.stderr)
    return 1 if evaluation_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
