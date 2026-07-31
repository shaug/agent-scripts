"""Shared test fixtures for review-fix-loop's `local_commit` and `update_pr`
end-to-end test suites (`test_local_commit.py`, `test_update_pr.py`).

Mirrors this repository's own `carve-changesets/scripts/tests/helpers.py`
precedent: fixture plumbing used by more than one test module in the same
skill lives in one sibling `helpers.py`, so a real scenario difference
between the two suites shows up as a difference in test code, not as
copy-pasted setup that has to be kept in sync by hand.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parents[2]


def load_module(name: str, filename: str):
    """Load one of this skill's bundled `scripts/<filename>` modules under a
    dedicated `sys.modules` name, matching the dependency-free
    importlib-loading convention every script in this skill already uses."""
    spec = importlib.util.spec_from_file_location(
        name, SKILL_ROOT / "scripts" / filename
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# A dedicated `local_commit.py` load for this module's own use of `LE.git`
# and the `ReviewPass`/`FixDecision` dataclasses below. Every fixture here is
# duck-typed (attribute access only, never `isinstance`), so constructing a
# `ReviewPass`/`FixDecision` from this module's own load is exactly as valid
# to either suite's separately loaded `LC`/`UP.LC` as one built from that
# suite's own load — see `local_commit.py`'s own module docstring for why
# cross-module-instance duck-typing is safe throughout this skill's engine.
LC = load_module("review_fix_loop_test_helpers_local_commit", "local_commit.py")
LE = LC.LE


def init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    LE.git("init", "-q", "-b", "main", cwd=path)
    LE.git("config", "user.email", "test@example.com", cwd=path)
    LE.git("config", "user.name", "Test", cwd=path)
    (path / "README.md").write_text("initial\n")
    LE.git("add", "-A", cwd=path)
    LE.git("commit", "-q", "-m", "initial commit", cwd=path)


ALWAYS_PASS_VALIDATION = [
    {"name": "focused unit test", "command": "true", "scope": "focused"},
    {"name": "full repository gate", "command": "true", "scope": "full"},
]

CLEAN_TEMPLATE = {
    "schema_version": "1.4",
    "lens": "aggregate",
    "verdict": "clean",
    "findings": [],
    "blocking_reasons": [],
    "validation_limitations": [],
    "next_action": "No changes are required.",
}

FINDING_ID = "correctness-001"


def finding() -> dict[str, Any]:
    return {
        "id": FINDING_ID,
        "lens": "correctness",
        "severity": "blocking",
        "confidence": "high",
        "rule": "example rule",
        "evidence": [
            {"location": "marker.txt:1", "detail": "marker.txt is not 'fixed'"}
        ],
        "concern": "marker.txt does not read 'fixed'",
        "impact": "the candidate is incomplete",
        "proposed_change": "write 'fixed' into marker.txt",
        "expected_effect": "marker.txt reads 'fixed'",
    }


def make_marker_reviewer(repo: Path):
    """A fake reviewer whose verdict is a real function of `marker.txt`'s
    content at the exact head it is asked to review: `clean` once it reads
    'fixed', `changes_required` with one `FINDING_ID` finding otherwise.
    Shared by both the `local_commit` and `update_pr` end-to-end suites."""

    def reviewer(
        *, packet, briefing, head_sha, comparison_base_sha, independence, sequence
    ):
        del packet, briefing, independence, sequence
        content = LE.git("show", f"{head_sha}:marker.txt", cwd=repo).stdout.strip()
        candidate = {"head_sha": head_sha, "comparison_base_sha": comparison_base_sha}
        if content == "fixed":
            result = {
                **CLEAN_TEMPLATE,
                "candidate": candidate,
                "lens_executions": [
                    {
                        "lens": lens,
                        "head_sha": head_sha,
                        "comparison_base_sha": comparison_base_sha,
                        "verdict": "clean",
                        "freshly_executed": True,
                    }
                    for lens in (
                        "solution_simplicity",
                        "correctness",
                        "code_simplicity",
                    )
                ],
            }
        else:
            result = {
                **CLEAN_TEMPLATE,
                "candidate": candidate,
                "verdict": "changes_required",
                "findings": [finding()],
                "lens_executions": [
                    {
                        "lens": "solution_simplicity",
                        "head_sha": head_sha,
                        "comparison_base_sha": comparison_base_sha,
                        "verdict": "clean",
                        "freshly_executed": True,
                    }
                ],
                "next_action": f"Fix {FINDING_ID}.",
            }
        return LC.ReviewPass(result=result)

    return reviewer


def make_clean_reviewer():
    """A fake reviewer that always reports a clean aggregate verdict,
    regardless of candidate content. Used where a suite only needs immediate
    convergence and does not care about `marker.txt`'s content."""

    def reviewer(
        *, packet, briefing, head_sha, comparison_base_sha, independence, sequence
    ):
        del packet, briefing, independence, sequence
        candidate = {"head_sha": head_sha, "comparison_base_sha": comparison_base_sha}
        result = {
            **CLEAN_TEMPLATE,
            "candidate": candidate,
            "lens_executions": [
                {
                    "lens": lens,
                    "head_sha": head_sha,
                    "comparison_base_sha": comparison_base_sha,
                    "verdict": "clean",
                    "freshly_executed": True,
                }
                for lens in ("solution_simplicity", "correctness", "code_simplicity")
            ],
        }
        return LC.ReviewPass(result=result)

    return reviewer


def fixing_apply_fix(*, finding, attempt_path, change_contract, attempt_number):
    del finding, change_contract, attempt_number
    (attempt_path / "marker.txt").write_text("fixed\n")
    return f"fix: resolve {FINDING_ID}"


def accepting_decide(*, finding, change_contract, attempt_number):
    del change_contract, attempt_number
    return LC.FixDecision(
        disposition="accepted", rationale=f"{finding['id']} is tractable"
    )
