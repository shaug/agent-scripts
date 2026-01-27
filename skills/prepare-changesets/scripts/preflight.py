#!/usr/bin/env python3
"""Preflight checks for repo cleanliness, mergeability, and tests."""

from __future__ import annotations

import argparse
import subprocess

from common import (
    CommandError,
    branch_exists,
    checkout_restore,
    delete_branch,
    discover_test_command,
    ensure_clean_tree,
    ensure_git_repo,
    git,
    merge_base,
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
            git("reset", "--hard", base)
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
    *, base: str, source: str, test_cmd: str, skip_tests: bool, skip_merge_check: bool
) -> None:
    ensure_git_repo()
    ensure_clean_tree()

    if not branch_exists(base):
        raise CommandError(f"Base branch does not exist: {base}")
    if not branch_exists(source):
        raise CommandError(f"Source branch does not exist: {source}")

    mb = merge_base(base, source)
    print(f"[OK] merge-base({base}, {source}) = {mb}")

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
            effective_test_cmd = discovered
            print(f"[INFO] Using test command from AGENTS.md: {effective_test_cmd}")
        else:
            _print_test_command_help(discovery)
            raise CommandError("Test command is required unless --skip-tests is set.")

    if effective_test_cmd and not skip_tests:
        run_tests_on_branch(source, effective_test_cmd)
        print("[OK] Test command succeeded on source branch.")
    elif effective_test_cmd and skip_tests:
        print("[WARN] Test command provided but skipped by request.")
    else:
        print("[WARN] No test command provided.")

    ensure_clean_tree()
    print("[OK] Preflight checks passed.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Preflight checks for prepare-changesets."
    )
    parser.add_argument("--base", required=True, help="Base branch (e.g., main)")
    parser.add_argument("--source", required=True, help="Source branch to decompose")
    parser.add_argument(
        "--test-cmd",
        default="",
        help="Optional test/build command to run on the source branch",
    )
    parser.add_argument(
        "--skip-tests", action="store_true", help="Skip running the test command"
    )
    parser.add_argument(
        "--skip-merge-check", action="store_true", help="Skip mergeability simulation"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        preflight(
            base=args.base,
            source=args.source,
            test_cmd=args.test_cmd,
            skip_tests=args.skip_tests,
            skip_merge_check=args.skip_merge_check,
        )
        return 0
    except CommandError as exc:
        print(f"[ERROR] {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
