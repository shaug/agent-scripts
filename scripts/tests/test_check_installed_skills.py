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
        self.fresh_skills_root()

    def fresh_skills_root(self) -> None:
        """Allocate an empty installed-skills directory for one scenario."""
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.skills_root = Path(directory.name)

    def write_skill(self, directory: Path, declared: str, body: str = "") -> Path:
        """A minimal skill folder, for cases the real `skills/` cannot express."""
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "SKILL.md").write_text(
            f"---\nname: {declared}\n---\n{body}", encoding="utf-8"
        )
        return directory

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

    def test_a_stray_copy_is_told_to_be_removed_not_re_installed(self) -> None:
        """Re-installing writes `<root>/<skill>`, so it never clears a stray copy."""
        stray = self.install(A_SKILL, as_directory=f"{A_SKILL}-backup")

        status, output = self.run_check()

        self.assertEqual(status, 1)
        self.assertIn(
            "Re-installing cannot clear a copy under another directory", output
        )
        self.assertIn(str(stray), output)

    def test_removal_advice_never_names_another_skills_install_directory(self) -> None:
        """The one destructive instruction must not undo a re-install.

        A directory matches on its declared name as well as its own, so one
        directory can be attributed to two skills. If it is where a re-install
        writes some other skill, telling the operator to delete it uninstalls
        that skill one line after installing it.
        """
        repository = self.skills_root / "repository"
        self.write_skill(repository / "skills" / "alpha", "alpha")
        self.write_skill(repository / "skills" / "beta", "beta")

        installed_root = self.skills_root / "installed"
        # `<root>/beta` is where re-installing `beta` lands, and it declares
        # `alpha`, so it is matched as a stray copy of `alpha` as well.
        self.write_skill(installed_root / "beta", "alpha")

        report = check_installed_skills.compare(repository, installed_root)
        output = check_installed_skills.render(report)

        self.assertIn("drift  alpha", output)
        self.assertNotIn(str(installed_root / "beta"), output.split("Remove:")[-1])

    def test_removal_advice_compares_directories_by_identity_not_by_path(self) -> None:
        """The guard has to hold wherever one directory has two unequal paths.

        A symlink to the canonical directory is that case on every filesystem,
        so this pins the guard where continuous integration runs. The
        case-folding test below is the same defect's real-world trigger, but it
        can only run where the filesystem folds case.
        """
        self.install(A_SKILL)
        stray = self.skills_root / f"{A_SKILL}-old"
        stray.symlink_to(self.skills_root / A_SKILL, target_is_directory=True)

        status, output = self.run_check()

        self.assertEqual(status, 1)
        self.assertNotIn("Remove:", output)

    def test_removal_advice_survives_a_case_insensitive_filesystem(self) -> None:
        """The default skills root lives on one, where two names are one directory."""
        installed = self.install(A_SKILL, as_directory=A_SKILL.title())
        canonical = self.skills_root / A_SKILL
        if not canonical.is_dir() or not installed.samefile(canonical):
            self.skipTest("filesystem is case-sensitive")

        status, output = self.run_check()

        self.assertEqual(status, 1)
        self.assertNotIn("Remove:", output)

    def test_content_after_the_frontmatter_is_not_the_declared_name(self) -> None:
        """Reading past the closing fence would let prose rename a copy."""
        repository = self.skills_root / "repository"
        self.write_skill(repository / "skills" / "alpha", "alpha")

        installed_root = self.skills_root / "installed"
        stray = installed_root / "zzz"
        stray.mkdir(parents=True)
        (stray / "SKILL.md").write_text(
            "---\nname: unrelated\n---\n\nname: alpha\n", encoding="utf-8"
        )

        report = check_installed_skills.compare(repository, installed_root)

        self.assertEqual(report.compared, [])
        self.assertEqual(report.not_installed, ["alpha"])

    def test_a_duplicated_name_key_resolves_the_way_a_loader_resolves_it(self) -> None:
        """Last wins, so this check and the runtime agree on what is declared."""
        repository = self.skills_root / "repository"
        self.write_skill(repository / "skills" / "alpha", "alpha")

        installed_root = self.skills_root / "installed"
        stray = installed_root / "zzz"
        stray.mkdir(parents=True)
        (stray / "SKILL.md").write_text(
            "---\nname: something-else\nname: alpha\n---\n", encoding="utf-8"
        )

        report = check_installed_skills.compare(repository, installed_root)

        self.assertEqual([comparison.name for comparison in report.compared], ["alpha"])
        self.assertEqual(report.not_installed, [])

    def test_a_second_link_to_one_directory_still_contributes_its_content(self) -> None:
        """Descending once per real directory must not drop what a path exposes."""
        installed = self.install(A_SKILL)
        shared = self.skills_root / "shared"
        shared.mkdir()
        (shared / "leftover.md").write_text("from an older release\n", "utf-8")
        (installed / "one").symlink_to(shared, target_is_directory=True)
        (installed / "two").symlink_to(shared, target_is_directory=True)

        status, output = self.run_check()

        self.assertEqual(status, 1)
        self.assertIn("extra: one/leftover.md", output)
        self.assertIn("extra: two/leftover.md", output)

    def test_renamed_copy_is_found_whatever_its_frontmatter_looks_like(self) -> None:
        """Matching must not hinge on one spelling of the declared name.

        A copy under another directory name is found by what its `SKILL.md`
        declares, so every frontmatter shape a real skill might carry has to
        reach the same verdict as the plain unquoted one.
        """
        for declaration in (
            f"name: {A_SKILL}",
            f'name: "{A_SKILL}"',
            f"name: '{A_SKILL}'",
            f"name: {A_SKILL}  # canonical",
            f"name:    {A_SKILL}",
        ):
            with self.subTest(declaration=declaration):
                self.fresh_skills_root()
                installed = self.install(A_SKILL, as_directory=f"{A_SKILL}-old")
                document = installed / "SKILL.md"
                body = document.read_text(encoding="utf-8").splitlines()
                # Pinned: replacing a line that is not the declaration would
                # leave the original in place and test a two-`name:` document.
                self.assertTrue(body[1].startswith("name:"), body[1])
                body[1] = declaration
                document.write_text(
                    "\n".join(body) + "\nSTALE RUBRIC\n", encoding="utf-8"
                )

                status, output = self.run_check()

                self.assertEqual(status, 1)
                self.assertIn(f"drift  {A_SKILL}", output)
                self.assertNotIn(A_SKILL, self.not_installed_line(output))

    def test_unparsable_frontmatter_still_matches_on_the_directory_name(self) -> None:
        """A frontmatter this check cannot read must not hide an installed copy."""
        installed = self.install(A_SKILL)
        document = installed / "SKILL.md"
        document.write_text("no frontmatter at all\n", encoding="utf-8")

        status, output = self.run_check()

        self.assertEqual(status, 1)
        self.assertIn("differs: SKILL.md", output)
        self.assertNotIn(A_SKILL, self.not_installed_line(output))

    def test_a_name_inside_a_block_scalar_is_not_the_declared_name(self) -> None:
        """An indented `name:` belongs to the value it sits in, not the document."""
        stray = self.skills_root / "unrelated"
        stray.mkdir()
        (stray / "SKILL.md").write_text(
            f"---\nname: unrelated\ndescription: |\n  name: {A_SKILL}\n---\n",
            encoding="utf-8",
        )
        self.install(A_SKILL)

        status, output = self.run_check()

        self.assertEqual(status, 0)
        self.assertIn(f"ok     {A_SKILL}", output)

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

        self.assertEqual(status, 2)
        self.assertIn("nothing was compared", output)
        self.assertNotIn("Installed skills match this repository.", output)

    def test_unreadable_repository_source_invalidates_the_run(self) -> None:
        """A source that cannot be enumerated says nothing about a copy of it.

        Reporting it as installed-copy drift would print remediation that
        overwrites good installed files with a truncated source.
        """
        repository = self.skills_root / "repository"
        source = repository / "skills" / "demo"
        (source / "references").mkdir(parents=True)
        (source / "SKILL.md").write_text("---\nname: demo\n---\n", encoding="utf-8")
        (source / "references" / "rubric.md").write_text("rubric\n", encoding="utf-8")

        installed_root = self.skills_root / "installed"
        shutil.copytree(source, installed_root / "demo")

        blocked = source / "references"
        original_mode = blocked.stat().st_mode
        blocked.chmod(0o000)
        self.addCleanup(blocked.chmod, original_mode)
        if os.access(blocked, os.R_OK):  # pragma: no cover - root ignores the mode
            self.skipTest("filesystem does not enforce directory permissions")

        report = check_installed_skills.compare(repository, installed_root)
        output = check_installed_skills.render(report)

        self.assertIn("could not be read in full", output)
        self.assertIn(f"unreadable: {blocked}", output)
        self.assertNotIn("skills update", output)
        self.assertNotIn("extra:", output)
        self.assertEqual(
            check_installed_skills.exit_code(report),
            check_installed_skills.EXIT_MISCONFIGURED,
        )

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
