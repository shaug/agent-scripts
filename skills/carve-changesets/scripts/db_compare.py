#!/usr/bin/env python3
"""Database/schema equivalence comparison hooks."""

from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Iterator, Optional

from command_argv import display_argv, execute_argv, validate_argv
from common import (
    CommandError,
    branch_name_for,
    checkout_restore,
    current_branch,
    delete_branch,
    ensure_branches_exist,
    ensure_clean_tree,
    ensure_git_repo,
    git,
    is_path_ignored,
    repo_root,
    unique_temp_branch,
)

DIAGNOSTIC_LIMIT = 4096


def bounded_diagnostic(value: str) -> str:
    """Return useful command output without propagating an unbounded payload."""

    detail = value.strip()
    if len(detail) <= DIAGNOSTIC_LIMIT:
        return detail
    return (
        detail[:DIAGNOSTIC_LIMIT]
        + f"\n[TRUNCATED] Diagnostic limited to {DIAGNOSTIC_LIMIT} characters."
    )


def write_restricted_text(path: Path, value: str) -> None:
    """Write one raw comparison output with owner-only permissions."""

    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            descriptor = -1
            stream.write(value)
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def resolve_keep_output_dir(destination: Path) -> Path:
    """Resolve and validate one explicit raw-output retention destination."""

    resolved = destination.expanduser().resolve()
    root = repo_root().resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError:
        return resolved

    if relative.parts and relative.parts[0] == ".carve-changesets":
        return resolved
    if is_path_ignored(relative):
        return resolved
    raise CommandError(
        "Raw comparison output inside the repository must use "
        ".carve-changesets/ or another ignored path."
    )


@contextmanager
def comparison_workspace(keep_output_dir: Optional[Path]) -> Iterator[Path]:
    """Yield a restricted persistent or automatically removed workspace."""

    if keep_output_dir is None:
        with tempfile.TemporaryDirectory(
            prefix="carve-changesets-db-compare-"
        ) as temporary:
            directory = Path(temporary).resolve()
            os.chmod(directory, 0o700)
            print("[INFO] Raw comparison outputs are ephemeral.")
            yield directory
        return

    directory = resolve_keep_output_dir(keep_output_dir)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not directory.is_dir():
        raise CommandError(f"Raw output destination is not a directory: {directory}")
    print(f"[INFO] Retaining source output: {directory / 'source.txt'}")
    print(f"[INFO] Retaining chain output: {directory / 'chain.txt'}")
    yield directory


def run_capture(argv: object, outfile: Path) -> None:
    approved_argv = validate_argv(argv, label="database command argv")
    result = execute_argv(approved_argv, text=True, capture_output=True)
    if result.returncode != 0:
        detail = bounded_diagnostic(result.stderr or result.stdout or "")
        message = f"Command failed ({result.returncode}): {display_argv(approved_argv)}"
        if detail:
            message += f"\n{detail}"
        raise CommandError(message)
    write_restricted_text(outfile, result.stdout)


def db_compare(
    plan: Dict,
    *,
    source_argv: object,
    chain_argv: object,
    keep_output_dir: Optional[Path] = None,
) -> None:
    approved_source_argv = validate_argv(
        source_argv, label="approved source schema argv"
    )
    approved_chain_argv = validate_argv(chain_argv, label="approved chain schema argv")

    ensure_git_repo()
    ensure_clean_tree()

    base = plan["base_branch"]
    source = plan["source_branch"]
    total = len(plan["changesets"])
    chain = [branch_name_for(source, i) for i in range(1, total + 1)]
    ensure_branches_exist([base, source, *chain])

    temp_branch = unique_temp_branch("carve-temp-db_compare")
    print(f"[INFO] Creating temporary branch: {temp_branch}")

    original = current_branch()
    with comparison_workspace(keep_output_dir) as output_dir:
        source_out = output_dir / "source.txt"
        chain_out = output_dir / "chain.txt"
        try:
            with checkout_restore():
                git("checkout", source)
                print(f"[STEP] Running source command on {source}")
                run_capture(approved_source_argv, source_out)

                git("checkout", "-B", temp_branch, base)
                for name in chain:
                    print(f"[STEP] Merging {name} into {temp_branch}")
                    git("merge", "--no-ff", "--no-edit", name)

                print(f"[STEP] Running chain command on {temp_branch}")
                run_capture(approved_chain_argv, chain_out)

                print("[STEP] Diffing outputs (git diff --no-index)")
                diff = git(
                    "diff",
                    "--no-index",
                    "--",
                    str(source_out),
                    str(chain_out),
                    check=False,
                )
                if diff.returncode == 0:
                    print("[OK] No differences detected.")
                elif diff.returncode == 1:
                    print(
                        bounded_diagnostic(diff.stdout)
                        or "[WARN] Differences detected."
                    )
                else:
                    detail = bounded_diagnostic(diff.stderr or diff.stdout)
                    message = f"Database output comparison failed ({diff.returncode})."
                    if detail:
                        message += f"\n{detail}"
                    raise CommandError(message)
        finally:
            if current_branch() != original:
                git("checkout", original)
            delete_branch(temp_branch)

    ensure_clean_tree()
    print("[OK] db-compare completed.")
