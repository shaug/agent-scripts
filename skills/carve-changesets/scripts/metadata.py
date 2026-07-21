"""Durable identity carried by changeset commits and pull requests."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from typing import Callable, Sequence

TRAILER_SLUG = "Changeset-Slug"
TRAILER_INDEX = "Changeset-Index"
TRAILER_SOURCE = "Changeset-Source"
METADATA_MARKER = "carve-changesets:metadata:v1"

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_BLOCK_RE = re.compile(
    rf"<!--\s*{re.escape(METADATA_MARKER)}\s*\n(?P<payload>.*?)\n\s*-->",
    re.DOTALL,
)


class MetadataError(ValueError):
    """Raised when durable changeset identity is absent or contradictory."""


GitRunner = Callable[[Sequence[str], str], str]


@dataclass(frozen=True)
class ChangesetMetadata:
    """Identity shared by a changeset commit and its pull request."""

    slug: str
    index: int
    source_branch: str
    source_sha: str

    def __post_init__(self) -> None:
        if not self.slug.strip():
            raise MetadataError("Changeset slug must not be empty.")
        if self.index < 1:
            raise MetadataError("Changeset index must be a positive integer.")
        if not self.source_branch.strip():
            raise MetadataError("Changeset source branch must not be empty.")
        if " @ " in self.source_branch:
            raise MetadataError("Changeset source branch must not contain ' @ '.")
        if not _SHA_RE.fullmatch(self.source_sha):
            raise MetadataError(
                "Changeset source SHA must be a full lowercase 40-character SHA."
            )

    @property
    def source_trailer(self) -> str:
        return f"{self.source_branch} @ {self.source_sha}"


def _run_git_interpret_trailers(args: Sequence[str], input_text: str) -> str:
    try:
        result = subprocess.run(
            ["git", "interpret-trailers", *args],
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise MetadataError("Git is required to manage changeset trailers.") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise MetadataError(f"git interpret-trailers failed: {detail}")
    return result.stdout


def stamp_commit_message(
    message: str,
    metadata: ChangesetMetadata,
    *,
    runner: GitRunner = _run_git_interpret_trailers,
) -> str:
    """Return a commit message stamped by ``git interpret-trailers``."""

    if not message.strip():
        raise MetadataError("Commit message must not be empty.")
    return runner(
        (
            "--trailer",
            f"{TRAILER_SLUG}: {metadata.slug}",
            "--trailer",
            f"{TRAILER_INDEX}: {metadata.index}",
            "--trailer",
            f"{TRAILER_SOURCE}: {metadata.source_trailer}",
        ),
        message.rstrip() + "\n",
    )


def parse_commit_message(
    message: str,
    *,
    runner: GitRunner = _run_git_interpret_trailers,
) -> ChangesetMetadata:
    """Parse required identity trailers from a changeset commit message."""

    parsed = runner(("--parse",), message)
    values: dict[str, list[str]] = {}
    for line in parsed.splitlines():
        key, separator, value = line.partition(":")
        if separator:
            values.setdefault(key.strip(), []).append(value.strip())

    required = (TRAILER_SLUG, TRAILER_INDEX, TRAILER_SOURCE)
    missing = [key for key in required if not values.get(key)]
    if missing:
        raise MetadataError(
            "Missing required changeset trailer(s): " + ", ".join(missing)
        )
    duplicates = [key for key in required if len(values[key]) != 1]
    if duplicates:
        raise MetadataError(
            "Ambiguous duplicate changeset trailer(s): " + ", ".join(duplicates)
        )

    index_text = values[TRAILER_INDEX][0]
    try:
        index = int(index_text)
    except ValueError as exc:
        raise MetadataError(
            f"Changeset-Index must be a positive integer, got {index_text!r}."
        ) from exc

    source_text = values[TRAILER_SOURCE][0]
    source_branch, separator, source_sha = source_text.rpartition(" @ ")
    if not separator:
        raise MetadataError(
            "Changeset-Source must use '<source-branch> @ <source-sha>'."
        )
    return ChangesetMetadata(
        slug=values[TRAILER_SLUG][0],
        index=index,
        source_branch=source_branch,
        source_sha=source_sha,
    )


def render_pr_metadata(metadata: ChangesetMetadata) -> str:
    """Render deterministic, human-invisible pull request metadata."""

    payload = json.dumps(
        {
            "index": metadata.index,
            "slug": metadata.slug,
            "source_branch": metadata.source_branch,
            "source_sha": metadata.source_sha,
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    return f"<!-- {METADATA_MARKER}\n{payload}\n-->"


def embed_pr_metadata(body: str, metadata: ChangesetMetadata) -> str:
    """Append or replace the metadata block without changing human prose."""

    matches = list(_BLOCK_RE.finditer(body))
    if len(matches) > 1:
        raise MetadataError("PR body contains multiple changeset metadata blocks.")
    block = render_pr_metadata(metadata)
    if matches:
        match = matches[0]
        return body[: match.start()] + block + body[match.end() :]
    separator = "\n" if not body or body.endswith("\n") else "\n\n"
    return body + separator + block + "\n"


def parse_pr_metadata(body: str) -> ChangesetMetadata:
    """Parse metadata while tolerating arbitrary edits outside its block."""

    matches = list(_BLOCK_RE.finditer(body))
    if not matches:
        if "carve-changesets:metadata" in body:
            raise MetadataError(
                "Malformed carve-changesets PR metadata block; restore the v1 delimiters."
            )
        raise MetadataError("PR body is missing the carve-changesets metadata block.")
    if len(matches) > 1:
        raise MetadataError("PR body contains multiple changeset metadata blocks.")
    try:
        payload = json.loads(matches[0].group("payload"))
    except json.JSONDecodeError as exc:
        raise MetadataError(
            f"PR metadata block contains invalid JSON: {exc.msg}."
        ) from exc
    if not isinstance(payload, dict):
        raise MetadataError("PR metadata block must contain a JSON object.")
    expected = {"slug", "index", "source_branch", "source_sha"}
    missing = sorted(expected - payload.keys())
    extra = sorted(payload.keys() - expected)
    if missing:
        raise MetadataError("PR metadata is missing field(s): " + ", ".join(missing))
    if extra:
        raise MetadataError("PR metadata has unknown field(s): " + ", ".join(extra))
    if not isinstance(payload["slug"], str):
        raise MetadataError("PR metadata field 'slug' must be a string.")
    if not isinstance(payload["index"], int) or isinstance(payload["index"], bool):
        raise MetadataError("PR metadata field 'index' must be an integer.")
    if not isinstance(payload["source_branch"], str):
        raise MetadataError("PR metadata field 'source_branch' must be a string.")
    if not isinstance(payload["source_sha"], str):
        raise MetadataError("PR metadata field 'source_sha' must be a string.")
    return ChangesetMetadata(
        slug=payload["slug"],
        index=payload["index"],
        source_branch=payload["source_branch"],
        source_sha=payload["source_sha"],
    )
