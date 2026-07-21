#!/usr/bin/env python3
"""Patch and hunk-based changeset application helpers."""

from __future__ import annotations

import fnmatch
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from common import CommandError, git, repo_root


@dataclass(frozen=True)
class HunkSelector:
    file: str
    range_header: Optional[str]
    contains: Tuple[str, ...]
    excludes: Tuple[str, ...]
    occurrence: Optional[int]
    all_hunks: bool
    has_filters: bool


@dataclass
class Hunk:
    header: str
    lines: List[str]

    @property
    def body_lines(self) -> List[str]:
        return self.lines[1:]

    @property
    def body_text(self) -> str:
        return "\n".join(self.body_lines)


@dataclass
class DiffFile:
    old_path: Optional[str]
    new_path: Optional[str]
    header_lines: List[str]
    hunks: List[Hunk] = field(default_factory=list)
    is_binary: bool = False
    binary_lines: List[str] = field(default_factory=list)


@dataclass
class SelectedPatch:
    text: str
    files: int
    hunks: int
    file_labels: List[str]


def _strip_prefix(path: str) -> Optional[str]:
    if path in ("/dev/null", "dev/null"):
        return None
    if path.startswith("a/") or path.startswith("b/"):
        return path[2:]
    return path


def _file_label(df: DiffFile) -> str:
    return df.new_path or df.old_path or "<unknown>"


def _matches_any(path: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(path, pat) for pat in patterns)


def parse_hunk_selectors(
    selectors: Sequence[Dict], *, changeset_label: str
) -> List[HunkSelector]:
    parsed: List[HunkSelector] = []
    for idx, raw in enumerate(selectors, start=1):
        if not isinstance(raw, dict):
            raise CommandError(
                f"{changeset_label}: hunk selector {idx} must be an object."
            )
        file_path = raw.get("file")
        if not isinstance(file_path, str) or not file_path.strip():
            raise CommandError(
                f"{changeset_label}: hunk selector {idx} missing valid 'file'."
            )
        range_header = raw.get("range")
        if range_header is not None and not isinstance(range_header, str):
            raise CommandError(
                f"{changeset_label}: hunk selector {idx} 'range' must be a string."
            )
        contains = raw.get("contains", [])
        excludes = raw.get("excludes", [])
        if contains and (
            not isinstance(contains, list)
            or not all(isinstance(c, str) for c in contains)
        ):
            raise CommandError(
                f"{changeset_label}: hunk selector {idx} 'contains' must be a string array."
            )
        if excludes and (
            not isinstance(excludes, list)
            or not all(isinstance(c, str) for c in excludes)
        ):
            raise CommandError(
                f"{changeset_label}: hunk selector {idx} 'excludes' must be a string array."
            )
        all_hunks = raw.get("all", False)
        if all_hunks is not False and not isinstance(all_hunks, bool):
            raise CommandError(
                f"{changeset_label}: hunk selector {idx} 'all' must be a boolean."
            )

        occurrence = raw.get("occurrence")
        if occurrence is not None and (
            not isinstance(occurrence, int) or occurrence < 1
        ):
            raise CommandError(
                f"{changeset_label}: hunk selector {idx} 'occurrence' must be a positive integer."
            )

        has_filters = bool(
            all_hunks or range_header or contains or excludes or occurrence is not None
        )

        parsed.append(
            HunkSelector(
                file=file_path,
                range_header=str(range_header).strip() if range_header else None,
                contains=tuple(str(c) for c in contains),
                excludes=tuple(str(c) for c in excludes),
                occurrence=occurrence,
                all_hunks=bool(all_hunks),
                has_filters=has_filters,
            )
        )
    return parsed


