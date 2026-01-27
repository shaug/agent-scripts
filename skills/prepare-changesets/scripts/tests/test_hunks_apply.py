from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import helpers
from chain import compare_chain, create_chain
from plan_checks import validate_plan_strict


def _write_lines(path: Path, lines: list[str]) -> None:
    path.write_text("".join(line + "\n" for line in lines))


def _init_hunk_repo() -> tuple[Path, dict]:
    repo_dir = Path(tempfile.mkdtemp(prefix="pcs-test-hunks-"))
    helpers.run(["git", "init", "-b", "main"], cwd=repo_dir)
    helpers.run(["git", "config", "user.name", "PCS Test"], cwd=repo_dir)
    helpers.run(["git", "config", "user.email", "pcs-test@example.com"], cwd=repo_dir)
    (repo_dir / ".gitignore").write_text(".prepare-changesets/\n")

    base_lines = [f"line-{i}" for i in range(1, 41)]
    _write_lines(repo_dir / "notes.txt", base_lines)
    helpers.run(["git", "add", "-A"], cwd=repo_dir)
    helpers.run(["git", "commit", "-m", "base"], cwd=repo_dir)

    helpers.run(["git", "checkout", "-b", "feature/hunks"], cwd=repo_dir)
    source_lines = base_lines[:]
    source_lines[1] = "line-2 changed"
    source_lines[29] = "line-30 changed"
    _write_lines(repo_dir / "notes.txt", source_lines)
    helpers.run(["git", "add", "-A"], cwd=repo_dir)
    helpers.run(["git", "commit", "-m", "feature"], cwd=repo_dir)

    plan = {
        "feature_title": "Hunk feature",
        "base_branch": "main",
        "source_branch": "feature/hunks",
        "test_command": "",
        "changesets": [
            {
                "slug": "hunk-1",
                "description": "Apply first hunk.",
                "mode": "hunks",
                "include_paths": ["notes.txt"],
                "exclude_paths": [],
                "allow_partial_files": True,
                "hunk_selectors": [
                    {"file": "notes.txt", "contains": ["line-2 changed"]}
                ],
                "commit_message": "cs1",
                "pr_notes": [],
            },
            {
                "slug": "hunk-2",
                "description": "Apply second hunk.",
                "mode": "hunks",
                "include_paths": ["notes.txt"],
                "exclude_paths": [],
                "allow_partial_files": True,
                "hunk_selectors": [
                    {"file": "notes.txt", "contains": ["line-30 changed"]}
                ],
                "commit_message": "cs2",
                "pr_notes": [],
            },
        ],
    }

    return repo_dir, plan


def _init_context_shift_repo() -> tuple[Path, dict]:
    repo_dir = Path(tempfile.mkdtemp(prefix="pcs-test-shift-"))
    helpers.run(["git", "init", "-b", "main"], cwd=repo_dir)
    helpers.run(["git", "config", "user.name", "PCS Test"], cwd=repo_dir)
    helpers.run(["git", "config", "user.email", "pcs-test@example.com"], cwd=repo_dir)
    (repo_dir / ".gitignore").write_text(".prepare-changesets/\n")

    base_lines = [f"row-{i}" for i in range(1, 41)]
    _write_lines(repo_dir / "shift.txt", base_lines)
    helpers.run(["git", "add", "-A"], cwd=repo_dir)
    helpers.run(["git", "commit", "-m", "base"], cwd=repo_dir)

    helpers.run(["git", "checkout", "-b", "feature/shift"], cwd=repo_dir)
    source_lines = base_lines[:]
    source_lines.insert(5, "row-5.5 inserted")
    source_lines[30] = "row-31 changed"
    _write_lines(repo_dir / "shift.txt", source_lines)
    helpers.run(["git", "add", "-A"], cwd=repo_dir)
    helpers.run(["git", "commit", "-m", "feature"], cwd=repo_dir)

    plan = {
        "feature_title": "Shift feature",
        "base_branch": "main",
        "source_branch": "feature/shift",
        "test_command": "",
        "changesets": [
            {
                "slug": "insert",
                "description": "Insert line.",
                "mode": "hunks",
                "include_paths": ["shift.txt"],
                "exclude_paths": [],
                "allow_partial_files": True,
                "hunk_selectors": [
                    {"file": "shift.txt", "contains": ["row-5.5 inserted"]}
                ],
                "commit_message": "cs1",
                "pr_notes": [],
            },
            {
                "slug": "change",
                "description": "Modify later line.",
                "mode": "hunks",
                "include_paths": ["shift.txt"],
                "exclude_paths": [],
                "allow_partial_files": True,
                "hunk_selectors": [
                    {"file": "shift.txt", "contains": ["row-31 changed"]}
                ],
                "commit_message": "cs2",
                "pr_notes": [],
            },
        ],
    }

    return repo_dir, plan


