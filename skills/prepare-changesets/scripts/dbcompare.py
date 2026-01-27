#!/usr/bin/env python3
"""Database/schema equivalence comparison hooks."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import Dict

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


def run_capture(command: str, outfile: Path) -> None:
    result = subprocess.run(command, shell=True, text=True, capture_output=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise CommandError(f"Command failed: {command}\n{detail}")
    outfile.write_text(result.stdout)


def db_compare(plan: Dict, *, source_cmd: str, chain_cmd: str, out_dir: Path) -> None:
    if not source_cmd.strip() or not chain_cmd.strip():
        raise CommandError("db-compare requires both --source-cmd and --chain-cmd.")

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

    temp_branch = unique_temp_branch("pcs-temp-dbcompare")
    print(f"[INFO] Using output directory: {out_dir}")
    print(f"[INFO] Creating temporary branch: {temp_branch}")

    with checkout_restore() as original:
        try:
            git("checkout", source)
            print(f"[STEP] Running source command on {source}")
            run_capture(source_cmd, source_out)

            git("checkout", "-B", temp_branch, base)
            for name in chain:
                print(f"[STEP] Merging {name} into {temp_branch}")
                git("merge", "--no-ff", "--no-edit", name)

            print(f"[STEP] Running chain command on {temp_branch}")
            run_capture(chain_cmd, chain_out)

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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DB/schema compare helper.")
    parser.add_argument("--plan", default=str(Path(".prepare-changesets/plan.json")))
    parser.add_argument("--source-cmd", required=True)
    parser.add_argument("--chain-cmd", required=True)
    parser.add_argument(
        "--out-dir", default=str(Path(".prepare-changesets/db-compare"))
    )
    return parser
