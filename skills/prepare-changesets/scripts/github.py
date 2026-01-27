#!/usr/bin/env python3
"""GitHub CLI helpers for PR creation and merging."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from typing import Dict, Iterable, List

from common import (
    CommandError,
    base_for_changeset,
    branch_name_for,
    ensure_clean_tree,
    ensure_git_repo,
    run,
)


def gh_available() -> bool:
    return shutil.which("gh") is not None


def ensure_gh_ready() -> None:
    if not gh_available():
        raise CommandError("GitHub CLI ('gh') not found on PATH.")

    result = run(("gh", "auth", "status"), capture=True, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise CommandError(
            f"GitHub CLI is not authenticated. Run 'gh auth login' and retry.\n{detail}"
        )


def pr_title_for(feature_title: str, index: int, total: int) -> str:
    return f"{feature_title} ({index} of {total})"


def pr_body_for(plan: Dict, index: int, total: int, changeset: Dict) -> str:
    feature_title = plan["feature_title"].strip()
    description = str(changeset.get("description", "")).strip()
    notes = changeset.get("pr_notes", []) or []

    lines: List[str] = []
    lines.append("## Overall Feature")
    lines.append(feature_title)
    lines.append("")
    lines.append(f"## This Changeset ({index} of {total})")
    lines.append(description or "Describe the intent of this changeset.")
    lines.append("")
    lines.append("## Scaffolding, Flags, And Intentional Incompleteness")
    if notes and all(isinstance(n, str) and n.strip() for n in notes):
        for note in notes:
            lines.append(f"- {note.strip()}")
    else:
        lines.append("- None documented.")

    return "\n".join(lines).strip() + "\n"


def _print_cmd(cmd: Iterable[str]) -> None:
    printable = " ".join(subprocess.list2cmdline([part]) for part in cmd)
    print(printable)


def pr_create(plan: Dict, *, indices: List[int], dry_run: bool) -> None:
    ensure_git_repo()
    ensure_clean_tree()

    if not dry_run:
        ensure_gh_ready()

    base = plan["base_branch"]
    source = plan["source_branch"]
    changesets = plan["changesets"]
    total = len(changesets)

    for index in indices:
        if index < 1 or index > total:
            raise CommandError(f"--index must be between 1 and {total}.")

        head_branch = branch_name_for(source, index)
        base_branch = base_for_changeset(base, source, index)
        title = pr_title_for(plan["feature_title"], index, total)
        body = pr_body_for(plan, index, total, changesets[index - 1])

        cmd = (
            "gh",
            "pr",
            "create",
            "--base",
            base_branch,
            "--head",
            head_branch,
            "--title",
            title,
            "--body",
            body,
        )

        print(f"[STEP] PR for changeset {index}: {head_branch} -> {base_branch}")
        if dry_run:
            print("[DRY-RUN] Would run:")
            _print_cmd(cmd)
            continue

        result = run(cmd, capture=True, check=True)
        output = (result.stdout or "") + (result.stderr or "")
        url = ""
        for token in output.split():
            if token.startswith("http://") or token.startswith("https://"):
                url = token.strip()
                break
        if not url:
            view = run(
                (
                    "gh",
                    "pr",
                    "view",
                    "--head",
                    head_branch,
                    "--json",
                    "url",
                    "--jq",
                    ".url",
                ),
                capture=True,
                check=False,
            )
            url = (view.stdout or "").strip()
        if url:
            print(f"[OK] PR created: {url}")
        else:
            print("[OK] PR created.")

    if dry_run:
        print("[OK] Dry-run complete. Re-run with --no-dry-run to execute.")


def pr_edit_base(new_base: str, *, dry_run: bool) -> None:
    cmd = ("gh", "pr", "edit", "--base", new_base)
    print(f"[STEP] Updating PR base -> {new_base}")
    if dry_run:
        print("[DRY-RUN] Would run:")
        _print_cmd(cmd)
        return
    ensure_gh_ready()
    run(cmd, capture=True, check=True)


def pr_merge(head_branch: str, *, method: str, dry_run: bool) -> None:
    method = (method or "default").strip().lower()
    method_flags = {"merge": "--merge", "squash": "--squash", "rebase": "--rebase"}
    if method not in (*method_flags.keys(), "default"):
        raise CommandError(
            "Invalid merge method. Use 'default', 'merge', 'squash', or 'rebase'."
        )
    cmd: tuple[str, ...]
    if method == "default":
        cmd = ("gh", "pr", "merge", head_branch)
        print(f"[STEP] Merging PR for {head_branch} with method=default")
    else:
        cmd = ("gh", "pr", "merge", head_branch, method_flags[method])
        print(f"[STEP] Merging PR for {head_branch} with method={method}")
    if dry_run:
        print("[DRY-RUN] Would run:")
        _print_cmd(cmd)
        return
    ensure_gh_ready()
    run(cmd, capture=True, check=True)
    print("[OK] PR merged via gh.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="GitHub PR helpers for prepare-changesets."
    )
    parser.add_argument("--help-gh", action="store_true", help="Show gh help and exit")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.help_gh:
        ensure_gh_ready()
        run(("gh", "help"), capture=False, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