def _init_patch_repo() -> tuple[Path, dict]:
    repo_dir = Path(tempfile.mkdtemp(prefix="pcs-test-patch-"))
    helpers.run(["git", "init", "-b", "main"], cwd=repo_dir)
    helpers.run(["git", "config", "user.name", "PCS Test"], cwd=repo_dir)
    helpers.run(["git", "config", "user.email", "pcs-test@example.com"], cwd=repo_dir)
    (repo_dir / ".gitignore").write_text(".prepare-changesets/\n")

    (repo_dir / "patch.txt").write_text("base\n")
    helpers.run(["git", "add", "-A"], cwd=repo_dir)
    helpers.run(["git", "commit", "-m", "base"], cwd=repo_dir)

    helpers.run(["git", "checkout", "-b", "feature/patch"], cwd=repo_dir)
    (repo_dir / "patch.txt").write_text("base\npatch\n")
    helpers.run(["git", "add", "-A"], cwd=repo_dir)
    helpers.run(["git", "commit", "-m", "feature"], cwd=repo_dir)

    patch_dir = repo_dir / ".prepare-changesets" / "patches"
    patch_dir.mkdir(parents=True, exist_ok=True)
    diff = helpers.run(
        ["git", "diff", "main..feature/patch", "--", "patch.txt"],
        cwd=repo_dir,
    ).stdout
    (patch_dir / "patch.txt.patch").write_text(diff)

    plan = {
        "feature_title": "Patch feature",
        "base_branch": "main",
        "source_branch": "feature/patch",
        "test_command": "",
        "changesets": [
            {
                "slug": "patch",
                "description": "Apply patch file.",
                "mode": "patch",
                "patch_file": ".prepare-changesets/patches/patch.txt.patch",
                "commit_message": "cs1",
                "pr_notes": [],
            }
        ],
    }

    return repo_dir, plan


def _init_rename_repo() -> tuple[Path, dict]:
    repo_dir = Path(tempfile.mkdtemp(prefix="pcs-test-rename-"))
    helpers.run(["git", "init", "-b", "main"], cwd=repo_dir)
    helpers.run(["git", "config", "user.name", "PCS Test"], cwd=repo_dir)
    helpers.run(["git", "config", "user.email", "pcs-test@example.com"], cwd=repo_dir)
    (repo_dir / ".gitignore").write_text(".prepare-changesets/\n")

    (repo_dir / "old.txt").write_text("alpha\nbeta\ngamma\n")
    helpers.run(["git", "add", "-A"], cwd=repo_dir)
    helpers.run(["git", "commit", "-m", "base"], cwd=repo_dir)

    helpers.run(["git", "checkout", "-b", "feature/rename"], cwd=repo_dir)
    helpers.run(["git", "mv", "old.txt", "new.txt"], cwd=repo_dir)
    (repo_dir / "new.txt").write_text("alpha\nbeta changed\ngamma\n")
    helpers.run(["git", "add", "-A"], cwd=repo_dir)
    helpers.run(["git", "commit", "-m", "rename"], cwd=repo_dir)

    plan = {
        "feature_title": "Rename feature",
        "base_branch": "main",
        "source_branch": "feature/rename",
        "test_command": "",
        "changesets": [
            {
                "slug": "rename-hunk",
                "description": "Rename plus hunk.",
                "mode": "hunks",
                "include_paths": ["new.txt"],
                "exclude_paths": [],
                "allow_partial_files": True,
                "hunk_selectors": [{"file": "old.txt", "contains": ["beta changed"]}],
                "commit_message": "cs1",
                "pr_notes": [],
            }
        ],
    }

    return repo_dir, plan


class HunkApplyTests(unittest.TestCase):
    def test_hunks_apply_simple(self) -> None:
        repo_dir, plan = _init_hunk_repo()
        try:
            with helpers.chdir(repo_dir):
                create_chain(plan)
                diffstat, namestatus = compare_chain(plan)
                self.assertEqual(diffstat, "")
                self.assertEqual(namestatus, "")
        finally:
            shutil.rmtree(repo_dir)

    def test_hunks_apply_with_context_shift(self) -> None:
        repo_dir, plan = _init_context_shift_repo()
        try:
            with helpers.chdir(repo_dir):
                create_chain(plan)
                diffstat, namestatus = compare_chain(plan)
                self.assertEqual(diffstat, "")
                self.assertEqual(namestatus, "")
        finally:
            shutil.rmtree(repo_dir)

    def test_hunks_selector_ambiguous(self) -> None:
        repo_dir, plan = _init_hunk_repo()
        try:
            plan["changesets"][0]["hunk_selectors"] = [
                {"file": "notes.txt", "contains": ["line-"]}
            ]
            with helpers.chdir(repo_dir):
                ok, errors, _warnings = validate_plan_strict(plan)
                self.assertFalse(ok)
                self.assertTrue(errors)
        finally:
            shutil.rmtree(repo_dir)

    def test_patch_mode(self) -> None:
        repo_dir, plan = _init_patch_repo()
        try:
            with helpers.chdir(repo_dir):
                create_chain(plan)
                diffstat, namestatus = compare_chain(plan)
                self.assertEqual(diffstat, "")
                self.assertEqual(namestatus, "")
        finally:
            shutil.rmtree(repo_dir)

    def test_hunks_with_rename_scope_include_new_path(self) -> None:
        repo_dir, plan = _init_rename_repo()
        try:
            with helpers.chdir(repo_dir):
                ok, errors, warnings = validate_plan_strict(plan)
                self.assertTrue(ok, f"expected strict validation to pass: {errors}")
                self.assertTrue(warnings, "expected a warning for old path usage")
                create_chain(plan)
                diffstat, namestatus = compare_chain(plan)
                self.assertEqual(diffstat, "")
                self.assertEqual(namestatus, "")
        finally:
            shutil.rmtree(repo_dir)

    def test_hunks_with_rename_scope_exclude_either_path(self) -> None:
        repo_dir, plan = _init_rename_repo()
        try:
            plan["changesets"][0]["exclude_paths"] = ["old.txt"]
            with helpers.chdir(repo_dir):
                ok, errors, _warnings = validate_plan_strict(plan)
                self.assertFalse(ok)
                self.assertTrue(errors)
        finally:
            shutil.rmtree(repo_dir)


if __name__ == "__main__":
    unittest.main()
