# Validation evidence

- Focused: `pytest tests/test_webhooks.py` passed, 4 tests. The added test
  checks that a first delivery records `received_at`.
- Full: `pytest` passed, 37 tests.

The candidate diff is complete. The test commands did not modify tracked files.
