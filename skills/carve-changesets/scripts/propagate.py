#!/usr/bin/env python3
"""Remote push safety for a materialized changeset chain.

Merge and downstream propagation belong to epic child #33. This module retains
only the #30 push-chain surface.
"""

from __future__ import annotations

from typing import Dict, List

from common import (
    CommandError,
    branch_exists,
    branch_name_for,
    ensure_clean_tree,
    ensure_git_repo,
    git,
)


def _ensure_chain_exists(source: str, total: int) -> List[str]:
    chain = [branch_name_for(source, index) for index in range(1, total + 1)]
    missing = [branch for branch in chain if not branch_exists(branch)]
    if missing:
        raise CommandError("Missing changeset branches:\n" + "\n".join(missing))
    return chain


def remote_exists(remote: str) -> bool:
    return git("remote", "get-url", remote, check=False).returncode == 0


def remote_branch_head(remote: str, branch: str) -> str | None:
    result = git(
        "ls-remote",
        "--heads",
        remote,
        f"refs/heads/{branch}",
        check=False,
    )
    if result.returncode != 0:
        raise CommandError(f"Unable to resolve {remote}/{branch} before push.")
    line = result.stdout.strip()
    return line.split()[0] if line else None


def push_changeset_branch(branch: str, *, remote: str, dry_run: bool) -> None:
    expected = remote_branch_head(remote, branch)
    lease = f"--force-with-lease=refs/heads/{branch}:{expected or ''}"
    refspec = f"refs/heads/{branch}:refs/heads/{branch}"
    command = ("git", "push", remote, refspec, lease)
    print(f"[STEP] Pushing changeset branch {branch} to {remote} with an exact lease")
    if dry_run:
        print("[DRY-RUN] Would run:")
        print(" ".join(command))
        return
    git("push", remote, refspec, lease)


def push_chain(plan: Dict, *, remote: str, dry_run: bool) -> None:
    """Push changeset branches only; never force-push the base or source."""

    ensure_git_repo()
    ensure_clean_tree()
    if not remote_exists(remote):
        raise CommandError(f"Remote does not exist: {remote}")

    base = plan["base_branch"]
    source = plan["source_branch"]
    chain = _ensure_chain_exists(source, len(plan["changesets"]))
    print(
        f"[INFO] Base branch {base} is intentionally excluded. Push or update it "
        "separately with a verified fast-forward-only workflow."
    )
    print(f"[INFO] Source branch {source} is immutable and will not be pushed.")
    for branch in chain:
        push_changeset_branch(branch, remote=remote, dry_run=dry_run)

    if dry_run:
        print("[OK] Dry-run push-chain complete. Re-run with --no-dry-run to execute.")
    else:
        print("[OK] push-chain completed.")
