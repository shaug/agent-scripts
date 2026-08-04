from __future__ import annotations

import contextlib
import importlib.util
import io
import json
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

DISTRIBUTION_EXCLUSIONS = shutil.ignore_patterns(
    "__pycache__", "*.pyc", ".skill-state", ".DS_Store"
)


class CheckInstalledSkillsTests(unittest.TestCase):
    """The command's observable contract: what it prints and what it exits."""

    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.skills_root = Path(directory.name)

    def install(self, *skills: str) -> None:
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
        for source in sources:
            shutil.copytree(
                source, self.skills_root / source.name, ignore=DISTRIBUTION_EXCLUSIONS
            )

    def run_check(self, *extra_argv: str) -> tuple[int, str]:
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            status = check_installed_skills.main(
                ["--skills-root", str(self.skills_root), *extra_argv]
            )
        return status, stream.getvalue()

    def test_faithful_install_reports_no_drift(self) -> None:
        self.install()

        status, output = self.run_check()

        self.assertEqual(status, 0)
        self.assertIn("Installed skills match this repository.", output)
        self.assertNotIn("drift", output)

    def test_stale_bundled_review_contract_is_reported(self) -> None:
        """A stale bundled contract is the drift that silently weakens review."""
        self.install()
        bundled = (
            self.skills_root
            / "review-correctness"
            / "references"
            / "review-suite"
            / "review-result.schema.json"
        )
        schema = json.loads(bundled.read_text(encoding="utf-8"))
        schema["properties"]["schema_version"] = {"const": "1.0"}
        schema["properties"].pop("lens_executions", None)
        bundled.write_text(json.dumps(schema), encoding="utf-8")

        status, output = self.run_check()

        self.assertEqual(status, 1)
        self.assertIn("drift  review-correctness", output)
        self.assertIn(
            "differs: references/review-suite/review-result.schema.json", output
        )
        self.assertIn("Installed skills are stale: review-correctness", output)

    def test_stale_skill_prose_is_reported(self) -> None:
        """A dropped required section is drift even when every file is present."""
        self.install()
        skill_document = self.skills_root / "review-correctness" / "SKILL.md"
        body = skill_document.read_text(encoding="utf-8")
        skill_document.write_text(
            body.replace("## Perform the required traversal pass", ""), encoding="utf-8"
        )

        status, output = self.run_check()

        self.assertEqual(status, 1)
        self.assertIn("differs: SKILL.md", output)

    def test_absent_bundled_directory_is_reported(self) -> None:
        self.install()
        shutil.rmtree(
            self.skills_root / "review-code-change" / "references" / "review-suite"
        )

        status, output = self.run_check()

        self.assertEqual(status, 1)
        self.assertIn("missing: references/review-suite/validate.py", output)

    def test_file_only_in_the_installed_copy_is_reported(self) -> None:
        self.install()
        (self.skills_root / "review-correctness" / "leftover.md").write_text(
            "from an older release\n", encoding="utf-8"
        )

        status, output = self.run_check()

        self.assertEqual(status, 1)
        self.assertIn("extra: leftover.md", output)

    def test_runtime_byproducts_are_not_drift(self) -> None:
        """Caches and skill-local state are written at runtime, not distributed."""
        self.install()
        installed = self.skills_root / "review-correctness"
        (installed / "scripts" / "__pycache__").mkdir(parents=True, exist_ok=True)
        (installed / "scripts" / "__pycache__" / "helper.cpython-313.pyc").write_bytes(
            b"\x00"
        )
        (installed / ".skill-state").mkdir(exist_ok=True)
        (installed / ".skill-state" / "run.json").write_text("{}", encoding="utf-8")
        (installed / ".review-correctness").mkdir(exist_ok=True)
        (installed / ".review-correctness" / "notes.md").write_text(
            "scratch\n", encoding="utf-8"
        )
        (installed / ".DS_Store").write_bytes(b"\x00")

        status, output = self.run_check()

        self.assertEqual(status, 0)
        self.assertIn("Installed skills match this repository.", output)

    def test_uninstalled_skill_is_named_without_failing(self) -> None:
        """Choosing not to install a skill is not drift in the ones installed."""
        self.install("review-correctness")

        status, output = self.run_check()

        self.assertEqual(status, 0)
        self.assertIn("ok     review-correctness", output)
        self.assertIn("not installed: ", output)
        self.assertIn("babysit-pr", output.split("not installed: ")[1])

    def test_absent_skills_root_is_skipped(self) -> None:
        """Continuous integration has no installed distribution to compare."""
        self.skills_root = self.skills_root / "nonexistent"

        status, output = self.run_check()

        self.assertEqual(status, 0)
        self.assertIn("nothing to compare", output)

    def test_skills_root_comes_from_the_environment_when_unset(self) -> None:
        self.install()
        with unittest.mock.patch.dict(
            "os.environ",
            {check_installed_skills.SKILLS_ROOT_ENV: str(self.skills_root)},
        ):
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                status = check_installed_skills.main([])

        self.assertEqual(status, 0)
        self.assertIn(str(self.skills_root), stream.getvalue())


if __name__ == "__main__":
    unittest.main()
