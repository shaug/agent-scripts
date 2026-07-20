# Solution-simplicity rubric

Use this rubric after establishing the ticket's observable contract and the
candidate's complete boundary. Inspect only dimensions that apply.

## Map mechanisms to evidence

For each major mechanism, record both its cost and its justification.

| Mechanism                       | Typical cost                                   | Sufficient justification                                  |
| ------------------------------- | ---------------------------------------------- | --------------------------------------------------------- |
| Service or module boundary      | ownership, calls, failure surface              | repository boundary or distinct lifecycle                 |
| Interface, registry, or plugin  | indirection, configuration, extension contract | multiple real consumers or required public extension      |
| State machine                   | states, transitions, recovery paths            | evidenced lifecycle and illegal-transition protection     |
| Queue, retry, or reconciler     | delivery semantics, operations, observability  | real asynchronous or partial-failure behavior             |
| Cache or duplicate store        | invalidation, consistency, repair              | measured need or required availability boundary           |
| Migration or compatibility path | dual behavior, cleanup, rollout burden         | existing data, callers, or explicit compatibility promise |
| Configuration or feature flag   | combinations, ownership, retirement            | documented rollout or user-selectable behavior            |
| Generic framework               | concepts and future maintenance                | more than one current use or explicit platform goal       |

Do not treat an unsupported mechanism as unnecessary until the repository's
instructions, named design documents, nearby patterns, and operational context
have been checked.

## Look for disproportionate machinery

Ask whether the candidate introduces:

- an abstraction with one speculative consumer;
- a generic framework for one narrow operation;
- compatibility handling for callers or data that do not exist;
- a pre-release migration or backfill with no historical state;
- extension points or configuration without a stated need;
- retry, reconciliation, or state beyond the evidenced failure model;
- another source of truth for a future possibility;
- custom infrastructure where an established repository primitive already meets
  the contract;
- indirection that moves complexity without removing it; or
- platform work embedded in a PR-sized feature.

These are investigation prompts. A finding still needs a smaller,
requirement-complete alternative.

## Protect required complexity

Preserve machinery that enforces:

- ordering, uniqueness, atomicity, or fencing;
- concurrency safety and idempotency;
- authentication, authorization, or data protection;
- partial-failure handling, bounded retry, cancellation, or recovery;
- migration of real schema or persisted data;
- documented public compatibility;
- required rollout controls and observability; or
- a demonstrated repository architecture boundary.

Do not replace explicit safety semantics with an informal sequence of operations
or assume success-only behavior.

## Construct the smaller alternative

A sufficient alternative names the concrete repository primitive or direct flow,
identifies which candidate mechanisms disappear, preserves every acceptance
criterion and invariant, and explains its failure behavior. Reject an
alternative that depends on a new unstated assumption.

Measure the reduction in human and operational terms: fewer concepts, states,
branches, owners, configuration combinations, migration phases, failure modes,
or sources of truth. Fewer lines alone are not evidence.

## Choose severity

- `blocking`: the unsupported design breaches explicit scope or architecture, or
  creates a demonstrated correctness or operational hazard.
- `strong_recommendation`: the candidate works, but a tractable alternative
  removes material unjustified machinery while preserving the contract.
- `defer`: the concern is real but belongs to another ticket or awaits a named
  decision.

If a product, architecture, compatibility, data, or operational decision is
required to know which design is sufficient, return `blocked` instead of
inventing the answer.
