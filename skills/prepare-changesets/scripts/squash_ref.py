#!/usr/bin/env python3
"""Create a local squashed reference branch for comparison workflows."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Tuple

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from common import (  # noqa: E402
    CommandError,
    branch_exists,
    checkout_restore,
    delete_branch,
    ensure_clean_tree,
    ensure_git_repo,
    git,
    load_plan,
    merge_base,
    squashed_branch_name,
)


def _resolve_base_source(*, plan_path: Path, base: str, source: str) -> Tuple[str, str]:
    plan: Optional[dict] = None
    if plan_path.exists():
        plan = load_plan(plan_path)

    resolved_base = base.strip() or (
        str(plan.get("base_branch", "")).strip() if plan else ""
    )
    resolved_source = source.strip() or (
        str(plan.get("source_branch", "")).strip() if plan else ""
    )

    if not resolved_base or not resolved_source:
        raise CommandError(
            "Provide --base and --source, or ensure the plan exists with base_branch and source_branch."
        )
    return resolved_base, resolved_source


def create_squashed_ref(
    *,
    base: str,
    source: str,
    reuse_existing: bool,
    recreate: bool,
) -> str:
    ensure_git_repo()
    ensure_clean_tree()

    if not branch_exists(base):
        raise CommandError(f"Base branch does not exist: {base}")
    if not branch_exists(source):
        raise CommandError(f"Source branch does not exist: {source}")

    squashed = squashed_branch_name(source)
    exists = branch_exists(squashed)

    if exists and not (reuse_existing or recreate):
        raise CommandError(
            "\n".join(
                [
                    f"Squashed reference branch already exists: {squashed}",
                    "Ask whether to reuse it. If approved, re-run with --reuse-existing.",
                    "If it must be rebuilt, re-run with --recreate.",
                ]
            )
        )

    if exists and recreate:
        print(f"[STEP] Deleting existing squashed reference: {squashed}")
        delete_branch(squashed)

    if branch_exists(squashed) and reuse_existing:
        print(f"[OK] Reusing existing squashed reference: {squashed}")
        print("[NOTE] Keep this branch local-only. Do not push it.")
        return squashed

    mb = merge_base(base, source)
    print(f"[INFO] merge-base({base}, {source}) = {mb}")
    print(f"[STEP] Creating squashed reference branch: {squashed}")

    with checkout_restore() as original:
        try:
            git("checkout", "-B", squashed, mb)
            merge_result = git("merge", "--squash", source, check=False)
            if merge_result.returncode != 0:
                git("merge", "--abort", check=False)
                raise CommandError(
                    "Squash merge failed. Resolve source/base divergence before creating a squashed reference."
                )

            diff_cached = git("diff", "--cached", "--quiet", check=False)
            if diff_cached.returncode == 0:
                print("[WARN] No staged changes after squash merge.")
            else:
                git("commit", "-m", f"pcs: squash reference for {source}")
                print("[OK] Squashed reference commit created.")
        finally:
            git("checkout", original)

    ensure_clean_tree()
    print("[NOTE] Keep this branch local-only. Do not push it.")
    return squashed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a local squashed reference branch."
    )
    parser.add_argument(
        "--plan",
        default=str(Path(".prepare-changesets/plan.json")),
        help="Optional plan path used to resolve base/source when not provided explicitly.",
    )
    parser.add_argument("--base", default="", help="Base branch (e.g., main)")
    parser.add_argument("--source", default="", help="Source branch to squash")
    parser.add_argument(
        "--reuse-existing",
        action="store_true",
        help="Reuse an existing <source>-squashed branch if it exists.",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Delete and recreate the squashed reference branch.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        base, source = _resolve_base_source(
            plan_path=Path(args.plan),
            base=args.base,
            source=args.source,
        )
        create_squashed_ref(
            base=base,
            source=source,
            reuse_existing=bool(args.reuse_existing),
            recreate=bool(args.recreate),
        )
        return 0
    except CommandError as exc:
        print(f"[ERROR] {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
