# Code-simplicity rubric

Use this rubric after establishing the change contract and chosen solution.
Inspect only the changed code, tests, and immediate collaborators.

## Search before inventing

Search for matching repository primitives by behavior, not only by name:

- shared policy and authorization helpers;
- domain types, validators, normalizers, serializers, and error translators;
- services, repositories, query builders, and extension points;
- test builders, fixtures, assertions, and scenario helpers; and
- already-installed dependencies that own the exact behavior.

Verify semantic fit, including failure behavior and edge cases. Prefer direct
reuse. A wrapper around an existing primitive is a reduction only when it
removes meaningful caller knowledge rather than hiding one call.

## Inspect local complexity

Look for materially repeated:

- business policy or state-transition rules;
- validation, normalization, serialization, and error mapping;
- queries and transaction boundaries;
- multi-pass transformations and intermediate representations;
- recursion or phase machinery for a direct bounded traversal;
- parameters and branches forwarded through thin layers;
- test setup that obscures the behavior under test; and
- hand-written behavior already maintained by a suitable dependency.

Do not report repetition that makes different invariants, failure paths, or
security boundaries explicit.

## Reject complexity relocation

A proposed helper or abstraction must remove concepts from callers and have a
cohesive repository-owned responsibility. Reject it when it merely:

- renames an existing operation;
- forwards the same parameters and branches;
- moves a conditional without centralizing policy;
- introduces a generic API for one use;
- replaces direct code with configuration; or
- forces readers to jump elsewhere to understand an unchanged amount of logic.

## Simplify tests without erasing meaning

Share stable construction and irrelevant defaults. Keep the action and
materially different expectation visible in each test. Preserve separate cases
for different authorization roles, failure modes, boundaries, state transitions,
concurrency interleavings, and public contracts even when their setup looks
similar.

Do not parameterize tests merely to reduce lines if the resulting table hides
which invariant failed.

## Evaluate dependencies

For an installed dependency, cite its manifest entry and matching semantics. For
a new dependency, include maintenance health, security exposure, bundle or
runtime effect, license compatibility, and repository policy. Recommend it only
when those costs are lower than maintaining the bespoke behavior it replaces.

## Measure the reduction

Name the expected reduction using evidence: one policy instead of three, one
pass instead of four, no duplicate representation, two fewer branches, one less
public wrapper, or shared irrelevant setup while preserving explicit scenarios.
Lines may support the explanation but are never the sole measure.

Route a change that replaces the implementation strategy, storage model, service
boundary, or operational design to the whole-solution lens.
