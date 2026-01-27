#!/usr/bin/env python3
"""Downstream propagation and remote push helpers."""

from __future__ import annotations

import argparse
from typing import Dict, List

from common import (
    CommandError,
    base_for_changeset,
    branch_exists,
    branch_name_for,
    checkout_restore,
    ensure_clean_tree,
    ensure_git_repo,
    git,
)
from github import ensure_gh_ready, pr_edit_base


def downstream_base_after_merge(
    base_branch: str,
    source_branch: str,
    total: int,
    merged_index: int,
    index: int,
) -> str:
    """Return the correct base for a downstream changeset after a merge."""
    if merged_index == 0:
        return (
            base_branch
            if index == 1
            else branch_name_for(source_branch, index - 1, total)
        )

    if index == merged_index + 1:
        return (
            base_branch
            if merged_index == 1
            else branch_name_for(source_branch, merged_index - 1, total)
        )

    return branch_name_for(source_branch, index - 1, total)


def _ensure_chain_exists(source: str, total: int) -> List[str]:
    chain = [branch_name_for(source, i, total) for i in range(1, total + 1)]
    missing = [b for b in chain if not branch_exists(b)]
    if missing:
        raise CommandError("Missing changeset branches:\n" + "\n".join(missing))
    return chain


def remote_exists(remote: str) -> bool:
    return git("remote", "get-url", remote, check=False).returncode == 0


def push_branch(branch: str, *, remote: str, dry_run: bool) -> None:
    cmd = ("git", "push", remote, branch, "--force-with-lease")
    print(f"[STEP] Pushing {branch} to {remote} with --force-with-lease")
    if dry_run:
        print("[DRY-RUN] Would run:")
        print(" ".join(cmd))
        return
    git("push", remote, branch, "--force-with-lease")


def push_chain(plan: Dict, *, remote: str, dry_run: bool) -> None:
    ensure_git_repo()
    ensure_clean_tree()

    base = plan["base_branch"]
    source = plan["source_branch"]
    total = len(plan["changesets"])

    if not remote_exists(remote):
        raise CommandError(f"Remote does not exist: {remote}")

    chain = _ensure_chain_exists(source, total)
    branches = [base, *chain]

    with checkout_restore() as original:
        for branch in branches:
            git("checkout", branch)
            push_branch(branch, remote=remote, dry_run=dry_run)
        print(f"\n[INFO] Restored original branch: {original}")

    if dry_run:
        print("[OK] Dry-run push-chain complete. Re-run with --no-dry-run to execute.")
    else:
        print("[OK] push-chain completed.")


def propagate_downstream(
    *,
    plan: Dict,
    merged_index: int,
    dry_run: bool,
    update_pr_bases: bool,
    skip_local_merge: bool,
    push: bool,
    remote: str,
) -> None:
    ensure_git_repo()
    ensure_clean_tree()

    base = plan["base_branch"]
    source = plan["source_branch"]
    total = len(plan["changesets"])

    if merged_index < 0 or merged_index > total:
        raise CommandError(f"--merged-index must be between 0 and {total}.")

    if push and not remote_exists(remote):
        raise CommandError(f"Remote does not exist: {remote}")

    chain = _ensure_chain_exists(source, total)

    if update_pr_bases and not dry_run:
        ensure_gh_ready()

    merged_head = (
        branch_name_for(source, merged_index, total) if merged_index >= 1 else ""
    )
    merged_base = (
        base_for_changeset(base, source, total, merged_index)
        if merged_index >= 1
        else base
    )

    print(f"[INFO] Propagating forward from merged index: {merged_index}")

    with checkout_restore() as original:
        if merged_index >= 1 and not skip_local_merge:
            print(
                f"\n[STEP] Updating local base branch {merged_base} with {merged_head}"
            )
            if dry_run:
                print("[DRY-RUN] Would run:")
                print(f"git checkout {merged_base}")
                print(
                    f"git merge --ff-only {merged_head}  # falls back to --no-ff --no-edit on failure"
                )
            else:
                git("checkout", merged_base)
                ff_only = git("merge", "--ff-only", merged_head, check=False)
                if ff_only.returncode != 0:
                    print(
                        "[WARN] --ff-only merge failed; falling back to --no-ff --no-edit."
                    )
                    git("merge", "--no-ff", "--no-edit", merged_head)
                if push:
                    push_branch(merged_base, remote=remote, dry_run=dry_run)

        start_index = 1 if merged_index == 0 else merged_index + 1
        for idx in range(start_index, total + 1):
            if idx <= merged_index:
                continue
            name = chain[idx - 1]
            new_base = downstream_base_after_merge(
                base, source, total, merged_index, idx
            )

            print(f"\n[STEP] Rebasing {name} onto {new_base}")
            if dry_run:
                print("[DRY-RUN] Would run:")
                print(f"git checkout {name}")
                print(f"git rebase {new_base}")
            else:
                git("checkout", name)
                git("rebase", new_base)

            if push:
                push_branch(name, remote=remote, dry_run=dry_run)

            if update_pr_bases:
                pr_edit_base(new_base, dry_run=dry_run)

        print(f"\n[INFO] Restored original branch: {original}")

    if dry_run:
        print("[OK] Dry-run propagation complete. Re-run with --no-dry-run to execute.")
    else:
        print("[OK] Downstream propagation completed.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Propagate downstream changesets.")
    parser.add_argument(
        "--plan", default=".prepare-changesets/plan.json", help="Plan path"
    )
    parser.add_argument(
        "--merged-index",
        type=int,
        required=True,
        help="1-based index of the merged changeset, or 0 to propagate onto base only",
    )
    parser.add_argument(
        "--update-pr-bases", dest="update_pr_bases", action="store_true"
    )
    parser.add_argument(
        "--no-update-pr-bases", dest="update_pr_bases", action="store_false"
    )
    parser.add_argument("--skip-local-merge", action="store_true")
    parser.add_argument("--push", action="store_true")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true")
    parser.add_argument("--no-dry-run", dest="dry_run", action="store_false")
    parser.set_defaults(dry_run=True, update_pr_bases=True)
    return parser


if __name__ == "__main__":
    import sys
    from pathlib import Path

    scripts_dir = Path(__file__).resolve().parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    from cli import main as cli_main

    raise SystemExit(cli_main(["propagate", *sys.argv[1:]]))
