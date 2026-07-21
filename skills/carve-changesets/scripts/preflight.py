#!/usr/bin/env python3
"""Preflight checks for repo cleanliness, mergeability, and tests."""

from __future__ import annotations

import subprocess

from common import (
    CommandError,
    branch_exists,
    checkout_restore,
    compute_freshness,
    delete_branch,
    discover_test_command,
    ensure_clean_tree,
    ensure_git_repo,
    git,
    is_path_ignored,
    unique_temp_branch,
)


def check_mergeability(base: str, source: str) -> None:
    temp_branch = unique_temp_branch("pcs-temp-preflight")
    print(f"[INFO] Checking mergeability via temporary branch: {temp_branch}")

    with checkout_restore() as original:
        try:
            git("checkout", "-B", temp_branch, base)
            merge_result = git("merge", "--no-commit", "--no-ff", source, check=False)
            if merge_result.returncode != 0:
                raise CommandError(
                    "Mergeability check failed. Resolve conflicts or rebase the source branch."
                )
        finally:
            git("merge", "--abort", check=False)
            git("checkout", original)
            delete_branch(temp_branch)


def run_tests_on_branch(branch: str, test_cmd: str) -> None:
    print(f"[INFO] Running test command on {branch}: {test_cmd}")
    with checkout_restore(branch):
        result = subprocess.run(test_cmd, shell=True)
        if result.returncode != 0:
            raise CommandError("Test command failed.")
        ensure_clean_tree()


def _print_test_command_help(discovery: dict) -> None:
    reason = str(discovery.get("reason", "unknown"))
    candidates = list(discovery.get("candidates", []))
    suggestions = list(discovery.get("suggestions", []))

    if reason == "agents-missing":
        print("[WARN] No AGENTS.md found at repo root.")
    elif reason == "agents-no-test-command":
        print("[WARN] AGENTS.md found but no clear test command was detected.")
    elif reason == "agents-ambiguous":
        print("[WARN] Multiple test commands were detected in AGENTS.md:")
        for cmd in candidates:
            print(f"  - {cmd}")

    if suggestions:
        print("[HINT] Likely test commands to consider:")
        for cmd in suggestions:
            print(f"  - {cmd}")

    print("[NEXT] Ask once for the desired test command, then re-run with --test-cmd.")
    print(
        "[NEXT] If still unknown, re-run with --skip-tests and record this in the plan."
    )


def preflight(
    *,
    base: str,
    source: str,
    test_cmd: str,
    skip_tests: bool,
    skip_merge_check: bool,
    allow_source_behind_base: bool = False,
    confirm_source_behind_base: bool = False,
    allow_recordkeeping_tracked: bool = False,
) -> None:
    ensure_git_repo()
    ensure_clean_tree()

    if not branch_exists(base):
        raise CommandError(f"Base branch does not exist: {base}")
    if not branch_exists(source):
        raise CommandError(f"Source branch does not exist: {source}")

    recordkeeping_path = ".carve-changesets/"
    if not is_path_ignored(recordkeeping_path):
        message = (
            "[ERROR] .carve-changesets/ is not ignored. Add it to .gitignore or "
            ".git/info/exclude to keep plan/state files out of PRs.\n"
            "Override (not recommended): re-run with --allow-recordkeeping-tracked."
        )
        if allow_recordkeeping_tracked:
            print(
                "[WARN] .carve-changesets/ is not ignored; proceeding by explicit override."
            )
        else:
            raise CommandError(message)

    freshness = compute_freshness(base, source)
    mb = str(freshness["merge_base"])
    base_head = str(freshness["base_head"])
    print(f"[OK] merge-base({base}, {source}) = {mb}")

    if freshness["source_behind_base"]:
        message = (
            "[ERROR] Source branch is behind base branch.\n"
            f"Base:   {base} @ {base_head}\n"
            f"Source: {source} (merge-base={mb})\n\n"
            "This workflow assumes the source includes the current base HEAD to avoid churn\n"
            "while carving changesets.\n\n"
            f"Fix: merge or rebase {source} onto {base}, then re-run preflight.\n"
            "Override (not recommended): re-run with --allow-source-behind-base and record why in the plan."
        )
        if allow_source_behind_base:
            print(
                "[WARN] Source branch is behind base branch; proceeding by explicit override."
            )
        elif confirm_source_behind_base:
            response = input("Source is behind base. Proceed anyway? [y/N] ").strip()
            if response.lower() not in ("y", "yes"):
                raise CommandError(message)
            print(
                "[WARN] Source branch is behind base branch; proceeding by explicit confirmation."
            )
        else:
            raise CommandError(message)

    if not skip_merge_check:
        check_mergeability(base, source)
        print("[OK] Mergeability check passed.")
    else:
        print("[WARN] Skipping mergeability check by request.")

    effective_test_cmd = test_cmd.strip()
    if not effective_test_cmd and not skip_tests:
        discovery = discover_test_command("")
        discovered = str(discovery.get("command") or "").strip()
        if discovered:
            print(f"[HINT] Discovered test command proposal: {discovered}")
            print("[NEXT] Re-run with that exact command passed via --test-cmd.")
        else:
            _print_test_command_help(discovery)
        raise CommandError(
            "Preflight never executes discovered commands; pass an explicitly "
            "approved --test-cmd or use --skip-tests."
        )

    if effective_test_cmd and not skip_tests:
        run_tests_on_branch(source, effective_test_cmd)
        print("[OK] Test command succeeded on source branch.")
    elif effective_test_cmd and skip_tests:
        print("[WARN] Test command provided but skipped by request.")
    else:
        print("[WARN] No test command provided.")

    ensure_clean_tree()
    print("[OK] Preflight checks passed.")
