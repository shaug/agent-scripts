# Carve-changesets evaluations

`cases.json` contains peer-shaped behavioral scenarios. `expectations.json`
keeps their terminal states and action obligations separate so an evaluated
runtime never receives grader answers or fixture identities. The runner sends
one JSON packet on stdin to a fresh `--executor` process for each case and
expects one JSON object on stdout.

The bundled `fixture_executor.py` is a deterministic simulation used to test the
harness and contract plumbing. It is not a model evaluation. A compatible agent
adapter can be supplied with:

```bash
python3 scripts/evals/runner.py --executor "python3 /path/to/adapter.py"
```

`integration_cases.json` replaces the former mechanics-only prompt CSV. Run it
with `scripts/evals/runner.py --integration-self-test`. That mode directly
exercises the real helpers and retains the deterministic grader as an objective
validation layer: it checks a clean tree, plan validity, source-hash
immutability, complete chain materialization, reconstructed-tree equivalence,
and approved prefix validation. It does not evaluate agent judgment.

`just eval-carve-changesets` runs both the integration self-test and the
result-blind forward cases without requiring any particular agent CLI.