def parse_unified_diff(diff_text: str) -> List[DiffFile]:
    lines = diff_text.splitlines()
    files: List[DiffFile] = []
    current: Optional[DiffFile] = None
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("diff --git "):
            if current:
                files.append(current)
            parts = line.split(" ")
            old_path = _strip_prefix(parts[2]) if len(parts) > 2 else None
            new_path = _strip_prefix(parts[3]) if len(parts) > 3 else None
            current = DiffFile(
                old_path=old_path,
                new_path=new_path,
                header_lines=[line],
            )
            i += 1
            continue

        if current is None:
            i += 1
            continue

        if line.startswith("GIT binary patch"):
            current.is_binary = True
            while i < len(lines):
                line = lines[i]
                if line.startswith("diff --git "):
                    break
                current.binary_lines.append(line)
                i += 1
            continue

        if line.startswith("@@ "):
            hunk_lines = [line]
            i += 1
            while i < len(lines):
                line = lines[i]
                if line.startswith("diff --git ") or line.startswith("@@ "):
                    break
                hunk_lines.append(line)
                i += 1
            current.hunks.append(Hunk(header=hunk_lines[0], lines=hunk_lines))
            continue

        current.header_lines.append(line)
        i += 1

    if current:
        files.append(current)

    return files


def build_diff(base: str, source: str) -> List[DiffFile]:
    diff = git(
        "diff",
        "--binary",
        "--full-index",
        "--find-renames=20%",
        f"{base}..{source}",
    ).stdout
    return parse_unified_diff(diff)


def _selectors_for_file(
    selectors: Sequence[HunkSelector], df: DiffFile
) -> List[HunkSelector]:
    label = _file_label(df)
    matched: List[HunkSelector] = []
    for selector in selectors:
        if selector.file == label:
            matched.append(selector)
            continue
        if df.old_path and selector.file == df.old_path:
            matched.append(selector)
            continue
        if df.new_path and selector.file == df.new_path:
            matched.append(selector)
    return matched


def select_hunks_for_changeset(
    diff_files: Sequence[DiffFile],
    selectors: Sequence[HunkSelector],
    *,
    include_paths: Sequence[str],
    exclude_paths: Sequence[str],
    allow_partial_files: bool,
    changeset_label: str,
) -> SelectedPatch:
    if not selectors:
        raise CommandError(f"{changeset_label}: hunk_selectors must be non-empty.")

    patch_lines: List[str] = []
    selected_files: List[str] = []
    selected_hunks = 0
    seen_selectors = {id(selector): False for selector in selectors}

    for df in diff_files:
        file_selectors = _selectors_for_file(selectors, df)
        if not file_selectors:
            continue

        label = _file_label(df)
        labels = {p for p in (df.old_path, df.new_path) if p}
        if df.is_binary:
            raise CommandError(
                f"{changeset_label}: {label} is binary; use mode=patch for binary files."
            )
        if not df.hunks:
            raise CommandError(
                f"{changeset_label}: {label} has no hunks available to select."
            )

        select_all = any(sel.all_hunks for sel in file_selectors) or (
            not allow_partial_files
            and any(not sel.has_filters for sel in file_selectors)
        )
        chosen: List[Hunk] = []
        if select_all:
            for selector in file_selectors:
                seen_selectors[id(selector)] = True
                if include_paths and not any(
                    _matches_any(path, include_paths) for path in labels
                ):
                    raise CommandError(
                        f"{changeset_label}: selector file {selector.file} does not match include_paths."
                    )
                if exclude_paths and any(
                    _matches_any(path, exclude_paths) for path in labels
                ):
                    raise CommandError(
                        f"{changeset_label}: selector file {selector.file} is excluded by exclude_paths."
                    )
            chosen = list(df.hunks)
        else:
            for selector in file_selectors:
                seen_selectors[id(selector)] = True
                if include_paths and not any(
                    _matches_any(path, include_paths) for path in labels
                ):
                    raise CommandError(
                        f"{changeset_label}: selector file {selector.file} does not match include_paths."
                    )
                if exclude_paths and any(
                    _matches_any(path, exclude_paths) for path in labels
                ):
                    raise CommandError(
                        f"{changeset_label}: selector file {selector.file} is excluded by exclude_paths."
                    )
                candidates: List[Hunk] = []
                for hunk in df.hunks:
                    if (
                        selector.range_header
                        and selector.range_header.strip() != hunk.header.strip()
                    ):
                        continue
                    body = hunk.body_text
                    if selector.contains and not all(
                        c in body for c in selector.contains
                    ):
                        continue
                    if selector.excludes and any(c in body for c in selector.excludes):
                        continue
                    candidates.append(hunk)

                if not candidates:
                    raise CommandError(
                        f"{changeset_label}: selector for {label} matched no hunks."
                    )

                if selector.occurrence is not None:
                    if selector.occurrence > len(candidates):
                        raise CommandError(
                            f"{changeset_label}: selector for {label} occurrence {selector.occurrence}"
                            f" exceeds {len(candidates)} matches."
                        )
                    chosen_hunk = candidates[selector.occurrence - 1]
                    if chosen_hunk not in chosen:
                        chosen.append(chosen_hunk)
                else:
                    if len(candidates) > 1:
                        raise CommandError(
                            f"{changeset_label}: selector for {label} matched multiple hunks; "
                            "add 'occurrence' to disambiguate."
                        )
                    if candidates[0] not in chosen:
                        chosen.append(candidates[0])

        if not allow_partial_files and len(chosen) != len(df.hunks):
            raise CommandError(
                f"{changeset_label}: {label} requires all hunks when allow_partial_files=false."
            )

        if chosen:
            patch_lines.extend(df.header_lines)
            for hunk in chosen:
                patch_lines.extend(hunk.lines)
            selected_files.append(label)
            selected_hunks += len(chosen)

    missing = [s.file for s in selectors if not seen_selectors[id(s)]]
    if missing:
        missing_list = ", ".join(sorted(set(missing)))
        raise CommandError(
            f"{changeset_label}: selector file(s) not found in diff: {missing_list}."
        )

    if not selected_files:
        raise CommandError(f"{changeset_label}: no hunks selected for this changeset.")

    patch_text = "\n".join(patch_lines) + "\n"
    return SelectedPatch(
        text=patch_text,
        files=len(selected_files),
        hunks=selected_hunks,
        file_labels=selected_files,
    )


