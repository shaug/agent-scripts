# Orchestration protocol

This protocol owns sequencing and aggregation only. The shared contract owns
packet and result semantics; each lens skill owns its review rubric.

## Prepare and validate evidence

Resolve the live ticket or PR before reading the implementation. Separate
explicit requirements from inferred context and record non-goals and invariants.
Read applicable repository instructions and named specifications, then capture
the complete diff, exact candidate identity, representative nearby code and
tests, validation evidence, and worktree state.

Run the shared packet validator. Do not invoke a lens with a malformed packet.
Do not repair missing intent by reading the implementation transcript.

## Sequence decisions

Use this decision table after validating each lens result.

| Current result                                | Next action                                                          |
| --------------------------------------------- | -------------------------------------------------------------------- |
| solution `blocked`                            | aggregate `blocked`; stop                                            |
| solution requires strategy replacement        | aggregate findings; caller redesigns; stop                           |
| solution has a tractable in-strategy proposal | run correctness                                                      |
| solution `clean`                              | run correctness                                                      |
| correctness `blocked`                         | aggregate `blocked`; stop                                            |
| correctness has a gating finding              | aggregate findings; caller fixes; stop                               |
| correctness `clean`                           | run code simplicity                                                  |
| code simplicity `blocked`                     | aggregate `blocked`; stop                                            |
| code simplicity has a gating finding          | aggregate findings; caller fixes, then rechecks code and correctness |
| all required results `clean`                  | aggregate `clean`; stop                                              |

A solution result requires strategy replacement when its proposed change
replaces major mechanisms, ownership boundaries, storage, state, or operational
design and its next action calls for redesign or a full restart. Do not infer
early exit merely from finding count. A bounded local removal can proceed to
correctness.

For a tractable gating proposal, pass the validated simplification result beside
the unchanged packet when invoking correctness. Do not merge it into the packet.
Require correctness to return one shared proposal disposition for every supplied
gating finding. A missing or mismatched disposition makes the lens result
untrustworthy and therefore `blocked`.

## Validate lens results

For every result:

- validate it against the shared result schema and cross-field semantics;
- require the expected lens name;
- require the packet's exact head and comparison-base identity for clean and
  changes-required results;
- reject stale, malformed, or mismatched results as `blocked`; and
- retain explicit validation limitations.
- when simplification proposals were supplied to correctness, require exactly
  one disposition for each supplied gating finding and no unknown finding IDs.

## Deduplicate root causes

Cluster findings only when concrete evidence shows the same root cause and
smallest sufficient correction. Similar location or wording alone is not enough.
Use stable IDs and `related_finding_ids` to retain the contributing identities.

For a true duplicate:

1. Keep one finding owned by the lens with the controlling concern: correctness,
   then solution simplicity, then code simplicity.
2. Retain unique evidence from every contributing lens.
3. Preserve the highest supported severity and confidence.
4. State the smallest correction that satisfies the controlling constraint.
5. List the other stable IDs in `related_finding_ids`.

Keep separate findings when their corrections or material impacts differ.

## Resolve conflicts

When a simplification proposal conflicts with demonstrated correctness,
security, compatibility, migration, concurrency, or repository constraints:

- require correctness to mark the proposal `unsafe` with concrete evidence;
- omit the rejected simplification finding from the aggregate findings;
- preserve the disposition in the aggregate; and
- do not create a correctness finding unless the current candidate itself has a
  demonstrated defect.

When correctness marks a proposal `compatible`, keep the simplification finding
actionable in the aggregate. A proposal disposition does not erase an unrelated
correctness finding.

Do not downgrade a correctness finding because a different design might avoid
it. A caller may choose a redesign, but that begins a new full review on a new
head.

## Aggregate verdicts

- `blocked` wins when evidence, dependencies, candidate identity, or any
  required lens is untrustworthy.
- Otherwise, `changes_required` wins when a blocking or strong-recommendation
  finding remains.
- Otherwise, return `clean`, including any real deferred findings.

Deferred-only results are clean because deferred findings do not gate the
candidate. Never erase their evidence or silently promote them into the active
scope.

## Re-review matrix

| Change applied by caller | New-head sequence                                           |
| ------------------------ | ----------------------------------------------------------- |
| solution redesign        | solution, correctness, code                                 |
| correctness fix          | correctness, then affected downstream lenses                |
| code-simplicity fix      | code, then targeted correctness                             |
| base-only drift          | apply shared drift rules, then reset only affected evidence |

Count a full cycle when a candidate reaches a material finding and the caller
supplies a new head for another full or required downstream pass. At cycle
three, return unresolved findings and tell the caller that the automatic cycle
budget is exhausted.

## Preserve read-only operation

Record candidate state before delegation and verify it afterward. Treat an
unexpected modification by any delegated lens as an integrity failure and return
`blocked`. The caller owns all changes and external workflow actions.
