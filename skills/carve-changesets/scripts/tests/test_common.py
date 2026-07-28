from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import helpers  # noqa: F401  # ensures sys.path is set
from common import DEFAULT_PLAN_PATH, CommandError, init_plan, load_plan, validate_plan


class CommonTests(unittest.TestCase):
    def test_plan_validation_catches_missing_fields(self) -> None:
        valid, errors = validate_plan({"name": "bad"})
        self.assertFalse(valid)
        self.assertTrue(errors)

    def test_init_plan_writes_valid_plan(self) -> None:
        temp_dir = Path(tempfile.mkdtemp(prefix="pcs-test-plan-"))
        try:
            plan_path = temp_dir / DEFAULT_PLAN_PATH
            init_plan(
                plan_path=plan_path,
                base="main",
                source="feature/x",
                title="Title",
                changesets=2,
                test_argv=[],
                force=True,
            )
            plan = load_plan(plan_path)
            valid, errors = validate_plan(plan)
            self.assertTrue(valid, f"plan should validate: {errors}")
            self.assertEqual([], plan["test_argv"])
        finally:
            shutil.rmtree(temp_dir)

    def test_plan_validation_rejects_legacy_test_command_with_migration(self) -> None:
        plan = {
            "feature_title": "Title",
            "base_branch": "main",
            "source_branch": "feature/x",
            "test_command": "just test",
            "changesets": [
                {
                    "slug": "one",
                    "description": "One.",
                    "include_paths": ["a.txt"],
                }
            ],
        }
        valid, errors = validate_plan(plan)
        self.assertFalse(valid)
        self.assertTrue(any("test_argv" in error for error in errors), errors)

    def test_init_plan_rejects_unknown_command_representations(self) -> None:
        invalid_values = ["x", ("python3",), {"python3": "-V"}]
        temp_dir = Path(tempfile.mkdtemp(prefix="pcs-test-plan-"))
        try:
            for index, value in enumerate(invalid_values):
                plan_path = temp_dir / f"plan-{index}.json"
                with self.subTest(value=value):
                    with self.assertRaises(CommandError):
                        init_plan(
                            plan_path=plan_path,
                            base="main",
                            source="feature/x",
                            title="Title",
                            changesets=1,
                            test_argv=value,
                            force=True,
                        )
                    self.assertFalse(plan_path.exists())
        finally:
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    unittest.main()
