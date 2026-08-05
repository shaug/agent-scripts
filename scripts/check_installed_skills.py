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

Because the failure being detected is a silent success, this command treats its
own silent successes as failures too. Comparing nothing, being pointed at a
directory that does not exist, and failing to read part of a tree are all
reported and exit non-zero rather than passing quietly.

An installed copy is matched by the name its `SKILL.md` declares, not by its
directory name, because that declared name is what an agent runtime loads. A
stale copy left behind under a different directory name is still a live skill.

The comparison is against the working tree, not against `origin/main`: a
checkout that is itself behind the remote will report "in sync" while both
copies are stale. Update the checkout first when that matters.
"""

from __future__ import annotations

import argparse
import filecmp
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_SKILLS_ROOT = "~/.agents/skills"
SKILLS_ROOT_ENV = "AGENTS_SKILLS_DIR"

EXIT_IN_SYNC = 0
EXIT_DRIFTED = 1
EXIT_MISCONFIGURED = 2

# Interpreter and filesystem byproducts, which appear at any depth.
IGNORED_DIRECTORY_NAMES = frozenset({"__pycache__"})
IGNORED_FILE_NAMES = frozenset({".DS_Store"})
IGNORED_FILE_SUFFIXES = frozenset({".pyc"})

# Paths relative to a skill root that are not part of what gets distributed:
# the record-keeping directory `AGENTS.md` prescribes, and the eval summaries
# `just eval-record` appends, which are committed evidence for repository
# readers and grow after every recorded run without changing what an installed
# skill does. Each skill's own `.<skill-name>` directory is added per skill.
IGNORED_SKILL_RELATIVE_DIRECTORIES = frozenset({".skill-state", "evals/results"})

FRONTMATTER_FENCE = "---"
NAME_FIELD = re.compile(r"name:\s*(\S+)")


@dataclass
class SkillComparison:
    """One installed copy of a skill measured against its repository source."""

    name: str
    directory: Path
    differing: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    extra: list[str] = field(default_factory=list)
    unreadable: list[str] = field(default_factory=list)

    @property
    def misnamed(self) -> bool:
        """The copy declares this skill from a differently named directory."""
        return self.directory.name != self.name

    @property
    def is_drifted(self) -> bool:
        return bool(
            self.differing
            or self.missing
            or self.extra
            or self.unreadable
            or self.misnamed
        )


@dataclass
class Report:
    """The complete result of one comparison run."""

    skills_root: Path
    compared: list[SkillComparison] = field(default_factory=list)
    not_installed: list[str] = field(default_factory=list)

    @property
    def drifted(self) -> list[SkillComparison]:
        return [comparison for comparison in self.compared if comparison.is_drifted]

    @property
    def is_clean(self) -> bool:
        # Comparing nothing is never a match: it means the skills root holds no
        # copy of anything this repository ships, which is a misconfigured path
        # far more often than it is a deliberate empty install.
        return bool(self.compared) and not self.drifted


def _ignored_file(name: str) -> bool:
    return name in IGNORED_FILE_NAMES or Path(name).suffix in IGNORED_FILE_SUFFIXES


def _distributed_files(root: Path, skill: str) -> tuple[set[str], list[str]]:
    """Every distributed file under `root`, plus any subtree that cannot be read.

    Returns POSIX paths relative to `root`. Symlinked directories are followed
    so a copy assembled out of links compares by content, with a realpath guard
    so a cycle terminates instead of walking forever.
    """
    ignored_relative = {Path(entry) for entry in IGNORED_SKILL_RELATIVE_DIRECTORIES}
    ignored_relative.add(Path(f".{skill}"))

    found: set[str] = set()
    unreadable: list[str] = []
    visited: set[str] = set()

    def record_unreadable(error: OSError) -> None:
        unreadable.append(str(error.filename or root))

    for directory, subdirectories, filenames in os.walk(
        root, followlinks=True, onerror=record_unreadable
    ):
        real = os.path.realpath(directory)
        if real in visited:
            subdirectories[:] = []
            continue
        visited.add(real)

        relative_directory = Path(directory).relative_to(root)
        subdirectories[:] = [
            name
            for name in subdirectories
            if name not in IGNORED_DIRECTORY_NAMES
            and relative_directory / name not in ignored_relative
        ]
        for filename in filenames:
            if _ignored_file(filename):
                continue
            found.add((relative_directory / filename).as_posix())

    return found, unreadable


def _declared_name(skill_document: Path) -> str | None:
    """The `name:` a `SKILL.md` declares in its frontmatter, if it has one."""
    try:
        lines = skill_document.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines()
    except OSError:
        return None
    if not lines or lines[0].strip() != FRONTMATTER_FENCE:
        return None
    for line in lines[1:]:
        if line.strip() == FRONTMATTER_FENCE:
            return None
        match = NAME_FIELD.fullmatch(line.strip())
        if match:
            return match.group(1)
    return None


def _repository_skills(repository_root: Path) -> list[str]:
    return sorted(
        path.parent.name
        for path in (repository_root / "skills").glob("*/SKILL.md")
        if path.is_file()
    )


def _installed_copies(skills_root: Path, skills: list[str]) -> dict[str, list[Path]]:
    """Map each repository skill to every installed directory providing it.

    A directory is matched by the name its `SKILL.md` declares, so a copy
    renamed on disk is still found. A directory named for a repository skill is
    matched too, even with an absent or unreadable `SKILL.md`, so a gutted
    install is reported rather than mistaken for an absent one.
    """
    known = set(skills)
    copies: dict[str, list[Path]] = {}
    for document in sorted(skills_root.glob("*/SKILL.md")):
        declared = _declared_name(document) or document.parent.name
        if declared in known:
            copies.setdefault(declared, []).append(document.parent)
    for skill in skills:
        directory = skills_root / skill
        if directory.is_dir() and directory not in copies.get(skill, []):
            copies.setdefault(skill, []).append(directory)
    return copies


def compare(repository_root: Path, skills_root: Path) -> Report:
    """Compare every repository skill installed under `skills_root`."""
    report = Report(skills_root=skills_root)
    skills = _repository_skills(repository_root)
    installed = _installed_copies(skills_root, skills)

    for skill in skills:
        directories = installed.get(skill)
        if not directories:
            report.not_installed.append(skill)
            continue

        source = repository_root / "skills" / skill
        source_files, source_unreadable = _distributed_files(source, skill)
        for directory in sorted(directories):
            installed_files, installed_unreadable = _distributed_files(directory, skill)
            comparison = SkillComparison(
                name=skill,
                directory=directory,
                missing=sorted(source_files - installed_files),
                extra=sorted(installed_files - source_files),
                unreadable=sorted(source_unreadable + installed_unreadable),
            )
            comparison.differing = sorted(
                relative
                for relative in source_files & installed_files
                if not _same_content(source / relative, directory / relative)
            )
            report.compared.append(comparison)
    return report


def _same_content(source: Path, installed: Path) -> bool:
    """Whether two distributed files are byte-identical.

    A file that cannot be read at all — a dangling symlink most often — counts
    as different rather than raising, so one broken entry is reported as drift
    instead of aborting every remaining skill's comparison.
    """
    try:
        return filecmp.cmp(source, installed, shallow=False)
    except OSError:
        return False


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
        if comparison.misnamed:
            lines.append(
                f"           installed in directory {comparison.directory.name}, "
                f"which declares skill {comparison.name}"
            )
        for label, paths in (
            ("differs", comparison.differing),
            ("missing", comparison.missing),
            ("extra", comparison.extra),
            ("unreadable", comparison.unreadable),
        ):
            lines.extend(f"           {label}: {path}" for path in paths)

    if report.not_installed:
        lines.append(f"  not installed: {', '.join(report.not_installed)}")

    lines.append("")
    if not report.compared:
        lines.append(
            f"No skill from this repository is installed in {report.skills_root}, "
            "so nothing was compared."
        )
        return "\n".join(lines)
    if report.is_clean:
        lines.append("Installed skills match this repository.")
        return "\n".join(lines)

    names = sorted({comparison.name for comparison in report.drifted})
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


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    supplied = args.skills_root or os.environ.get(SKILLS_ROOT_ENV)
    skills_root = Path(supplied or DEFAULT_SKILLS_ROOT).expanduser()

    if not skills_root.is_dir():
        if supplied:
            # Naming a root is an assertion that it exists. Skipping quietly
            # would turn a typo into a check that can never fail.
            print(f"error: {skills_root} is not a directory", file=sys.stderr)
            return EXIT_MISCONFIGURED
        print(f"No installed skills directory at {skills_root}; nothing to compare")
        return EXIT_IN_SYNC

    repository_root = Path(__file__).resolve().parents[1]
    report = compare(repository_root, skills_root)
    print(render(report))
    return EXIT_IN_SYNC if report.is_clean else EXIT_DRIFTED


if __name__ == "__main__":
    raise SystemExit(main())
