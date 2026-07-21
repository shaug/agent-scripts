# Review-code-change evaluations

- `cases.json` + `expectations.json`: orchestration scenario contract data
  consumed by `scripts/tests/test_orchestration_contract.py`.
- `standalone-clean/`: raw forward-evaluation inputs for a full suite run. The
  expected outcome lives in `expected/standalone-clean.result.json`, outside the
  input directory, so a forward-testing reviewer pointed at the input directory
  cannot read the answer key.
