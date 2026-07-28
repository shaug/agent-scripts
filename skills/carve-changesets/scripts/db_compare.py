#!/usr/bin/env python3
"""Database/schema equivalence comparison hooks."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from command_argv import display_argv, execute_argv, validate_argv
from common import (
    CommandError,
    branch_name_for,
    checkout_restore,
    delete_branch,
    ensure_branches_exist,
    ensure_clean_tree,
    ensure_git_repo,
    git,
    unique_temp_branch,
)


def run_capture(argv: object, outfile: Path) -> None:
    approved_argv = validate_argv(argv, label="database command argv")
    result = execute_argv(approved_argv, text=True, capture_output=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise CommandError(f"Command failed: {display_argv(approved_argv)}\n{detail}")
    outfile.write_text(result.stdout)


def db_compare(
    plan: Dict,
    *,
    source_argv: object,
    chain_argv: object,
    out_dir: Path,
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

    out_dir.mkdir(parents=True, exist_ok=True)
    source_out = out_dir / "source.txt"
    chain_out = out_dir / "chain.txt"

    temp_branch = unique_temp_branch("carve-temp-db_compare")
    print(f"[INFO] Using output directory: {out_dir}")
    print(f"[INFO] Creating temporary branch: {temp_branch}")

    with checkout_restore() as original:
        try:
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
                "diff", "--no-index", "--", str(source_out), str(chain_out), check=False
            )
            if diff.returncode == 0:
                print("[OK] No differences detected.")
            else:
                print(diff.stdout.strip() or "[WARN] Differences detected.")
        finally:
            git("checkout", original)
            delete_branch(temp_branch)

    ensure_clean_tree()
    print("[OK] db-compare completed.")
