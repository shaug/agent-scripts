from __future__ import annotations

import json
import os
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in os.sys.path:
    os.sys.path.insert(0, str(SCRIPTS_DIR))


def run(
    cmd: list[str], *, cwd: Path, check: bool = True
) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=check)


def commit(cwd: Path, message: str, *, allow_empty: bool = False) -> None:
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as message_file:
        message_file.write(message + "\n")
        message_file.flush()
        command = ["git", "commit", "-F", message_file.name]
        if allow_empty:
            command.append("--allow-empty")
        run(command, cwd=cwd)


@contextmanager
def chdir(path: Path):
    original = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(original)


def init_repo() -> tuple[Path, dict]:
    repo_dir = Path(tempfile.mkdtemp(prefix="pcs-test-repo-"))

    run(["git", "init", "-b", "main"], cwd=repo_dir)
    run(["git", "config", "user.name", "PCS Test"], cwd=repo_dir)
    run(["git", "config", "user.email", "pcs-test@example.com"], cwd=repo_dir)

    # Keep recordkeeping artifacts out of git status checks.
    (repo_dir / ".gitignore").write_text(".carve-changesets/\n")

    (repo_dir / "a.txt").write_text("base-a\n")
    (repo_dir / "b.txt").write_text("base-b\n")
    run(["git", "add", "-A"], cwd=repo_dir)
    commit(repo_dir, "base")

    run(["git", "checkout", "-b", "feature/test"], cwd=repo_dir)
    (repo_dir / "a.txt").write_text("feature-a\n")
    (repo_dir / "b.txt").write_text("feature-b\n")
    (repo_dir / "c.txt").write_text("feature-c\n")
    run(["git", "add", "-A"], cwd=repo_dir)
    commit(repo_dir, "feature")

    plan = {
        "feature_title": "Test feature",
        "base_branch": "main",
        "source_branch": "feature/test",
        "test_command": "",
        "changesets": [
            {
                "slug": "a-only",
                "description": "Apply a.txt changes.",
                "include_paths": ["a.txt"],
                "exclude_paths": [],
                "commit_message": "cs1",
                "pr_notes": ["note"],
            },
            {
                "slug": "rest",
                "description": "Apply remaining changes.",
                "include_paths": ["b.txt", "c.txt"],
                "exclude_paths": [],
                "commit_message": "cs2",
                "pr_notes": ["note"],
            },
        ],
    }

    return repo_dir, plan


def init_conflict_repo() -> tuple[Path, dict]:
    repo_dir = Path(tempfile.mkdtemp(prefix="pcs-test-conflict-"))

    run(["git", "init", "-b", "main"], cwd=repo_dir)
    run(["git", "config", "user.name", "PCS Test"], cwd=repo_dir)
    run(["git", "config", "user.email", "pcs-test@example.com"], cwd=repo_dir)

    (repo_dir / ".gitignore").write_text(".carve-changesets/\n")

    (repo_dir / "conflict.txt").write_text("line\n")
    run(["git", "add", "-A"], cwd=repo_dir)
    commit(repo_dir, "base")

    run(["git", "checkout", "-b", "feature/conflict"], cwd=repo_dir)
    (repo_dir / "conflict.txt").write_text("feature-change\n")
    run(["git", "add", "conflict.txt"], cwd=repo_dir)
    commit(repo_dir, "feature change")

    run(["git", "checkout", "main"], cwd=repo_dir)
    (repo_dir / "conflict.txt").write_text("main-change\n")
    run(["git", "add", "conflict.txt"], cwd=repo_dir)
    commit(repo_dir, "main change")

    plan = {
        "feature_title": "Conflict feature",
        "base_branch": "main",
        "source_branch": "feature/conflict",
        "test_command": "",
        "changesets": [
            {
                "slug": "conflict",
                "description": "Conflicting change.",
                "include_paths": ["conflict.txt"],
                "exclude_paths": [],
                "commit_message": "cs1",
                "pr_notes": ["note"],
            }
        ],
    }

    return repo_dir, plan


def init_remote(repo_dir: Path) -> Path:
    remote_dir = Path(tempfile.mkdtemp(prefix="pcs-test-remote-")) / "remote.git"
    run(["git", "init", "--bare", str(remote_dir)], cwd=repo_dir)
    run(["git", "remote", "add", "origin", str(remote_dir)], cwd=repo_dir)
    return remote_dir


def write_plan(plan_path: Path, plan: dict) -> None:
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(plan, indent=2) + "\n")
