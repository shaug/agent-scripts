"""Shared helpers for prepare-changesets scripts."""

from __future__ import annotations

import datetime as _dt
import json
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

DEFAULT_PLAN_PATH = Path(".prepare-changesets/plan.json")


class CommandError(RuntimeError):
    """Raised when a subprocess or git command fails."""


def run(
    cmd: Sequence[str], *, capture: bool = True, check: bool = True
) -> subprocess.CompletedProcess:
    """Run a command and return the completed process."""
    try:
        result = subprocess.run(
            list(cmd),
            text=True,
            capture_output=capture,
            check=False,
        )
    except FileNotFoundError as exc:
        raise CommandError(f"Command not found: {cmd[0]}") from exc

    if check and result.returncode != 0:
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        detail = stderr or stdout or f"exit code {result.returncode}"
        raise CommandError(f"Command failed: {' '.join(cmd)}\n{detail}")
    return result


def git(
    *args: str, capture: bool = True, check: bool = True
) -> subprocess.CompletedProcess:
    """Run a git command."""
    return run(("git",) + args, capture=capture, check=check)


def ensure_git_repo() -> None:
    git("rev-parse", "--is-inside-work-tree")


def ensure_clean_tree() -> None:
    status = git("status", "--porcelain").stdout.strip()
    if status:
        raise CommandError(
            "Working tree is not clean. Commit, stash, or discard changes first."
        )


def branch_exists(name: str) -> bool:
    result = git("rev-parse", "--verify", name, capture=True, check=False)
    return result.returncode == 0


def current_branch() -> str:
    return git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()


def merge_base(base: str, source: str) -> str:
    return git("merge-base", base, source).stdout.strip()


def diff_name_status(base: str, source: str) -> str:
    return git("diff", "--name-status", f"{base}..{source}").stdout.strip()


def diff_stat(base: str, source: str) -> str:
    return git("diff", "--stat", f"{base}..{source}").stdout.strip()


def unique_temp_branch(prefix: str) -> str:
    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{prefix}-{ts}"


def delete_branch(name: str) -> None:
    git("branch", "-D", name, check=False)


def ensure_branches_exist(branches: Iterable[str]) -> None:
    missing = [b for b in branches if not branch_exists(b)]
    if missing:
        raise CommandError("Missing branch(es):\n" + "\n".join(missing))


def branch_name_for(source_branch: str, index: int, total: int) -> str:
    return f"{source_branch}-{index}-of-{total}"


def base_for_changeset(
    base_branch: str, source_branch: str, total: int, index: int
) -> str:
    if index <= 1:
        return base_branch
    return branch_name_for(source_branch, index - 1, total)


@contextmanager
def checkout_restore(target: Optional[str] = None):
    """Checkout target branch (if provided) and always restore the original branch."""
    original = current_branch()
    try:
        if target and target != original:
            git("checkout", target)
        yield original
    finally:
        if current_branch() != original:
            git("checkout", original)


def load_plan(path: Path) -> Dict:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise CommandError(f"Plan file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CommandError(f"Invalid JSON in plan file {path}: {exc}") from exc


def validate_plan(plan: Dict) -> Tuple[bool, List[str]]:
    errors: List[str] = []

    def require_string(key: str) -> None:
        if (
            key not in plan
            or not isinstance(plan.get(key), str)
            or not str(plan[key]).strip()
        ):
            errors.append(f"Missing or invalid string field: {key}")

    require_string("feature_title")
    require_string("base_branch")
    require_string("source_branch")

    changesets = plan.get("changesets")
    if not isinstance(changesets, list) or not changesets:
        errors.append("Plan must include a non-empty 'changesets' array.")
        return False, errors

    for idx, cs in enumerate(changesets, start=1):
        if not isinstance(cs, dict):
            errors.append(f"Changeset {idx} must be an object.")
            continue

        for key in ("slug", "description", "include_paths"):
            if key not in cs:
                errors.append(f"Changeset {idx} missing required field: {key}")

        if "slug" in cs and (not isinstance(cs["slug"], str) or not cs["slug"].strip()):
            errors.append(f"Changeset {idx} has invalid slug.")
        if "description" in cs and (
            not isinstance(cs["description"], str) or not cs["description"].strip()
        ):
            errors.append(f"Changeset {idx} has invalid description.")

        include = cs.get("include_paths")
        if (
            not isinstance(include, list)
            or not include
            or not all(isinstance(p, str) for p in include)
        ):
            errors.append(
                f"Changeset {idx} include_paths must be a non-empty string array."
            )

        exclude = cs.get("exclude_paths", [])
        if exclude and (
            not isinstance(exclude, list)
            or not all(isinstance(p, str) for p in exclude)
        ):
            errors.append(
                f"Changeset {idx} exclude_paths must be a string array when provided."
            )

        pr_notes = cs.get("pr_notes", [])
        if pr_notes and (
            not isinstance(pr_notes, list)
            or not all(isinstance(p, str) for p in pr_notes)
        ):
            errors.append(
                f"Changeset {idx} pr_notes must be a string array when provided."
            )

    return (not errors), errors


def default_changeset(index: int) -> Dict:
    return {
        "slug": f"changeset-{index}",
        "description": f"Describe the intent for changeset {index}.",
        "include_paths": ["src/**"],
        "exclude_paths": [],
        "commit_message": f"changeset: placeholder {index}",
        "pr_notes": ["Replace with PR notes for this changeset."],
    }


def init_plan(
    *,
    plan_path: Path,
    base: str,
    source: str,
    title: str,
    changesets: int,
    test_cmd: str,
    force: bool,
) -> None:
    plan_path.parent.mkdir(parents=True, exist_ok=True)

    if plan_path.exists() and not force:
        raise CommandError(
            f"Plan already exists: {plan_path}. Use --force to overwrite."
        )

    plan = {
        "feature_title": title,
        "base_branch": base,
        "source_branch": source,
        "test_command": test_cmd or "",
        "changesets": [default_changeset(i) for i in range(1, changesets + 1)],
    }

    plan_path.write_text(json.dumps(plan, indent=2) + "\n")
