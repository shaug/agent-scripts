#!/usr/bin/env python3
"""Single structured chokepoint for every carve-changesets ``gh`` call."""

from __future__ import annotations

import json
import subprocess
from typing import Dict, Iterable, List, Sequence

from common import (
    CommandError,
    base_for_changeset,
    branch_name_for,
    ensure_clean_tree,
    ensure_git_repo,
    git,
    message_file,
)
from metadata import embed_pr_metadata, parse_commit_message
from rehydrate import PullRequestRecord


def _format_error(command: Sequence[str], error: subprocess.CalledProcessError) -> str:
    stdout = (error.stdout or "").strip()
    stderr = (error.stderr or "").strip()
    details = [f"GitHub CLI command failed: {' '.join(command)}"]
    if stdout:
        details.append(f"stdout: {stdout}")
    if stderr:
        details.append(f"stderr: {stderr}")
    return "\n".join(details)


def gh_capture(
    args: Sequence[str], *, allowed_returncodes: Iterable[int] = ()
) -> tuple[str, str]:
    """Run ``gh`` with list argv and return captured stdout and stderr."""

    command = ["gh", *args]
    try:
        result = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise CommandError("GitHub CLI ('gh') not found on PATH.") from exc
    except subprocess.CalledProcessError as exc:
        if exc.returncode in set(allowed_returncodes):
            return exc.stdout or "", exc.stderr or ""
        raise CommandError(_format_error(command, exc)) from exc
    return result.stdout, result.stderr or ""


def gh_json(args: Sequence[str], *, allowed_returncodes: Iterable[int] = ()) -> object:
    """Run ``gh`` and decode one JSON response."""

    stdout, _ = gh_capture(args, allowed_returncodes=allowed_returncodes)
    if not stdout.strip():
        return None
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise CommandError(
            f"Failed to parse JSON from GitHub CLI command: {' '.join(args)}"
        ) from exc


def ensure_gh_ready() -> None:
    gh_capture(("auth", "status"))


def pr_title_for(feature_title: str, index: int, total: int) -> str:
    return f"{feature_title} ({index} of {total})"


def pr_body_for(plan: Dict, index: int, total: int, changeset: Dict) -> str:
    notes = changeset.get("pr_notes", []) or []
    lines = [
        "## Overall Feature",
        plan["feature_title"].strip(),
        "",
        f"## This Changeset ({index} of {total})",
        str(changeset.get("description", "")).strip()
        or "Describe the intent of this changeset.",
        "",
        "## Scaffolding, Flags, And Intentional Incompleteness",
    ]
    if notes and all(isinstance(note, str) and note.strip() for note in notes):
        lines.extend(f"- {note.strip()}" for note in notes)
    else:
        lines.append("- None documented.")
    branch = branch_name_for(plan["source_branch"], index)
    message = git("show", "-s", "--format=%B", branch).stdout
    return embed_pr_metadata(
        "\n".join(lines).strip() + "\n", parse_commit_message(message)
    )


def _print_command(command: Sequence[str]) -> None:
    print(" ".join(subprocess.list2cmdline([part]) for part in command))


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
        head = branch_name_for(source, index)
        pr_base = base_for_changeset(base, source, index)
        title = pr_title_for(plan["feature_title"], index, total)
        body = pr_body_for(plan, index, total, changesets[index - 1])
        with message_file(body) as body_path:
            args = (
                "pr",
                "create",
                "--base",
                pr_base,
                "--head",
                head,
                "--title",
                title,
                "--body-file",
                body_path,
            )
            print(f"[STEP] PR for changeset {index}: {head} -> {pr_base}")
            if dry_run:
                print("[DRY-RUN] Would run:")
                _print_command(("gh", *args))
                continue
            gh_capture(args)
        created = gh_json(("pr", "view", head, "--json", "number,url"))
        if not isinstance(created, dict):
            raise CommandError(f"PR for {head} was created but could not be verified.")
        print(f"[OK] PR #{created['number']} created: {created['url']}")

    if dry_run:
        print("[OK] Dry-run complete. Re-run with --no-dry-run to execute.")


def pull_requests_for_source(source_branch: str) -> list[PullRequestRecord]:
    """Return complete GitHub PR evidence needed by live rehydration."""

    payload = gh_json(
        (
            "pr",
            "list",
            "--state",
            "all",
            "--limit",
            "100",
            "--json",
            "number,headRefName,headRefOid,baseRefName,state,body",
        )
    )
    if not isinstance(payload, list):
        raise CommandError("Unexpected GitHub PR list response.")
    prefix = f"{source_branch}-"
    records: list[PullRequestRecord] = []
    for item in payload:
        if not isinstance(item, dict):
            raise CommandError("Unexpected GitHub PR record.")
        head = str(item.get("headRefName") or "")
        suffix = head.removeprefix(prefix)
        if not head.startswith(prefix) or not suffix.isdigit() or int(suffix) < 1:
            continue
        records.append(
            PullRequestRecord(
                number=int(item["number"]),
                head_branch=head,
                head_sha=str(item.get("headRefOid") or ""),
                base_branch=str(item.get("baseRefName") or ""),
                state=str(item.get("state") or ""),
                body=str(item.get("body") or ""),
            )
        )
    return records
