# Correctness review rubric

Use only the dimensions applicable to the candidate. Begin with its stated goal
and repository evidence; never turn this reference into a generic checklist
report.

## Goal and behavior

- Trace each acceptance criterion to observable implementation and evidence.
- Check logic, state transitions, boundary values, empty states, ordering,
  pagination, precision, timezones, and encoding where relevant.
- Verify named preserved behavior and detect regressions outside the happy path.
- Distinguish a real requirement from behavior imagined by the implementation.

## Security and authorization

- Verify authentication and authorization at the actual trust boundary.
- Check input validation, injection paths, path traversal, unsafe serialization,
  secret handling, and unintended data exposure.
- Check tenant, organization, role, ownership, and field-level access rules.
- Treat a demonstrated privilege expansion or missing trust-boundary check as
  blocking.

Do not request generalized hardening without a reachable current risk.

## Failure and data integrity

- Follow error propagation, cleanup, partial failure, and recovery behavior.
- Check transactions, consistency boundaries, retries, idempotency, duplicate
  delivery, cancellation, timeouts, and races when the change participates in
  them.
- Verify atomicity and fencing requirements before proposing simpler control
  flow.
- Check resource ownership and cleanup for files, connections, locks, streams,
  and background work.

## Repository architecture and compatibility

- Read applicable agent instructions (`AGENTS.md`, `CLAUDE.md`, or equivalent),
  contributor guidance, named designs, and public contracts before judging
  architecture or idioms.
- Inspect representative nearby code and tests for actual extension points,
  module boundaries, error handling, naming, and test conventions.
- Check public APIs, schemas, migrations, serialization, compatibility, and
  rollout behavior explicitly required by the ticket or repository.
- Prefer local evidence over generic SOLID, design-pattern, function-length, or
  cyclomatic-complexity rules.

Do not invent legacy consumers, migration requirements, or compatibility
promises.

## Tests and validation

- Require evidence for success, relevant failure paths, regressions, and named
  preserved behavior.
- Detect assertions that do not exercise the changed behavior, mocks that bypass
  the risk, and passing suites that omit a required boundary.
- Treat missing required validation, unexplained unavailable commands, and
  contradictory test evidence according to the shared blocked and finding
  semantics.
- Do not demand redundant tests when existing coverage or repository convention
  already proves the behavior.

## Performance and operations

- Report only plausible material regressions such as obvious N+1 work, unbounded
  processing, blocking operations on a critical path, leaked resources, or a
  documented capacity violation.
- Tie operational findings to current ordering, latency, memory, retry, or
  availability requirements.
- Do not recommend caching, parallelism, indexing, batching, or new dependencies
  speculatively.

## False-positive controls

Omit a concern when:

- repository instructions or a named contract explicitly establish the candidate
  behavior;
- representative nearby code uses the same pattern for the same boundary;
- existing tests already prove the claimed missing behavior;
- the impact is aesthetic, hypothetical, or outside any current requirement;
- the proposed correction merely substitutes a preferred pattern; or
- the concern belongs exclusively to solution-simplicity or code-simplicity
  review without a demonstrated correctness consequence.
