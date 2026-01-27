from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import helpers  # noqa: F401  # ensures sys.path is set
from common import DEFAULT_PLAN_PATH, init_plan, load_plan, validate_plan


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
                test_cmd="",
                force=True,
            )
            plan = load_plan(plan_path)
            valid, errors = validate_plan(plan)
            self.assertTrue(valid, f"plan should validate: {errors}")
        finally:
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    unittest.main()
