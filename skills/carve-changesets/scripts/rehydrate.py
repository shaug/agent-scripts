"""Reconstruct changeset topology from live git refs and GitHub PR records."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from metadata import (
    ChangesetMetadata,
    MetadataError,
    parse_commit_message,
    parse_pr_metadata,
)


class RehydrationError(RuntimeError):
    """Raised when live evidence cannot identify one unambiguous chain."""


@dataclass(frozen=True)
class PullRequestRecord:
    """GitHub fields supplied by the consolidated CLI's gh chokepoint."""

    number: int
    head_branch: str
    head_sha: str
    base_branch: str
    state: str
    body: str
    title: str = ""
    merge_sha: str | None = None
    is_cross_repository: bool = False


@dataclass(frozen=True)
class ChangesetRecord:
    metadata: ChangesetMetadata
    branch: str
    head: str
    base: str
    pr_number: int | None = None
    pr_state: str | None = None


@dataclass(frozen=True)
class Chain:
    base_branch: str
    source_branch: str
    source_sha: str
    changesets: tuple[ChangesetRecord, ...]


def _git(cwd: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RehydrationError(
            "Git is required to rehydrate a changeset chain."
        ) from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RehydrationError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout


def discover_changeset_heads(
    cwd: Path,
    source_branch: str,
    remote: str,
    *,
    prefer_remote: bool = False,
) -> dict[int, tuple[str, str]]:
    """Resolve current changeset refs and reject local/remote ambiguity."""

    output = _git(
        cwd,
        "for-each-ref",
        "--format=%(refname)%00%(objectname)",
        "refs/heads",
        f"refs/remotes/{remote}",
    )
    prefix = re.escape(source_branch)
    local_pattern = re.compile(
        rf"^refs/heads/(?P<branch>{prefix}-(?P<index>[1-9][0-9]*))$"
    )
    remote_pattern = re.compile(
        rf"^refs/remotes/{re.escape(remote)}/(?P<branch>{prefix}-(?P<index>[1-9][0-9]*))$"
    )
    candidates: dict[int, dict[str, tuple[str, str]]] = {}
    for line in output.splitlines():
        ref, separator, head = line.partition("\0")
        if not separator:
            continue
        match = remote_pattern.fullmatch(ref)
        kind = "remote"
        if match is None:
            match = local_pattern.fullmatch(ref)
            kind = "local"
        if match is None:
            continue
        index = int(match.group("index"))
        candidates.setdefault(index, {})[kind] = (match.group("branch"), head)

    heads: dict[int, tuple[str, str]] = {}
    for index, variants in candidates.items():
        local = variants.get("local")
        published = variants.get("remote")
        if local and published and local[1] != published[1]:
            if prefer_remote:
                heads[index] = published
                continue
            raise RehydrationError(
                f"Changeset branch {local[0]} is ambiguous: local head {local[1]} "
                f"differs from {remote} head {published[1]}."
            )
        heads[index] = published or local  # type: ignore[assignment]
    return heads


def _pr_by_branch(
    pull_requests: Iterable[PullRequestRecord], source_branch: str
) -> dict[str, PullRequestRecord]:
    pattern = re.compile(rf"^{re.escape(source_branch)}-[1-9][0-9]*$")
    grouped: dict[str, list[PullRequestRecord]] = {}
    for pr in pull_requests:
        if pattern.fullmatch(pr.head_branch):
            grouped.setdefault(pr.head_branch, []).append(pr)
    duplicates = {branch: prs for branch, prs in grouped.items() if len(prs) > 1}
    if duplicates:
        detail = ", ".join(
            f"{branch} -> PRs {', '.join(f'#{pr.number}' for pr in prs)}"
            for branch, prs in sorted(duplicates.items())
        )
        raise RehydrationError(
            f"Multiple PRs claim the same changeset branch: {detail}."
        )
    return {branch: prs[0] for branch, prs in grouped.items()}


def rehydrate_chain(
    *,
    source_branch: str,
    pull_requests: Sequence[PullRequestRecord] = (),
    base_branch: str | None = None,
    cwd: Path | str = Path.cwd(),
    remote: str = "origin",
    prefer_remote: bool = False,
) -> Chain:
    """Reconstruct an ordered chain without consulting local plan or state files."""

    if not source_branch.strip():
        raise RehydrationError("Source branch must not be empty.")
    repo = Path(cwd)
    heads = discover_changeset_heads(
        repo, source_branch, remote, prefer_remote=prefer_remote
    )
    prs = _pr_by_branch(pull_requests, source_branch)
    pr_indices = {
        int(pr.head_branch.removeprefix(f"{source_branch}-")): pr for pr in prs.values()
    }
    found = sorted(set(heads) | set(pr_indices))
    if not found:
        raise RehydrationError(
            f"No changeset branches or PRs named {source_branch}-N were found."
        )
    expected = list(range(1, found[-1] + 1))
    if found != expected:
        missing = sorted(set(expected) - set(found))
        raise RehydrationError(
            "Changeset branch sequence has gap(s): missing index "
            + ", ".join(str(index) for index in missing)
            + "."
        )

    if base_branch is None:
        first_pr = prs.get(f"{source_branch}-1")
        if first_pr is None:
            raise RehydrationError(
                "Base branch is required when changeset 1 has no PR relationship."
            )
        base_branch = first_pr.base_branch
    if not base_branch.strip():
        raise RehydrationError("Base branch must not be empty.")

    records: list[ChangesetRecord] = []
    source_sha: str | None = None
    slugs: set[str] = set()
    prior_prs_merged = True
    for index in found:
        pr = pr_indices.get(index)
        if index in heads:
            branch, head = heads[index]
        elif pr is not None and pr.state.upper() == "MERGED":
            branch, head = pr.head_branch, pr.head_sha
            _git(repo, "cat-file", "-e", f"{head}^{{commit}}")
        else:
            raise RehydrationError(
                f"Open changeset branch {source_branch}-{index} is missing locally and on {remote}."
            )
        message = _git(repo, "show", "-s", "--format=%B", head)
        try:
            metadata = parse_commit_message(message)
        except MetadataError as exc:
            raise RehydrationError(f"Changeset branch {branch}: {exc}") from exc
        if metadata.index != index:
            raise RehydrationError(
                f"Changeset branch {branch} has Changeset-Index {metadata.index}; expected {index}."
            )
        if metadata.source_branch != source_branch:
            raise RehydrationError(
                f"Changeset branch {branch} names source {metadata.source_branch!r}; "
                f"expected {source_branch!r}."
            )
        if source_sha is None:
            source_sha = metadata.source_sha
        elif metadata.source_sha != source_sha:
            raise RehydrationError(
                f"Changeset branch {branch} names source SHA {metadata.source_sha}; "
                f"expected {source_sha}."
            )
        if metadata.slug in slugs:
            raise RehydrationError(
                f"Duplicate changeset slug {metadata.slug!r} in chain."
            )
        slugs.add(metadata.slug)

        predecessor_base = base_branch if index == 1 else f"{source_branch}-{index - 1}"
        pr = prs.get(branch)
        if pr is not None:
            if pr.is_cross_repository:
                raise RehydrationError(
                    f"PR #{pr.number} uses a fork head; changeset branches must belong "
                    "to the selected repository."
                )
            if pr.head_sha != head:
                raise RehydrationError(
                    f"PR #{pr.number} head {pr.head_sha} disagrees with branch {branch} head {head}."
                )
            allowed_bases = {predecessor_base}
            if prior_prs_merged:
                allowed_bases.add(base_branch)
            if pr.base_branch not in allowed_bases:
                raise RehydrationError(
                    f"PR #{pr.number} base {pr.base_branch!r} conflicts with allowed "
                    f"base(s) {', '.join(repr(item) for item in sorted(allowed_bases))} "
                    f"for changeset {index}."
                )
            try:
                pr_metadata = parse_pr_metadata(pr.body)
            except MetadataError as exc:
                raise RehydrationError(f"PR #{pr.number}: {exc}") from exc
            if pr_metadata != metadata:
                raise RehydrationError(
                    f"PR #{pr.number} metadata disagrees with commit trailers for {branch}."
                )
        records.append(
            ChangesetRecord(
                metadata=metadata,
                branch=branch,
                head=head,
                base=pr.base_branch if pr else predecessor_base,
                pr_number=pr.number if pr else None,
                pr_state=pr.state.upper() if pr else None,
            )
        )
        prior_prs_merged = (
            prior_prs_merged and pr is not None and pr.state.upper() == "MERGED"
        )

    assert source_sha is not None
    return Chain(
        base_branch=base_branch,
        source_branch=source_branch,
        source_sha=source_sha,
        changesets=tuple(records),
    )
