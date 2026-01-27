#!/usr/bin/env python3
"""Changeset chain creation, comparison, and validation."""

from __future__ import annotations

import fnmatch
import subprocess
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from common import (
    CommandError,
    branch_name_for,
    checkout_restore,
    delete_branch,
    diff_name_status,
    diff_stat,
    ensure_branches_exist,
    ensure_clean_tree,
    ensure_git_repo,
    git,
    unique_temp_branch,
)


@dataclass
class DiffEntry:
    status: str
    path: str
    old_path: Optional[str] = None


def _matches_any(path: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(path, pat) for pat in patterns)


def changed_files_between(base: str, source: str) -> List[DiffEntry]:
    raw = diff_name_status(base, source)
    entries: List[DiffEntry] = []
    if not raw:
        return entries

    for line in raw.splitlines():
        parts = line.split("\t")
        if not parts:
            continue
        status = parts[0]
        code = status[0]
        if code == "R" and len(parts) >= 3:
            entries.append(DiffEntry(status=code, path=parts[2], old_path=parts[1]))
        elif len(parts) >= 2:
            entries.append(DiffEntry(status=code, path=parts[1]))
    return entries


def select_entries(
    entries: Sequence[DiffEntry], include: Sequence[str], exclude: Sequence[str]
) -> List[DiffEntry]:
    if not include:
        return []

    selected = [
        e
        for e in entries
        if _matches_any(e.path, include)
        or (e.old_path and _matches_any(e.old_path, include))
    ]
    if not exclude:
        return selected

    filtered: List[DiffEntry] = []
    for e in selected:
        if _matches_any(e.path, exclude):
            continue
        if e.old_path and _matches_any(e.old_path, exclude):
            continue
        filtered.append(e)
    return filtered


def apply_changeset(
    *, base_branch: str, source_branch: str, index: int, total: int, changeset: Dict
) -> Tuple[int, int]:
    include = changeset.get("include_paths", [])
    exclude = changeset.get("exclude_paths", [])

    diff_entries = changed_files_between(base_branch, source_branch)
    selected = select_entries(diff_entries, include, exclude)

    if not selected:
        print(f"[WARN] Changeset {index}: no files matched include/exclude rules.")
        return 0, 0

    checkout_paths: List[str] = []
    delete_paths: List[str] = []

    for entry in selected:
        if entry.status == "D":
            delete_paths.append(entry.path)
            continue
        if (
            entry.old_path
            and entry.old_path != entry.path
            and entry.old_path not in delete_paths
        ):
            delete_paths.append(entry.old_path)
        checkout_paths.append(entry.path)

    for path in checkout_paths:
        git("checkout", source_branch, "--", path)

    for path in delete_paths:
        git("rm", "-f", "--ignore-unmatch", path)

    git("add", "-A")

    diff_cached = git("diff", "--cached", "--quiet", check=False)
    if diff_cached.returncode == 0:
        print(f"[WARN] Changeset {index}: no staged changes after apply.")
        return len(checkout_paths), len(delete_paths)

    commit_message = changeset.get("commit_message")
    if not isinstance(commit_message, str) or not commit_message.strip():
        slug = str(changeset.get("slug", f"cs-{index}")).strip() or f"cs-{index}"
        commit_message = f"changeset {index} of {total}: {slug}"

    git("commit", "-m", commit_message)
    return len(checkout_paths), len(delete_paths)


def create_chain(plan: Dict) -> List[str]:
    ensure_git_repo()
    ensure_clean_tree()

    base = plan["base_branch"]
    source = plan["source_branch"]
    changesets = plan["changesets"]
    total = len(changesets)

    chain = [branch_name_for(source, i, total) for i in range(1, total + 1)]
    ensure_branches_exist([base, source])

    with checkout_restore() as original:
        print(f"[INFO] Starting from current branch: {original}")
        prev_branch = base
        for idx, cs in enumerate(changesets, start=1):
            name = chain[idx - 1]
            print(f"\n[STEP] Creating {name} from {prev_branch}")
            git("checkout", "-B", name, prev_branch)

            applied, deleted = apply_changeset(
                base_branch=base,
                source_branch=source,
                index=idx,
                total=total,
                changeset=cs,
            )
            print(
                f"[OK] Applied changeset {idx}: {applied} paths checked out, {deleted} paths removed"
            )
            prev_branch = name

    print("[OK] Changeset branch chain created.")
    return chain


def compare_chain(plan: Dict) -> Tuple[str, str]:
    ensure_git_repo()
    ensure_clean_tree()

    base = plan["base_branch"]
    source = plan["source_branch"]
    total = len(plan["changesets"])

    chain = [branch_name_for(source, i, total) for i in range(1, total + 1)]
    ensure_branches_exist([base, source, *chain])

    temp_branch = unique_temp_branch("pcs-temp-compare")
    print(f"[INFO] Creating temporary comparison branch: {temp_branch}")

    with checkout_restore() as original:
        try:
            git("checkout", "-B", temp_branch, base)
            for name in chain:
                print(f"[STEP] Merging {name} into {temp_branch}")
                git("merge", "--no-ff", "--no-edit", name)

            diffstat = diff_stat(temp_branch, source)
            namestatus = diff_name_status(temp_branch, source)
        finally:
            git("checkout", original)
            delete_branch(temp_branch)
            print(f"\n[INFO] Restored original branch: {original}")

    return diffstat, namestatus


def validate_chain(plan: Dict, *, test_cmd: str) -> None:
    """Merge changesets in order into a temp branch and run tests after each merge."""
    if not test_cmd.strip():
        raise CommandError("validate-chain requires a non-empty --test-cmd.")

    ensure_git_repo()
    ensure_clean_tree()

    base = plan["base_branch"]
    source = plan["source_branch"]
    total = len(plan["changesets"])
    chain = [branch_name_for(source, i, total) for i in range(1, total + 1)]
    ensure_branches_exist([base, source, *chain])

    temp_branch = unique_temp_branch("pcs-temp-validate")
    print(f"[INFO] Creating temporary validation branch: {temp_branch}")

    with checkout_restore() as original:
        try:
            git("checkout", "-B", temp_branch, base)
            for idx, name in enumerate(chain, start=1):
                print(f"\n[STEP] Merging {name} ({idx} of {total})")
                git("merge", "--no-ff", "--no-edit", name)
                print(f"[STEP] Running tests after changeset {idx}: {test_cmd}")
                if git("diff", "--quiet", check=False).returncode != 0:
                    raise CommandError(
                        "Working tree became dirty during validate-chain."
                    )
                result = subprocess.run(test_cmd, shell=True)
                if result.returncode != 0:
                    raise CommandError(f"Test command failed after changeset {idx}.")
        finally:
            git("checkout", original)
            delete_branch(temp_branch)
            print(f"\n[INFO] Restored original branch: {original}")

    print("[OK] validate-chain completed successfully.")
