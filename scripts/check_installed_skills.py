#!/usr/bin/env python3
"""Compare installed skill copies against this repository's `skills/` tree.

Skills are distributed by copying a skill folder out of this repository into an
agent's skills directory, so an installed copy is a snapshot that never learns
about later commits. That drift is silent in the worst possible place: a stale
review skill still runs, still validates its own result against the stale
contract it shipped with, and still reports a verdict. Nothing inside the
installed snapshot can detect the problem, because the snapshot is internally
consistent — old prose, old schema, and old validator all agree with each other.
Detection has to compare the snapshot against a source of truth outside it,
which is what this check does.

The comparison is against the working tree, not against `origin/main`: a
checkout that is itself behind the remote will report "in sync" while both
copies are stale. Update the checkout first when that matters.
"""

from __future__ import annotations

import argparse
import filecmp
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_SKILLS_ROOT = "~/.agents/skills"
SKILLS_ROOT_ENV = "AGENTS_SKILLS_DIR"

# Record-keeping directories a skill writes at runtime, per AGENTS.md, plus
# interpreter and filesystem byproducts. None of these are distributed, so a
# difference in them is not drift.
IGNORED_DIRECTORY_NAMES = frozenset({"__pycache__", ".skill-state"})
IGNORED_FILE_NAMES = frozenset({".DS_Store"})
IGNORED_FILE_SUFFIXES = frozenset({".pyc", ".pyo"})


@dataclass
class SkillComparison:
    """One skill's installed copy measured against its repository source."""

    name: str
    differing: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    extra: list[str] = field(default_factory=list)

    @property
    def is_drifted(self) -> bool:
        return bool(self.differing or self.missing or self.extra)


@dataclass
class Report:
    """The complete result of one comparison run."""

    skills_root: Path
    compared: list[SkillComparison] = field(default_factory=list)
    not_installed: list[str] = field(default_factory=list)

    @property
    def drifted(self) -> list[SkillComparison]:
        return [comparison for comparison in self.compared if comparison.is_drifted]


def _ignored_directory(name: str, skill: str) -> bool:
    return name in IGNORED_DIRECTORY_NAMES or name == f".{skill}"


def _ignored_file(name: str) -> bool:
    return name in IGNORED_FILE_NAMES or Path(name).suffix in IGNORED_FILE_SUFFIXES


def _relative_files(root: Path, skill: str) -> set[str]:
    """Every distributed file under `root`, as POSIX paths relative to it."""
    found: set[str] = set()
    for directory, subdirectories, filenames in os.walk(root):
        subdirectories[:] = [
            name for name in subdirectories if not _ignored_directory(name, skill)
        ]
        for filename in filenames:
            if _ignored_file(filename):
                continue
            path = Path(directory, filename)
            found.add(path.relative_to(root).as_posix())
    return found


def _repository_skills(repository_root: Path) -> list[str]:
    return sorted(
        path.parent.name
        for path in (repository_root / "skills").glob("*/SKILL.md")
        if path.is_file()
    )


def compare(repository_root: Path, skills_root: Path) -> Report:
    """Compare every repository skill that is installed under `skills_root`."""
    report = Report(skills_root=skills_root)
    for skill in _repository_skills(repository_root):
        installed = skills_root / skill
        if not installed.is_dir():
            report.not_installed.append(skill)
            continue

        source = repository_root / "skills" / skill
        source_files = _relative_files(source, skill)
        installed_files = _relative_files(installed, skill)
        comparison = SkillComparison(
            name=skill,
            missing=sorted(source_files - installed_files),
            extra=sorted(installed_files - source_files),
        )
        comparison.differing = sorted(
            relative
            for relative in source_files & installed_files
            if not filecmp.cmp(source / relative, installed / relative, shallow=False)
        )
        report.compared.append(comparison)
    return report


def render(report: Report) -> str:
    """Render a report as the operator-facing text the command prints."""
    lines = [
        f"Comparing installed skills in {report.skills_root} against this repository"
    ]
    for comparison in report.compared:
        if not comparison.is_drifted:
            lines.append(f"  ok     {comparison.name}")
            continue
        lines.append(f"  drift  {comparison.name}")
        for label, paths in (
            ("differs", comparison.differing),
            ("missing", comparison.missing),
            ("extra", comparison.extra),
        ):
            lines.extend(f"           {label}: {path}" for path in paths)

    if report.not_installed:
        lines.append(f"  not installed: {', '.join(report.not_installed)}")

    drifted = report.drifted
    if not drifted:
        lines.append("")
        lines.append("Installed skills match this repository.")
        return "\n".join(lines)

    names = [comparison.name for comparison in drifted]
    lines.append("")
    lines.append(f"Installed skills are stale: {', '.join(names)}")
    lines.append("Re-install them from this repository, for example:")
    lines.append(f"  skills update -g -y {' '.join(names)}")
    return "\n".join(lines)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare installed skill copies against this repository."
    )
    parser.add_argument(
        "--skills-root",
        help=(
            "Installed skills directory "
            f"(default: ${SKILLS_ROOT_ENV} or {DEFAULT_SKILLS_ROOT})"
        ),
    )
    return parser.parse_args(argv)


def _resolve_skills_root(argument: str | None) -> Path:
    raw = argument or os.environ.get(SKILLS_ROOT_ENV) or DEFAULT_SKILLS_ROOT
    return Path(raw).expanduser()


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    skills_root = _resolve_skills_root(args.skills_root)
    if not skills_root.is_dir():
        print(f"No installed skills directory at {skills_root}; nothing to compare")
        return 0

    repository_root = Path(__file__).resolve().parents[1]
    report = compare(repository_root, skills_root)
    print(render(report))
    return 1 if report.drifted else 0


if __name__ == "__main__":
    raise SystemExit(main())
