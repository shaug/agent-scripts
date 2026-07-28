# Implement-epic evaluations

`cases.json` describes scenario inputs and `expectations.json` records the
required terminal state and actions for each case. The general pair is consumed
by `scripts/tests/test_orchestration_contract.py` as contract data and can be
replayed manually or through a compatible headless agent harness. Dependency
provenance cases are also mirrored into the shared fresh-process forward corpus;
run them with `just eval-implement-epic`. Give an evaluated agent only scenario
inputs; never show it expectations.
