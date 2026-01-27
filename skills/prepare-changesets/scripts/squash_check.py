#!/usr/bin/env python3
"""Compare the changeset chain against a local squashed reference via rebase."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Tuple

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from common import (  # noqa: E402
    CommandError,
    branch_exists,
    branch_name_for,
    checkout_restore,
    delete_branch,
    diff_name_status,
    diff_stat,
    ensure_branches_exist,
    ensure_clean_tree,
    ensure_git_repo,
    git,
    load_plan,
    squashed_branch_name,
    unique_temp_branch,
    validate_plan,
)


def _load_valid_plan(plan_path: Path) -> Dict:
    plan = load_plan(plan_path)
    valid, errors = validate_plan(plan)
    if not valid:
        detail = "; ".join(errors) or "unknown validation error"
        raise CommandError(f"Plan validation failed: {detail}")
    return plan


def _chain_for_plan(plan: Dict) -> List[str]:
    source = plan["source_branch"]
    total = len(plan["changesets"])
    if total < 1:
        raise CommandError("Plan must include at least one changeset.")
    return [branch_name_for(source, i) for i in range(1, total + 1)]


def squash_check(plan: Dict) -> Tuple[str, str]:
    ensure_git_repo()
    ensure_clean_tree()

    base = plan["base_branch"]
    source = plan["source_branch"]
    chain = _chain_for_plan(plan)
    tip = chain[-1]
    squashed = squashed_branch_name(source)

    if not branch_exists(squashed):
        raise CommandError(
            "\n".join(
                [
                    f"Squashed reference branch not found: {squashed}",
                    "Create it with squash_ref.py before running squash_check.",
                ]
            )
        )

    ensure_branches_exist([base, source, squashed, *chain])

    temp_branch = unique_temp_branch("pcs-temp-squash-check")
    print(f"[INFO] Using squashed reference: {squashed}")
    print(f"[INFO] Chain tip: {tip}")
    print(f"[INFO] Creating temporary squash-check branch: {temp_branch}")

    with checkout_restore() as original:
        try:
            git("checkout", "-B", temp_branch, squashed)
            rebase_result = git("rebase", "--empty=drop", tip, check=False)
            if rebase_result.returncode != 0:
                git("rebase", "--abort", check=False)
                raise CommandError(
                    "Squash-check rebase encountered conflicts. The chain may not capture the source branch cleanly."
                )

            diffstat = diff_stat(tip, temp_branch)
            namestatus = diff_name_status(tip, temp_branch)
        finally:
            git("checkout", original)
            delete_branch(temp_branch)
            print(f"\n[INFO] Restored original branch: {original}")

    ensure_clean_tree()
    return diffstat, namestatus


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Rebase a local squashed reference onto the chain tip and diff the result."
    )
    parser.add_argument(
        "--plan",
        default=str(Path(".prepare-changesets/plan.json")),
        help="Plan path",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        plan = _load_valid_plan(Path(args.plan))
        diffstat, namestatus = squash_check(plan)

        print("\n[INFO] Diffstat vs chain tip after squash-check rebase:")
        if diffstat:
            print(diffstat)
        else:
            print("[OK] No diffstat differences detected.")

        print("\n[INFO] Name-status vs chain tip after squash-check rebase:")
        if namestatus:
            print(namestatus)
        else:
            print("[OK] No name-status differences detected.")

        print("[OK] squash-check completed.")
        return 0
    except CommandError as exc:
        print(f"[ERROR] {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
