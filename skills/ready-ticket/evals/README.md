# Ready-ticket evaluations

`cases.json` holds scenario inputs and `expectations.json` records the required
terminal result and actions for each case. The pair is consumed by
`scripts/tests/test_authoring_contract.py` as contract data and can be replayed
manually or through a compatible headless agent harness. Give an evaluated agent
only the scenario inputs; never show it the expectations.

Every case is result-blind: no case carries a `workflow_state` or a
`required_actions` field, and no case narrates the outcome its scenario is meant
to produce. The four terminal results — `ticket_ready`, `draft_ready`,
`decomposition_recommended`, and `blocked` — are each covered, and the contract
test fails if the expectation set ever drifts from exactly those four.

## What is not here yet

These fixtures pin the contract; they are not a pressure test. This skill was
authored without a recorded baseline, so the rationalization table in `SKILL.md`
carries anticipated wording rather than verbatim wording an agent produced, and
it is marked as such. Establishing the baseline, replacing that wording, and
running the before/after comparison belong to
[issue #137](https://github.com/shaug/agent-scripts/issues/137), which
pressure-tests this skill from baseline.
