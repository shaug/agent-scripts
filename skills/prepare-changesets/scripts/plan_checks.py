#!/usr/bin/env python3
"""Strict plan validation and consistency checks."""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from common import (
    CommandError,
    branch_exists,
    diff_name_status,
    git,
    load_state,
    repo_root,
)
from patch_apply import build_diff, parse_hunk_selectors, select_hunks_for_changeset


def _changed_paths(base: str, source: str) -> List[str]:
    raw = diff_name_status(base, source)
    paths: List[str] = []
    for line in raw.splitlines():
        parts = line.split("\t")
        if not parts:
            continue
        code = parts[0][:1]
        if code == "R" and len(parts) >= 3:
            paths.append(parts[1])
            paths.append(parts[2])
        elif len(parts) >= 2:
            paths.append(parts[1])
    return paths


def _matches_any(path: str, patterns: Sequence[str]) -> bool:
    for pattern in patterns:
        if fnmatch.fnmatch(path, pattern):
            return True
    return False


def _warn_placeholders(changeset: Dict, index: int, warnings: List[str]) -> None:
    slug = str(changeset.get("slug", "")).strip()
    if slug.startswith("changeset-") or slug.startswith("cs-"):
        warnings.append(f"Changeset {index}: slug looks like a placeholder.")

    pr_notes = changeset.get("pr_notes", [])
    if isinstance(pr_notes, list):
        for note in pr_notes:
            if isinstance(note, str) and "replace with" in note.lower():
                warnings.append(
                    f"Changeset {index}: pr_notes contains placeholder text."
                )
                break

    commit_message = str(changeset.get("commit_message", "")).strip().lower()
    if "placeholder" in commit_message:
        warnings.append(f"Changeset {index}: commit_message looks like a placeholder.")


def _validate_paths_mode(
    *,
    base: str,
    source: str,
    changeset: Dict,
    index: int,
    errors: List[str],
) -> None:
    include = changeset.get("include_paths", [])
    exclude = changeset.get("exclude_paths", [])
    if not include:
        errors.append(
            f"Changeset {index}: include_paths must be non-empty for mode=paths."
        )
        return
    changed = _changed_paths(base, source)
    matched = []
    for path in changed:
        if _matches_any(path, include) and not _matches_any(path, exclude):
            matched.append(path)
    if not matched:
        errors.append(
            f"Changeset {index}: include_paths did not match any changed files."
        )


def _validate_patch_mode(*, changeset: Dict, index: int, errors: List[str]) -> None:
    patch_file = changeset.get("patch_file")
    if not isinstance(patch_file, str) or not patch_file.strip():
        errors.append(f"Changeset {index}: patch_file must be a non-empty string.")
        return
    path = Path(patch_file)
    if not path.is_absolute():
        path = repo_root() / path
    if not path.exists():
        errors.append(f"Changeset {index}: patch_file not found: {path}")
        return
    if path.stat().st_size == 0:
        errors.append(f"Changeset {index}: patch_file is empty: {path}")


def _validate_hunks_mode(
    *,
    base: str,
    source: str,
    changeset: Dict,
    index: int,
    errors: List[str],
) -> None:
    selectors = changeset.get("hunk_selectors", [])
    try:
        parsed = parse_hunk_selectors(selectors, changeset_label=f"Changeset {index}")
    except CommandError as exc:
        errors.append(str(exc))
        return

    include = changeset.get("include_paths", [])
    exclude = changeset.get("exclude_paths", [])
    allow_partial = bool(changeset.get("allow_partial_files", True))
    diff_files = build_diff(base, source)
    try:
        select_hunks_for_changeset(
            diff_files,
            parsed,
            include_paths=include,
            exclude_paths=exclude,
            allow_partial_files=allow_partial,
            changeset_label=f"Changeset {index}",
        )
    except CommandError as exc:
        errors.append(str(exc))


def _warn_state_drift(plan: Dict, warnings: List[str]) -> None:
    state = load_state()
    if not state:
        return

    source = plan.get("source_branch", "")
    if isinstance(source, str) and source:
        try:
            current = git("rev-parse", source).stdout.strip()
        except CommandError:
            current = ""
        recorded = str(state.get("source_head", "")).strip()
        if current and recorded and current != recorded:
            warnings.append(
                "Source branch HEAD differs from recorded state.json. "
                "Re-validate changeset boundaries before continuing."
            )

    recorded_changesets = state.get("changesets", [])
    if not isinstance(recorded_changesets, list):
        return

    for entry in recorded_changesets:
        if not isinstance(entry, dict):
            continue
        branch = str(entry.get("branch", "")).strip()
        head = str(entry.get("head", "")).strip()
        if not branch or not head:
            continue
        if not branch_exists(branch):
            warnings.append(f"Recorded branch missing: {branch}")
            continue
        current = git("rev-parse", branch).stdout.strip()
        if current != head:
            warnings.append(
                f"Branch head drift detected for {branch}. "
                "Avoid rewriting earlier changeset branches."
            )


def validate_plan_strict(plan: Dict) -> Tuple[bool, List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []

    base = str(plan.get("base_branch", "")).strip()
    source = str(plan.get("source_branch", "")).strip()
    if not base or not source:
        errors.append("Plan missing base_branch or source_branch.")
        return False, errors, warnings

    changesets = plan.get("changesets")
    if not isinstance(changesets, list):
        errors.append("Plan missing changesets array.")
        return False, errors, warnings

    for idx, cs in enumerate(changesets, start=1):
        if not isinstance(cs, dict):
            errors.append(f"Changeset {idx} must be an object.")
            continue
        mode = str(cs.get("mode", "paths")).strip() or "paths"
        if mode == "paths":
            _validate_paths_mode(
                base=base, source=source, changeset=cs, index=idx, errors=errors
            )
        elif mode == "patch":
            _validate_patch_mode(changeset=cs, index=idx, errors=errors)
        elif mode == "hunks":
            _validate_hunks_mode(
                base=base, source=source, changeset=cs, index=idx, errors=errors
            )
        else:
            errors.append(
                f"Changeset {idx}: unsupported mode '{mode}'. Use 'paths', 'patch', or 'hunks'."
            )

        _warn_placeholders(cs, idx, warnings)

    test_cmd = str(plan.get("test_command", "")).strip()
    if not test_cmd:
        warnings.append("Plan test_command is empty; set it or pass --test-cmd.")

    _warn_state_drift(plan, warnings)

    return (not errors), errors, warnings