def apply_patch_text(patch_text: str, *, label: str) -> None:
    if not patch_text.strip():
        raise CommandError(f"{label}: patch is empty.")

    with tempfile.NamedTemporaryFile("w", delete=False, prefix="pcs-patch-") as handle:
        handle.write(patch_text)
        patch_path = Path(handle.name)

    try:
        result = git(
            "apply",
            "--index",
            "--3way",
            "--whitespace=nowarn",
            str(patch_path),
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise CommandError(
                f"{label}: git apply failed.\n{detail or 'Patch did not apply cleanly.'}"
            )
    finally:
        patch_path.unlink(missing_ok=True)


def check_patch_text(patch_text: str, *, label: str) -> None:
    if not patch_text.strip():
        raise CommandError(f"{label}: patch is empty.")

    with tempfile.NamedTemporaryFile("w", delete=False, prefix="pcs-patch-") as handle:
        handle.write(patch_text)
        patch_path = Path(handle.name)

    try:
        result = git(
            "apply",
            "--check",
            "--3way",
            "--whitespace=nowarn",
            str(patch_path),
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise CommandError(
                f"{label}: git apply --check failed.\n"
                f"{detail or 'Patch did not apply cleanly.'}"
            )
    finally:
        patch_path.unlink(missing_ok=True)


def resolve_patch_path(patch_file: str) -> Path:
    raw = Path(patch_file)
    return raw if raw.is_absolute() else repo_root() / raw


def apply_patch_file(patch_file: str, *, label: str) -> None:
    patch_path = resolve_patch_path(patch_file)
    if not patch_path.exists():
        raise CommandError(f"{label}: patch file not found: {patch_path}")
    patch_text = patch_path.read_text()
    apply_patch_text(patch_text, label=label)


def check_patch_file(patch_file: str, *, label: str) -> None:
    patch_path = resolve_patch_path(patch_file)
    if not patch_path.exists():
        raise CommandError(f"{label}: patch file not found: {patch_path}")
    patch_text = patch_path.read_text()
    check_patch_text(patch_text, label=label)
