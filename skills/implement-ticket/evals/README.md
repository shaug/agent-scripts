# Implement-ticket evaluations

- `cases.json` + `expectations.json`: scenario contract data consumed by
  `scripts/tests/test_implement_ticket_contract.py`.
- `forward_cases.json` + `forward_expectations.json`: result-blind forward
  evaluations executed by `scripts/evals/run_forward.py`. Case artifacts carry
  pre-classified scenario flags (`whole_epic`, CI `classification`,
  `base_drift`, and similar), so grading covers obligation mapping and
  terminal-state selection rather than evidence classification. The default
  executor (`scripts/evals/fixture_executor.py`) is a deterministic simulation
  of a compliant runtime, not a model; pass `--executor` to grade a real agent
  runtime such as `scripts/evals/claude_executor.py`. Every expectation defines
  `forbidden_actions`, so emitting the whole action vocabulary fails.

Give an evaluated agent only the case artifacts; never show it any expectations
file.
