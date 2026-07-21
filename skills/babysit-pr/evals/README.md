# Babysit-pr evaluations

`cases.json` describes scenario inputs and `expectations.json` records the
required terminal state and actions for each case. There is no automated runner
yet; the pair is consumed by `scripts/tests/test_skill_contract.py` as contract
data and can be replayed manually or through a compatible headless agent
harness. Give an evaluated agent only `cases.json` entries; never show it
`expectations.json`.
