from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import shutil
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "check_installed_skills", REPOSITORY_ROOT / "scripts" / "check_installed_skills.py"
)
assert SPEC is not None and SPEC.loader is not None
check_installed_skills = importlib.util.module_from_spec(SPEC)
# Registered before execution so the module's dataclasses can resolve their own
# module namespace during class creation.
sys.modules[SPEC.name] = check_installed_skills
SPEC.loader.exec_module(check_installed_skills)

DISTRIBUTION_EXCLUSIONS = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store")

# Named only as fixture material. Assertions below never depend on their prose,
# so renaming a heading inside either skill cannot silently defuse a test.
A_SKILL = "review-correctness"
ANOTHER_SKILL = "review-code-change"


class CheckInstalledSkillsTests(unittest.TestCase):
    """The command's observable contract: what it prints and what it exits."""

    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.skills_root = Path(directory.name)

    def install(self, *skills: str, as_directory: str | None = None) -> Path:
        """Copy repository skills into the fixture as a distribution would."""
        sources = (
            [REPOSITORY_ROOT / "skills" / skill for skill in skills]
            if skills
            else sorted(
                path.parent
                for path in (REPOSITORY_ROOT / "skills").glob("*/SKILL.md")
                if path.is_file()
            )
        )
        destination = self.skills_root
        for source in sources:
            destination = self.skills_root / (as_directory or source.name)
            shutil.copytree(source, destination, ignore=DISTRIBUTION_EXCLUSIONS)
        return destination

    def run_check(self, *extra_argv: str) -> tuple[int, str]:
        stream = io.StringIO()
        errors = io.StringIO()
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(errors):
            status = check_installed_skills.main(
                ["--skills-root", str(self.skills_root), *extra_argv]
            )
        return status, stream.getvalue() + errors.getvalue()

    def not_installed_line(self, output: str) -> str:
        """The skills the report says are absent, as one line."""
        return next(
            (line for line in output.splitlines() if "not installed: " in line), ""
        )

    # --- a faithful install ------------------------------------------------

    def test_faithful_install_reports_no_drift(self) -> None:
        self.install()

        status, output = self.run_check()

        self.assertEqual(status, 0)
        self.assertIn("Installed skills match this repository.", output)
        self.assertNotIn("drift", output)

    # --- drift the check exists to catch ------------------------------------

    def test_stale_bundled_review_contract_is_reported(self) -> None:
        """A stale bundled contract is the drift that silently weakens review."""
        installed = self.install(A_SKILL)
        bundled = (
            installed / "references" / "review-suite" / "review-result.schema.json"
        )
        bundled.write_text(
            bundled.read_text(encoding="utf-8").replace('"1.', '"0.', 1),
            encoding="utf-8",
        )

        status, output = self.run_check()

        self.assertEqual(status, 1)
        self.assertIn(f"drift  {A_SKILL}", output)
        self.assertIn(
            "differs: references/review-suite/review-result.schema.json", output
        )
        self.assertIn(f"Installed skills are stale: {A_SKILL}", output)

    def test_same_length_edit_is_reported(self) -> None:
        """Byte comparison, not size comparison: one flipped character is drift."""
        installed = self.install(A_SKILL)
        document = installed / "SKILL.md"
        original = document.read_bytes()
        document.write_bytes(bytes([original[0] ^ 0x20]) + original[1:])
        self.assertEqual(len(document.read_bytes()), len(original))

        status, output = self.run_check()

        self.assertEqual(status, 1)
        self.assertIn("differs: SKILL.md", output)

    def test_absent_bundled_directory_is_reported(self) -> None:
        installed = self.install(ANOTHER_SKILL)
        shutil.rmtree(installed / "references" / "review-suite")

        status, output = self.run_check()

        self.assertEqual(status, 1)
        self.assertIn("missing: references/review-suite/validate.py", output)

    def test_file_only_in_the_installed_copy_is_reported(self) -> None:
        installed = self.install(A_SKILL)
        (installed / "leftover.md").write_text("from an older release\n", "utf-8")

        status, output = self.run_check()

        self.assertEqual(status, 1)
        self.assertIn("extra: leftover.md", output)

    def test_stale_copy_under_another_directory_name_is_reported(self) -> None:
        """A renamed copy still declares its skill, so it still loads and runs."""
        installed = self.install(A_SKILL, as_directory=f"{A_SKILL}-old")
        document = installed / "SKILL.md"
        document.write_text(
            document.read_text(encoding="utf-8") + "\nSTALE RUBRIC\n", encoding="utf-8"
        )

        status, output = self.run_check()

        self.assertEqual(status, 1)
        self.assertIn(f"drift  {A_SKILL}", output)
        self.assertIn(f"installed in directory {A_SKILL}-old", output)
        self.assertNotIn(A_SKILL, self.not_installed_line(output))

    def test_faithful_copy_under_another_directory_name_is_still_reported(self) -> None:
        """The directory name is itself drift: re-installing will not replace it."""
        self.install(A_SKILL, as_directory=f"{A_SKILL}-backup")

        status, output = self.run_check()

        self.assertEqual(status, 1)
        self.assertIn(f"installed in directory {A_SKILL}-backup", output)

    def test_gutted_install_is_reported_rather_than_called_absent(self) -> None:
        installed = self.install(A_SKILL)
        (installed / "SKILL.md").unlink()

        status, output = self.run_check()

        self.assertEqual(status, 1)
        self.assertIn("missing: SKILL.md", output)
        self.assertNotIn(A_SKILL, self.not_installed_line(output))

    # --- failures that must not pass quietly --------------------------------

    def test_skills_root_holding_no_repository_skill_is_not_a_match(self) -> None:
        """The misconfigured-path case must never render as a clean result."""
        foreign = self.skills_root / "some-unrelated-skill"
        foreign.mkdir()
        (foreign / "SKILL.md").write_text("---\nname: unrelated\n---\n", "utf-8")

        status, output = self.run_check()

        self.assertEqual(status, 1)
        self.assertIn("nothing was compared", output)
        self.assertNotIn("Installed skills match this repository.", output)

    def test_named_skills_root_that_does_not_exist_is_an_error(self) -> None:
        self.skills_root = self.skills_root / "typo"

        status, output = self.run_check()

        self.assertEqual(status, 2)
        self.assertIn("is not a directory", output)

    def test_named_skills_root_that_is_a_file_is_an_error(self) -> None:
        target = self.skills_root / "not-a-directory"
        target.write_text("", encoding="utf-8")
        self.skills_root = target

        status, output = self.run_check()

        self.assertEqual(status, 2)
        self.assertIn("is not a directory", output)

    def test_absent_default_skills_root_is_skipped(self) -> None:
        """Continuous integration has no installed distribution to compare."""
        with tempfile.TemporaryDirectory() as home:
            environment = {key: value for key, value in os.environ.items()}
            environment.pop(check_installed_skills.SKILLS_ROOT_ENV, None)
            environment["HOME"] = home
            with unittest.mock.patch.dict(os.environ, environment, clear=True):
                stream = io.StringIO()
                with contextlib.redirect_stdout(stream):
                    status = check_installed_skills.main([])

        self.assertEqual(status, 0)
        self.assertIn("nothing to compare", stream.getvalue())

    def test_unreadable_file_is_reported_and_later_skills_still_compared(self) -> None:
        """One dangling entry must not abort the rest of the run."""
        installed = self.install(A_SKILL)
        self.install(ANOTHER_SKILL)
        document = installed / "SKILL.md"
        document.unlink()
        document.symlink_to(self.skills_root / "does-not-exist")

        status, output = self.run_check()

        self.assertEqual(status, 1)
        self.assertIn("differs: SKILL.md", output)
        self.assertIn(f"ok     {ANOTHER_SKILL}", output)

    def test_unreadable_directory_is_reported_rather_than_skipped(self) -> None:
        installed = self.install(A_SKILL)
        blocked = installed / "references"
        original_mode = blocked.stat().st_mode
        blocked.chmod(0o000)
        self.addCleanup(blocked.chmod, original_mode)
        if os.access(blocked, os.R_OK):  # pragma: no cover - root ignores the mode
            self.skipTest("filesystem does not enforce directory permissions")

        status, output = self.run_check()

        self.assertEqual(status, 1)
        self.assertIn("unreadable:", output)

    # --- what is deliberately not drift -------------------------------------

    def test_runtime_byproducts_are_not_drift(self) -> None:
        """Caches and skill-local state are written at runtime, not distributed."""
        installed = self.install(A_SKILL)
        (installed / "scripts" / "__pycache__").mkdir(parents=True, exist_ok=True)
        (installed / "scripts" / "__pycache__" / "helper.cpython-313.pyc").write_bytes(
            b"\x00"
        )
        (installed / "stray.pyc").write_bytes(b"\x00")
        (installed / ".skill-state").mkdir(exist_ok=True)
        (installed / ".skill-state" / "run.json").write_text("{}", encoding="utf-8")
        (installed / f".{A_SKILL}").mkdir(exist_ok=True)
        (installed / f".{A_SKILL}" / "notes.md").write_text("scratch\n", "utf-8")
        (installed / ".DS_Store").write_bytes(b"\x00")

        status, output = self.run_check()

        self.assertEqual(status, 0)
        self.assertIn("Installed skills match this repository.", output)

    def test_eval_receipts_are_not_drift(self) -> None:
        """`just eval-record` appends receipts that no installed skill reads."""
        installed = self.install(A_SKILL)
        receipts = installed / "evals" / "results"
        receipts.mkdir(parents=True, exist_ok=True)
        (receipts / "2099-01-01T000000Z-0001-baseline.json").write_text("{}", "utf-8")

        status, output = self.run_check()

        self.assertEqual(status, 0)
        self.assertIn("Installed skills match this repository.", output)

    def test_skill_local_ignore_applies_only_at_the_skill_root(self) -> None:
        """The record-keeping convention is a root concern, not a name wildcard."""
        installed = self.install(A_SKILL)
        nested = installed / "references" / f".{A_SKILL}"
        nested.mkdir(parents=True, exist_ok=True)
        (nested / "smuggled.md").write_text("distributed content\n", "utf-8")

        status, output = self.run_check()

        self.assertEqual(status, 1)
        self.assertIn(f"extra: references/.{A_SKILL}/smuggled.md", output)

    def test_symlinked_directory_with_identical_content_is_not_drift(self) -> None:
        installed = self.install(A_SKILL)
        moved = self.skills_root / "elsewhere"
        shutil.move(str(installed / "references"), str(moved))
        (installed / "references").symlink_to(moved, target_is_directory=True)

        status, output = self.run_check()

        self.assertEqual(status, 0)
        self.assertIn("Installed skills match this repository.", output)

    def test_uninstalled_skill_is_named_without_failing(self) -> None:
        """Choosing not to install a skill is not drift in the ones installed."""
        self.install(A_SKILL)

        status, output = self.run_check()

        self.assertEqual(status, 0)
        self.assertIn(f"ok     {A_SKILL}", output)
        self.assertIn("not installed: ", output)
        self.assertIn(ANOTHER_SKILL, self.not_installed_line(output))

    # --- root resolution ----------------------------------------------------

    def test_skills_root_comes_from_the_environment_when_unset(self) -> None:
        self.install()
        with unittest.mock.patch.dict(
            os.environ,
            {check_installed_skills.SKILLS_ROOT_ENV: str(self.skills_root)},
        ):
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                status = check_installed_skills.main([])

        self.assertEqual(status, 0)
        self.assertIn(str(self.skills_root), stream.getvalue())

    def test_named_skills_root_wins_over_the_environment(self) -> None:
        self.install()
        with unittest.mock.patch.dict(
            os.environ,
            {check_installed_skills.SKILLS_ROOT_ENV: "/nonexistent/from/environment"},
        ):
            status, output = self.run_check()

        self.assertEqual(status, 0)
        self.assertIn(str(self.skills_root), output)
        self.assertNotIn("from/environment", output)


if __name__ == "__main__":
    unittest.main()
