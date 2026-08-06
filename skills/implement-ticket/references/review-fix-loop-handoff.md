# Review-fix-loop handoff and result mapping

Use repository-owned `review-fix-loop` as the sole canonical owner of the
initial candidate's review, finding disposition, fix authorship orchestration,
re-review, and convergence detection. Read its live skill,
[`references/CONTRACT.md`](../../review-fix-loop/references/CONTRACT.md), and
[`references/local-commit.md`](../../review-fix-loop/references/local-commit.md)
before delegation. If its delivered contract differs materially from this
boundary, stop and reconcile ownership rather than copying loop mechanics back
into `implement-ticket`.

This reference applies only to the initial candidate, before any publication
path is selected, and always under `publication.policy: local_commit` —
`review-fix-loop` never pushes on this skill's behalf. `babysit-pr`'s
post-publication remediation loop and `carve-changesets`'s per-changeset review
are separate, unmigrated consumers of repository-owned `review-code-change`;
this handoff does not apply to either.

## Responsibility boundary

`implement-ticket` retains ticket resolution and readiness, epic routing,
exclusive implementation state, the initial implementation, the change
contract's authored content (goal, acceptance criteria, non-goals, preserved
behaviors, allowed remediation scope), the validation commands it approves,
invocation construction, host-port implementation (see below), terminal-result
validation, publication-path selection, handoff to `babysit-pr` or
`carve-changesets`, tracker transition, cleanup, and final reporting.

After delegation, `review-fix-loop` owns the local candidate lock, reviewer
isolation and integrity enforcement, raw `review-code-change` packet
construction and binding, finding selection and ordering, fix-cycle budget
accounting, validated commit and fast-forward promotion of every accepted fix,
evidence invalidation after each new head, convergence detection, and its own
durable checkpoint and terminal result. Do not reproduce those mechanics in this
skill.

## Pre-mutation dependency gate

Verify `review-fix-loop` and `babysit-pr` by stable repository-owned name before
creating a branch or worktree. Missing `review-fix-loop` returns `blocked`
before mutation. `review-fix-loop`'s own dependency gate covers
`review-code-change` and its three lenses; do not additionally require or
substitute a direct `review-code-change` binding at this gate, and do not
download an external implementation at runtime, restore a private inlined fix
loop, or accept an unreviewed candidate as ready.

## Constructing the invocation

Immediately before delegation, capture the exact committed head, comparison
base, complete `base...HEAD` diff, and tracked/staged/unstaged/untracked/ignored
worktree state, exactly as this skill has always required before review. The
worktree must be globally clean and every intended change committed —
`review-fix-loop`'s own invocation schema rejects anything else. If the exact
diff is captured to a file for the invocation to reference, write it outside the
ticket worktree: a file inside the tracked worktree would appear as a candidate
mutation to `review-fix-loop`'s own before/after integrity checks around each
reviewer pass.

Map that evidence onto one `review-fix-loop` invocation:

- `candidate`: the exact branch, head SHA, comparison base, diff, and worktree
  state above, with `all_changes_committed: true`. No PR exists yet at this
  point in the workflow, so record `source_unavailable_reason` rather than a
  `source_binding` — this delegation never needs publication authority.
