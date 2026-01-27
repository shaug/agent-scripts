#!/usr/bin/env python3
"""Helpers for local eval setup and grading."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Tuple

from common import DEFAULT_PLAN_PATH


def run(cmd: list[str], *, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=True)


def write_plan(plan_path: Path, plan: Dict) -> None:
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(plan, indent=2) + "\n")


def init_eval_repo() -> Tuple[Path, Dict, str]:
    """Create a temporary repo with a known base/source and plan."""
    repo_dir = Path(tempfile.mkdtemp(prefix="pcs-eval-repo-"))

    run(["git", "init", "-b", "main"], cwd=repo_dir)
    run(["git", "config", "user.name", "PCS Eval"], cwd=repo_dir)
    run(["git", "config", "user.email", "pcs-eval@example.com"], cwd=repo_dir)

    # Keep eval artifacts out of git status checks.
    (repo_dir / ".gitignore").write_text(".prepare-changesets/\n")

    (repo_dir / "a.txt").write_text("base-a\n")
    (repo_dir / "b.txt").write_text("base-b\n")
    run(["git", "add", "-A"], cwd=repo_dir)
    run(["git", "commit", "-m", "base"], cwd=repo_dir)

    run(["git", "checkout", "-b", "feature/test"], cwd=repo_dir)
    (repo_dir / "a.txt").write_text("feature-a\n")
    (repo_dir / "b.txt").write_text("feature-b\n")
    (repo_dir / "c.txt").write_text("feature-c\n")
    run(["git", "add", "-A"], cwd=repo_dir)
    run(["git", "commit", "-m", "feature"], cwd=repo_dir)

    plan: Dict = {
        "feature_title": "Eval feature",
        "base_branch": "main",
        "source_branch": "feature/test",
        "test_command": "python3 -c \"print('ok')\"",
        "changesets": [
            {
                "slug": "a-only",
                "description": "Apply a.txt changes.",
                "include_paths": ["a.txt"],
                "exclude_paths": [],
                "commit_message": "cs1",
                "pr_notes": ["No behavior changes."],
            },
            {
                "slug": "rest",
                "description": "Apply remaining changes.",
                "include_paths": ["b.txt", "c.txt"],
                "exclude_paths": [],
                "commit_message": "cs2",
                "pr_notes": ["Completes the feature."],
            },
        ],
    }

    plan_path = repo_dir / DEFAULT_PLAN_PATH
    write_plan(plan_path, plan)

    source_hash = run(
        ["git", "rev-parse", plan["source_branch"]], cwd=repo_dir
    ).stdout.strip()
    return repo_dir, plan, source_hash


def cleanup_repo(repo_dir: Path) -> None:
    shutil.rmtree(repo_dir)
