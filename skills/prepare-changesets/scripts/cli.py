#!/usr/bin/env python3
"""CLI wiring for prepare-changesets helpers."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from chain import compare_chain, create_chain, validate_chain
from common import (
    DEFAULT_PLAN_PATH,
    CommandError,
    branch_exists,
    branch_name_for,
    discover_test_command,
    ensure_clean_tree,
    ensure_git_repo,
    init_plan,
    load_plan,
    validate_plan,
)
from dbcompare import db_compare
from github import pr_create, pr_merge
from patch_apply import build_diff
from plan_checks import strict_apply_check, validate_plan_strict
from preflight import preflight
from propagate import propagate_downstream, push_chain


def load_and_validate(plan_path: Path) -> Dict:
    plan = load_plan(plan_path)
    valid, errors = validate_plan(plan)
    if not valid:
        for err in errors:
            print(f"[ERROR] {err}")
        raise CommandError("Plan validation failed.")
    return plan


def cmd_preflight(args: argparse.Namespace) -> None:
    preflight(
        base=args.base,
        source=args.source,
        test_cmd=args.test_cmd,
        skip_tests=args.skip_tests,
        skip_merge_check=args.skip_merge_check,
        allow_source_behind_base=args.allow_source_behind_base,
        confirm_source_behind_base=args.confirm_source_behind_base,
    )


def cmd_init_plan(args: argparse.Namespace) -> None:
    plan_path = Path(args.plan)
    test_cmd = str(args.test_cmd or "").strip()
    if not test_cmd:
        discovery = discover_test_command("")
        discovered = str(discovery.get("command") or "").strip()
        if discovered:
            test_cmd = discovered
            print(f"[INFO] Using test command from AGENTS.md: {test_cmd}")
        else:
            reason = str(discovery.get("reason", "unknown"))
            if reason == "agents-missing":
                print("[WARN] No AGENTS.md found at repo root.")
            elif reason == "agents-no-test-command":
                print("[WARN] AGENTS.md found but no clear test command was detected.")
            elif reason == "agents-ambiguous":
                candidates = list(discovery.get("candidates", []))
                if candidates:
                    print("[WARN] Multiple test commands were detected in AGENTS.md:")
                    for cmd in candidates:
                        print(f"  - {cmd}")

            suggestions = list(discovery.get("suggestions", []))
            if suggestions:
                print("[HINT] Likely test commands to consider:")
                for cmd in suggestions:
                    print(f"  - {cmd}")
            print("[NEXT] Ask once for the desired test command and update the plan.")

    init_plan(
        plan_path=plan_path,
        base=args.base,
        source=args.source,
        title=args.title,
        changesets=args.changesets,
        test_cmd=test_cmd,
        force=args.force,
    )
    print(f"[OK] Wrote plan template: {plan_path}")
    print(
        "[NEXT] Edit the plan to reflect your Phase 1 decomposition before creating branches."
    )


def cmd_validate(args: argparse.Namespace) -> None:
    plan = load_plan(Path(args.plan))
    valid, errors = validate_plan(plan)
    if not valid:
        print("[ERROR] Plan validation failed:")
        for err in errors:
            print(f"  - {err}")
        raise CommandError("Plan is invalid.")
    if args.strict:
        strict_ok, strict_errors, strict_warnings = validate_plan_strict(plan)
        if strict_warnings:
            print("[WARN] Strict validation warnings:")
            for warn in strict_warnings:
                print(f"  - {warn}")
        if not strict_ok:
            print("[ERROR] Strict validation failed:")
            for err in strict_errors:
                print(f"  - {err}")
            raise CommandError("Plan is invalid under --strict.")
        ensure_git_repo()
        ensure_clean_tree()
        strict_apply_check(plan)
        print("[OK] Strict validation passed.")
        return
    print("[OK] Plan validation passed.")


def cmd_hunk_preview(args: argparse.Namespace) -> None:
    plan_path = Path(args.plan)
    base = args.base
    source = args.source
    if plan_path.exists() and (not base or not source):
        plan = load_plan(plan_path)
        base = base or plan.get("base_branch", "")
        source = source or plan.get("source_branch", "")
    if not base or not source:
        raise CommandError("hunk-preview requires --base and --source or a plan file.")

    diff_files = build_diff(base, source)
    target = args.file
    matched = [df for df in diff_files if target in (df.new_path, df.old_path)]
    if not matched:
        raise CommandError(f"No diff hunks found for file: {target}")

    contains = args.contains or []
    excludes = args.excludes or []

    for df in matched:
        if df.old_path and df.new_path and df.old_path != df.new_path:
            label = f"{df.old_path} -> {df.new_path}"
        else:
            label = df.new_path or df.old_path or "<unknown>"
        print(f"[FILE] {label}")
        if df.is_binary:
            print("  [BIN] Binary file; no textual hunks available.")
            continue
        if not df.hunks:
            print("  [INFO] No hunks in diff.")
            continue
        for idx, hunk in enumerate(df.hunks, start=1):
            body = hunk.body_text
            if contains and not all(c in body for c in contains):
                continue
            if excludes and any(c in body for c in excludes):
                continue
            print(f"\n  [HUNK {idx}] {hunk.header}")
            for line in hunk.lines[1:]:
                print(f"  {line}")


def cmd_run(args: argparse.Namespace) -> None:
    plan_path = Path(args.plan)
    plan_exists = plan_path.exists()

    preflight(
        base=args.base,
        source=args.source,
        test_cmd=args.test_cmd,
        skip_tests=args.skip_tests,
        skip_merge_check=args.skip_merge_check,
        allow_source_behind_base=args.allow_source_behind_base,
        confirm_source_behind_base=args.confirm_source_behind_base,
    )

    if not plan_exists or args.force_init:
        init_plan(
            plan_path=plan_path,
            base=args.base,
            source=args.source,
            title=args.title,
            changesets=args.changesets,
            test_cmd=str(args.test_cmd or "").strip(),
            force=args.force_init,
        )
        print(f"[OK] Wrote plan template: {plan_path}")
        print("[NEXT] Edit the plan to define changesets and selectors.")
    else:
        print(f"[INFO] Plan already exists: {plan_path}")

    if args.create_chain:
        plan = load_and_validate(plan_path)
        create_chain(plan)
        print("[NEXT] Review each changeset branch before creating PRs.")
    else:
        print("[NEXT] Run 'create-chain' after updating the plan.")


def cmd_status(args: argparse.Namespace) -> None:
    plan_path = Path(args.plan)
    plan = load_plan(plan_path)
    valid, errors = validate_plan(plan)
    if not valid:
        print("[WARN] Plan is invalid; status may be misleading.")
        for err in errors:
            print(f"  - {err}")

    base = plan["base_branch"]
    source = plan["source_branch"]
    total = len(plan.get("changesets", []))

    print(f"Plan: {plan_path}")
    print(f"Base: {base}")
    print(f"Source: {source}")
    print(f"Changesets: {total}")

    for i in range(1, total + 1):
        name = branch_name_for(source, i)
        exists = branch_exists(name)
        marker = "[OK]" if exists else "[  ]"
        print(f"{marker} {name}")


def cmd_create_chain(args: argparse.Namespace) -> None:
    plan = load_and_validate(Path(args.plan))
    create_chain(plan)
    print("[NEXT] Review each branch and refine commits as needed before opening PRs.")


def cmd_compare(args: argparse.Namespace) -> None:
    plan = load_and_validate(Path(args.plan))
    diffstat, namestatus = compare_chain(plan)

    print("\n[INFO] Diffstat vs source branch:")
    if diffstat:
        print(diffstat)
    else:
        print("[OK] No diffstat differences detected.")

    print("\n[INFO] Name-status vs source branch:")
    if namestatus:
        print(namestatus)
    else:
        print("[OK] No name-status differences detected.")

    print("[OK] Comparison completed. Investigate any reported differences.")


def cmd_validate_chain(args: argparse.Namespace) -> None:
    plan = load_and_validate(Path(args.plan))
    test_cmd = args.test_cmd or str(plan.get("test_command", "")).strip()
    validate_chain(plan, test_cmd=test_cmd)


def cmd_pr_create(args: argparse.Namespace) -> None:
    plan = load_and_validate(Path(args.plan))
    total = len(plan["changesets"])

    indices: List[int]
    if args.index is None:
        indices = list(range(1, total + 1))
    else:
        indices = [args.index]

    pr_create(plan, indices=indices, dry_run=args.dry_run)


def cmd_propagate(args: argparse.Namespace) -> None:
    plan = load_and_validate(Path(args.plan))
    propagate_downstream(
        plan=plan,
        merged_index=args.merged_index,
        dry_run=args.dry_run,
        update_pr_bases=args.update_pr_bases,
        skip_local_merge=args.skip_local_merge,
        push=args.push,
        remote=args.remote,
    )


def cmd_merge_propagate(args: argparse.Namespace) -> None:
    plan = load_and_validate(Path(args.plan))
    source = plan["source_branch"]
    total = len(plan["changesets"])
    index = args.index

    if index < 1 or index > total:
        raise CommandError(f"--index must be between 1 and {total}.")

    head_branch = branch_name_for(source, index)
    pr_merge(head_branch, method=args.method, dry_run=args.dry_run)

    propagate_downstream(
        plan=plan,
        merged_index=index,
        dry_run=args.dry_run,
        update_pr_bases=args.update_pr_bases,
        skip_local_merge=args.skip_local_merge,
        push=args.push,
        remote=args.remote,
    )


def cmd_push_chain(args: argparse.Namespace) -> None:
    plan = load_and_validate(Path(args.plan))
    push_chain(plan, remote=args.remote, dry_run=args.dry_run)


def cmd_db_compare(args: argparse.Namespace) -> None:
    plan = load_and_validate(Path(args.plan))
    out_dir = Path(args.out_dir)
    db_compare(
        plan, source_cmd=args.source_cmd, chain_cmd=args.chain_cmd, out_dir=out_dir
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Deterministic helpers for the prepare-changesets workflow."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_preflight = sub.add_parser(
        "preflight", help="Validate repo state, mergeability, and optional tests."
    )
    p_preflight.add_argument("--base", required=True, help="Base branch (e.g., main)")
    p_preflight.add_argument(
        "--source", required=True, help="Source branch to decompose"
    )
    p_preflight.add_argument(
        "--test-cmd",
        default="",
        help="Optional test/build command to run on the source branch",
    )
    p_preflight.add_argument(
        "--skip-tests", action="store_true", help="Skip running the test command"
    )
    p_preflight.add_argument(
        "--skip-merge-check", action="store_true", help="Skip mergeability simulation"
    )
    p_preflight.add_argument(
        "--allow-source-behind-base",
        action="store_true",
        help="Allow preflight to continue when source is behind base.",
    )
    p_preflight.add_argument(
        "--confirm-source-behind-base",
        action="store_true",
        help="Prompt for confirmation when source is behind base.",
    )
    p_preflight.set_defaults(func=cmd_preflight)

    p_init = sub.add_parser("init-plan", help="Create a plan template JSON file.")
    p_init.add_argument(
        "--plan",
        default=str(DEFAULT_PLAN_PATH),
        help="Plan path (default: .prepare-changesets/plan.json)",
    )
    p_init.add_argument("--base", required=True, help="Base branch")
    p_init.add_argument("--source", required=True, help="Source branch")
    p_init.add_argument("--title", required=True, help="Shared PR title base")
    p_init.add_argument(
        "--changesets", type=int, default=3, help="Number of placeholder changesets"
    )
    p_init.add_argument(
        "--test-cmd",
        default="",
        help="Optional test/build command to store in the plan",
    )
    p_init.add_argument("--force", action="store_true", help="Overwrite existing plan")
    p_init.set_defaults(func=cmd_init_plan)

    p_validate = sub.add_parser("validate", help="Validate a plan file.")
    p_validate.add_argument("--plan", default=str(DEFAULT_PLAN_PATH), help="Plan path")
    p_validate.add_argument(
        "--strict",
        action="store_true",
        help="Run strict validation (hunk matching, patch checks, placeholders).",
    )
    p_validate.set_defaults(func=cmd_validate)

    p_status = sub.add_parser("status", help="Show plan and branch-chain status.")
    p_status.add_argument("--plan", default=str(DEFAULT_PLAN_PATH), help="Plan path")
    p_status.set_defaults(func=cmd_status)

    p_create = sub.add_parser(
        "create-chain", help="Create the ordered changeset branch chain."
    )
    p_create.add_argument("--plan", default=str(DEFAULT_PLAN_PATH), help="Plan path")
    p_create.set_defaults(func=cmd_create_chain)

    p_compare = sub.add_parser(
        "compare", help="Merge the chain into a temp branch and diff vs source."
    )
    p_compare.add_argument("--plan", default=str(DEFAULT_PLAN_PATH), help="Plan path")
    p_compare.set_defaults(func=cmd_compare)

    p_validate_chain = sub.add_parser(
        "validate-chain",
        help="Merge changesets in order into a temp branch and run tests after each merge.",
    )
    p_validate_chain.add_argument(
        "--plan", default=str(DEFAULT_PLAN_PATH), help="Plan path"
    )
    p_validate_chain.add_argument(
        "--test-cmd",
        default="",
        help="Test command to run after each merge (defaults to plan.test_command)",
    )
    p_validate_chain.set_defaults(func=cmd_validate_chain)

    p_pr = sub.add_parser(
        "pr-create", help="Create stacked PRs with gh based on the plan."
    )
    p_pr.add_argument("--plan", default=str(DEFAULT_PLAN_PATH), help="Plan path")
    p_pr.add_argument(
        "--index",
        type=int,
        help="Create a PR for a single 1-based changeset index (default: all)",
    )
    p_pr.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Print gh commands without executing them (default).",
    )
    p_pr.add_argument(
        "--no-dry-run",
        dest="dry_run",
        action="store_false",
        help="Execute gh commands.",
    )
    p_pr.set_defaults(func=cmd_pr_create, dry_run=True)

    p_merge = sub.add_parser(
        "merge-propagate",
        help="Merge a reviewed changeset PR via gh, then propagate and update downstream PR bases.",
    )
    p_merge.add_argument("--plan", default=str(DEFAULT_PLAN_PATH), help="Plan path")
    p_merge.add_argument(
        "--index", type=int, required=True, help="1-based changeset index to merge"
    )
    p_merge.add_argument(
        "--method",
        choices=("merge", "squash", "rebase"),
        default="merge",
        help="gh pr merge strategy (default: merge)",
    )
    p_merge.add_argument(
        "--update-pr-bases",
        dest="update_pr_bases",
        action="store_true",
        help="Update downstream PR bases with gh (default).",
    )
    p_merge.add_argument(
        "--no-update-pr-bases",
        dest="update_pr_bases",
        action="store_false",
        help="Skip gh PR base updates.",
    )
    p_merge.add_argument(
        "--skip-local-merge",
        action="store_true",
        help="Skip local base-branch merge simulation.",
    )
    p_merge.add_argument(
        "--push",
        action="store_true",
        help="Push updated branches to the remote with --force-with-lease.",
    )
    p_merge.add_argument(
        "--remote", default="origin", help="Remote name for --push (default: origin)"
    )
    p_merge.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Print gh/git commands without executing them (default).",
    )
    p_merge.add_argument(
        "--no-dry-run",
        dest="dry_run",
        action="store_false",
        help="Execute gh/git commands.",
    )
    p_merge.set_defaults(func=cmd_merge_propagate, dry_run=True, update_pr_bases=True)

    p_propagate = sub.add_parser(
        "propagate", help="Rebase downstream changesets after a merge."
    )
    p_propagate.add_argument("--plan", default=str(DEFAULT_PLAN_PATH), help="Plan path")
    p_propagate.add_argument(
        "--merged-index",
        type=int,
        required=True,
        help="1-based index of the merged changeset, or 0 to propagate onto base only",
    )
    p_propagate.add_argument(
        "--update-pr-bases",
        dest="update_pr_bases",
        action="store_true",
        help="Update downstream PR bases with gh (default).",
    )
    p_propagate.add_argument(
        "--no-update-pr-bases",
        dest="update_pr_bases",
        action="store_false",
        help="Skip gh PR base updates.",
    )
    p_propagate.add_argument(
        "--skip-local-merge",
        action="store_true",
        help="Skip local base-branch merge simulation.",
    )
    p_propagate.add_argument(
        "--push",
        action="store_true",
        help="Push updated branches to the remote with --force-with-lease.",
    )
    p_propagate.add_argument(
        "--remote", default="origin", help="Remote name for --push (default: origin)"
    )
    p_propagate.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Print gh/git commands without executing them (default).",
    )
    p_propagate.add_argument(
        "--no-dry-run",
        dest="dry_run",
        action="store_false",
        help="Execute gh/git commands.",
    )
    p_propagate.set_defaults(func=cmd_propagate, dry_run=True, update_pr_bases=True)

    p_push = sub.add_parser(
        "push-chain",
        help="Push base and changeset branches to a remote with --force-with-lease.",
    )
    p_push.add_argument("--plan", default=str(DEFAULT_PLAN_PATH), help="Plan path")
    p_push.add_argument(
        "--remote", default="origin", help="Remote name (default: origin)"
    )
    p_push.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Print git commands without executing them (default).",
    )
    p_push.add_argument(
        "--no-dry-run",
        dest="dry_run",
        action="store_false",
        help="Execute git commands.",
    )
    p_push.set_defaults(func=cmd_push_chain, dry_run=True)

    p_db = sub.add_parser(
        "db-compare",
        help="Run source and chain schema commands and diff their outputs.",
    )
    p_db.add_argument("--plan", default=str(DEFAULT_PLAN_PATH), help="Plan path")
    p_db.add_argument(
        "--source-cmd",
        required=True,
        help="Command to run on the source branch (stdout is captured)",
    )
    p_db.add_argument(
        "--chain-cmd",
        required=True,
        help="Command to run on the merged chain branch (stdout is captured)",
    )
    p_db.add_argument(
        "--out-dir",
        default=str(DEFAULT_PLAN_PATH.parent / "db-compare"),
        help="Directory for captured outputs (default: .prepare-changesets/db-compare)",
    )
    p_db.set_defaults(func=cmd_db_compare)

    p_hunk = sub.add_parser(
        "hunk-preview",
        help="List candidate hunks for a file from base..source diff.",
    )
    p_hunk.add_argument("--plan", default=str(DEFAULT_PLAN_PATH), help="Plan path")
    p_hunk.add_argument("--base", default="", help="Base branch (optional)")
    p_hunk.add_argument("--source", default="", help="Source branch (optional)")
    p_hunk.add_argument("--file", required=True, help="Repo-relative file path")
    p_hunk.add_argument(
        "--contains",
        action="append",
        default=[],
        help="Only show hunks containing this string (repeatable)",
    )
    p_hunk.add_argument(
        "--excludes",
        action="append",
        default=[],
        help="Hide hunks containing this string (repeatable)",
    )
    p_hunk.set_defaults(func=cmd_hunk_preview)

    p_run = sub.add_parser(
        "run",
        help="Guided runner: preflight, create a plan if missing, optionally create chain.",
    )
    p_run.add_argument("--plan", default=str(DEFAULT_PLAN_PATH), help="Plan path")
    p_run.add_argument("--base", required=True, help="Base branch")
    p_run.add_argument("--source", required=True, help="Source branch")
    p_run.add_argument("--title", required=True, help="Shared PR title base")
    p_run.add_argument(
        "--changesets", type=int, default=3, help="Number of placeholder changesets"
    )
    p_run.add_argument(
        "--test-cmd",
        default="",
        help="Optional test/build command to run and store in the plan",
    )
    p_run.add_argument(
        "--skip-tests", action="store_true", help="Skip running the test command"
    )
    p_run.add_argument(
        "--skip-merge-check", action="store_true", help="Skip mergeability simulation"
    )
    p_run.add_argument(
        "--allow-source-behind-base",
        action="store_true",
        help="Allow preflight to continue when source is behind base.",
    )
    p_run.add_argument(
        "--confirm-source-behind-base",
        action="store_true",
        help="Prompt for confirmation when source is behind base.",
    )
    p_run.add_argument(
        "--create-chain",
        action="store_true",
        help="Create changeset branches after writing/validating the plan",
    )
    p_run.add_argument(
        "--force-init",
        action="store_true",
        help="Overwrite an existing plan file when running init",
    )
    p_run.set_defaults(func=cmd_run)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        args.func(args)
        ensure_clean_tree()
        return 0
    except CommandError as exc:
        print(f"[ERROR] {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
