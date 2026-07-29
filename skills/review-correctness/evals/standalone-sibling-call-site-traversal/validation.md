# Validation evidence

- Focused: `pytest tests/test_policy.py` passed, 5 tests. The suite checks
  `check_dependency` under both `mode="strict"` and `mode="permissive"`.
- Full: `pytest` passed, 52 tests.

The candidate diff is complete. The test commands did not modify tracked files.