- `change_contract`: the ticket's observable goal, every acceptance criterion
  and required verification item, explicit non-goals, behavior to preserve,
  named architecture/design/contract/migration/rollout documents, and
  representative nearby code and tests, exactly as this skill has always
  assembled them. Set `allowed_remediation_scope` to the ticket-scoped edit
  boundary [step 2](../SKILL.md#2-implement-only-the-live-contract) already
  enforces — a fix cycle may not expand past it.
- `review_execution.mode`: `fresh_subagent` by default, matching this skill's
  existing fresh read-only review requirement. Use `in_agent_override` only
  through an explicit current-user or caller-authorized override recorded before
  delegation; there is no automatic fallback.
- `fix_cycle_budget.max_fix_cycles`: `3`, matching this skill's existing
  three-cycle norm. This is a distinct budget from `review-code-change`'s own
  three-cycle lens-sequence retry budget; neither touches the other.
- `validation`: this ticket's separately approved focused and full commands.
- `publication.policy`: always `local_commit`. Never supply
  `publication.pull_request` or `remote_iteration_grants` here — no PR exists
  yet, and this skill still withholds the first remote push until
  [step 5](../SKILL.md#5-choose-exactly-one-publication-path) selects the
  publication path.

Author the change contract's goal, acceptance criteria, non-goals, and preserved
behaviors as neutral evidence, never as a pre-judged verdict —
`review-fix-loop`'s `reviewer` port passes them straight into its own
`review-code-change` packet, so steering language here steers that review
exactly as it would have before delegation.

## Host ports remain caller-owned

`review-fix-loop`'s engine is dependency-free: it cannot itself spawn a review
subagent, write a fix's content, or judge whether a finding is genuinely
tractable and in scope. Supply its `reviewer`, `decide`, `apply_fix`, and
validation ports yourself, exactly as
[`local-commit.md`](../../review-fix-loop/references/local-commit.md)'s "Host
boundary: the three ports" section describes:

- **`reviewer`**: spawn a fresh read-only context restricted to
  `Read, Grep, Glob, Bash, Agent, Task, Skill` that invokes repository-owned
  `review-code-change` with raw candidate evidence only — excluding the
  implementation transcript, intended solution, prior conclusions, and suspected
  findings, exactly as this skill has always required. Give the review a
  capability tier adequate for judgment: it inherits the session's tier by
  default, and a review that missed a defect a later cycle surfaces escalates
  one tier instead of rerunning identically.
- **`decide`**: apply
  [the consumption disciplines](review-suite/consumption-disciplines.md) to
  every finding `review-fix-loop` selects — verify it against the codebase
  before implementing it, clarify every unclear finding before implementing any,
  never perform agreement, and accept only a finding that is material and within
  `change_contract.allowed_remediation_scope`. `review-fix-loop`'s own finding
  selection and validate-and-commit sequence already implement blocking before
  simple before complex, validating each fix on its own before the next review —
  the `decide` port does not reorder or re-validate on its own. A finding whose
  correct fix would exceed that scope is not implement-ticket's to quarantine
  and defer inline anymore: return `expands_scope` and let `review-fix-loop`
  stop as `blocked/scope_decision_required`, surfacing it for the caller to
  disposition immediately rather than deferring it to a terminal-result
  quarantine list.
- **`apply_fix`**: implement the smallest coherent accepted remediation,
  applying [step 2](../SKILL.md#2-implement-only-the-live-contract)'s
  discipline. When this port is about to consume the invocation's last remaining
  fix cycle, replace the incumbent implementer rather than continuing it:
  dispatch a fresh context one capability tier above the incumbent's, or a fresh
  context at the same tier when no higher tier is available, briefed with the
  surviving finding and a summary of what prior attempts tried and why they
  failed, not the full implementation transcript. This is a caller-supplied
  policy layered onto the port — `review-fix-loop`'s own engine has no
  escalation mechanic and needs none for this to work. When a fix fails
  repeatedly and `superpowers:systematic-debugging` is available in the session
  skill listing, load it as the escalated implementer's recommended diagnosis
  method; when the peer is not in the listing, the escalated implementer
  diagnoses from logs and evidence without comment.
- **validation ports**: run this ticket's separately approved focused and full
  validation commands and classify a candidate-attributable failure as tractable
  remediation input exactly as [step 3](../SKILL.md#3-validate-in-layers)
  already requires.

## Resuming an interrupted or piecemeal invocation

`review-fix-loop` resumes from live repository and checkpoint state without
requiring an uninterrupted implementation transcript. Before constructing a new
invocation, check for an existing durable checkpoint under this candidate's
`.review-fix-loop/` directory:

- If one exists for this exact repository, branch, and candidate identity,
  reconcile and resume it rather than starting a fresh invocation. A resumed
  invocation keeps its original `invocation_id` and fix-cycle budget; do not
  reset consumed-cycle accounting or duplicate an already-committed fix. A
  reconciliation failure (an active lock holder, a dirty candidate, or live
  head/base that cannot be reconciled with the checkpoint) is
  `blocked/checkpoint_mismatch` or `blocked/candidate_busy` — preserve the
  checkpoint and candidate for inspection rather than discarding it.
- If none exists — including when the candidate's implementation was committed
  in an earlier, unrelated session — construct a fresh invocation from live
  repository state alone. A missing invocation history is not itself a blocker:
  `review-fix-loop`'s own design goal is resuming "without requiring an
  uninterrupted implementation transcript," so a piecemeal implementation and a
  single-session implementation start identically, bound only to the exact
  current head and comparison base.

## Terminal result mapping

Validate the returned terminal result against `review-fix-loop`'s own schema and
reread live Git state before mapping:

- `converged` ends this step. The final head and base are clean, required
  validation passed, and `write_isolation` was `enforced` throughout. Because
  `acceptance_reconciliation_required` is `true` whenever the head or base
  changed during the loop, rebuild the change-demonstrating-test evidence and
  the acceptance ledger against the exact final head before treating the
  candidate as ready, then continue to
  [step 5](../SKILL.md#5-choose-exactly-one-publication-path). Do not invoke an
  additional invented review cycle once a schema-valid `converged` result is
  already bound to the current head and base.
- `changes_remaining` maps to `blocked`. Preserve the local candidate — every
  commit `review-fix-loop` made remains locally committed and is reported in
  `unpushed_commits` — and report the exact `reason` (`cycle_budget_exhausted`,
  `repeated_finding`, `oscillation`, `expanding_findings`,
  `repeated_failed_attempt`, or `current_candidate_validation_failure`),
  `unresolved_or_deferred_findings`, and `operator_action` as the blocking
  evidence and next action.
- `blocked` maps to `blocked` with the exact reason, current candidate, and
  `operator_action`. `missing_capability` and `reviewer_integrity_failure` fold
  into this skill's existing "treat as a failed local gate" rule for a missing
  dependency or reviewer mutation. `scope_decision_required` and
  `operator_input_required` fold into this skill's existing "review feedback
  requires redesigning the ticket" stop condition. `remote_advanced` and
  `publication_failed` never apply under `local_commit` and indicate a contract
  violation if returned.

Never translate a stale, malformed, or invocation-mismatched terminal result
into `converged`. Read `review_records` and `unresolved_or_deferred_findings`
directly from the terminal result for the per-cycle finding history; do not
reconstruct a separate resolved/unresolved/superseded ledger on top of it —
`review-fix-loop` already binds every review pass and disposition to the exact
head that produced it.

## Forward evaluation integrity

Exercise this composition with raw live-shaped candidate, change-contract, and
validation artifacts. Exclude implementation transcripts, intended fixes,
expected outputs, suspected findings, and prior conclusions. Treat contaminated
evidence as invalid and rerun the evaluation with a fresh isolated reviewer or
worker context.
