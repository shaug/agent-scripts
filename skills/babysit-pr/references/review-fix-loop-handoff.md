# Review-fix-loop handoff and result mapping

Use repository-owned `review-fix-loop` as the sole canonical owner of
post-publication repository review, finding disposition, fix authorship
orchestration, re-review, convergence detection, and — under this policy — the
eventual push back to the PR. Read its live skill,
[`references/CONTRACT.md`](../../review-fix-loop/references/CONTRACT.md), and
[`references/update-pr.md`](../../review-fix-loop/references/update-pr.md)
before delegation. If its delivered contract differs materially from this
boundary, stop and reconcile ownership rather than copying loop mechanics back
into `babysit-pr`.

This reference applies to every head-changing repository-review pass this skill
performs on an already-published PR, always under
`publication.policy: update_pr` — `review-fix-loop` owns the exact expected-old
publish once its review converges, so this skill withholds its own push and
never races it. `implement-ticket`'s own initial-candidate delegation (before
any PR exists, under `local_commit`) and `carve-changesets`'s per-changeset
review are separate, differently-scoped consumers; this handoff does not apply
to either.

## Responsibility boundary

`babysit-pr` retains PR/candidate identity resolution, CI diagnosis and retries,
all published human/connector feedback collection and disposition, authoring the
actual fix content for a diagnosed CI failure or accepted feedback item, the
validation commands it approves, invocation construction, host-port
implementation (see below), terminal-result validation, mergeability, merge, and
final reporting. It never hands ticket lifecycle, tracker transition,
deployment, or cleanup to `review-fix-loop`.

After delegation, `review-fix-loop` owns the local candidate lock, reviewer
isolation and integrity enforcement, raw `review-code-change` packet
construction and binding, finding selection and ordering, fix-cycle budget
accounting, validated commit and fast-forward promotion of every accepted fix,
evidence invalidation after each new head, convergence detection, the exact
expected-old fast-forward publish once converged, and its own durable checkpoint
and terminal result. Do not reproduce those mechanics in this skill.

## Pre-mutation dependency gate

Verify `review-fix-loop` by stable repository-owned name before starting any
mutation-owning watch, per
[the skill's own dependency gate](../SKILL.md#pre-mutation-dependency-gate).
`review-fix-loop`'s own dependency gate covers `review-code-change` and its
three lenses; do not additionally require or substitute a direct
`review-code-change` binding here. Missing `review-fix-loop` returns `blocked`
before any code mutation; do not download an external implementation at runtime,
restore a private inlined fix loop, or accept an unreviewed candidate as ready.

## Constructing the invocation

Immediately before delegation, capture the exact committed local head,
comparison base, complete `base...HEAD` diff, and
tracked/staged/unstaged/untracked/ignored worktree state. The worktree must be
globally clean and every intended change committed but **not pushed** —
`review-fix-loop`'s own invocation schema rejects a dirty worktree, and pushing
first would hand it a candidate already equal to the remote head, defeating its
own expected-old publish.

Map that evidence onto one `review-fix-loop` invocation:

- `candidate`: the exact branch, local head SHA, comparison base, diff, and
  worktree state above, with `all_changes_committed: true`. Populate
  `source_binding` with the authenticated head repository, remote URL, fully
  qualified head ref, and the exact remote object ID this skill most recently
  observed for it (the PR's current head before this fix). This is the same
  pre-fix PR head value `publication.pull_request.expected_old_head_sha` below
  also carries, but the two fields serve independently required purposes:
  `source_binding.observed_object_id` only supports `review-fix-loop`'s own
  ahead/behind reporting, while `expected_old_head_sha` is the actual
  compare-and-swap value its expected-old fast-forward publish reads at push
  time — populate both from the same observed SHA.
- `change_contract`: the ticket's observable goal, acceptance criteria,
  non-goals, behavior to preserve, named architecture/design/contract documents,
  and representative nearby code and tests, reconstructed from live ticket or PR
  state when the caller supplied it, or from current PR description and
  repository instructions otherwise. Set `allowed_remediation_scope` to the
  ticket-scoped fix boundary this skill's own
  [CI and feedback decisions](ci-and-feedback.md) already enforce — material,
  ticket-scoped correctness/security/acceptance/architecture/validation issues
  only, never polish, hypothetical hardening, or sibling/parent work.
- `review_execution.mode`: `fresh_subagent` by default, matching this skill's
  existing fresh read-only review requirement. Use `in_agent_override` only
  through an explicit current-user or caller-authorized override recorded before
  delegation; there is no automatic fallback.
- `fix_cycle_budget.max_fix_cycles`: `3`, matching the repository's existing
  three-cycle norm used elsewhere in this suite (`review-code-change`'s own
  lens-sequence retry and `implement-ticket`'s initial-candidate delegation).
  This is a distinct budget from `review-code-change`'s own three-cycle
  lens-sequence retry budget; neither touches the other.
- `validation`: this skill's separately approved focused and full commands.
- `publication.policy`: always `update_pr`.
- `publication.pull_request`: the PR's own head repository, fully qualified head
  ref, base ref, this skill's most recently observed base SHA, and
  `expected_old_head_sha` — the same pre-fix PR head SHA recorded in
  `candidate.source_binding.observed_object_id` above. This field, not
  `source_binding`, is what `review-fix-loop`'s expected-old fast-forward
  publish actually compares against at push time; the invocation schema requires
  it here.
- `publication.remote_iteration_grants`: omit unless a specific,
  invocation-authorized mechanism demonstrably requires an origin-visible head
  mid-loop. Nothing in this skill's ordinary CI/feedback/review flow requires
  one.

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
[`update-pr.md`](../../review-fix-loop/references/update-pr.md)'s "Host
boundary" section describes (identical to `local_commit`'s three ports;
`resolve publication target`, `check remote`, and `publish` are
`review-fix-loop`'s own, not a host port):

- **`reviewer`**: spawn a fresh read-only context restricted to
  `Read, Grep, Glob, Bash, Agent, Task, Skill` that invokes repository-owned
  `review-code-change` with raw candidate evidence only — excluding the
  implementation transcript, the diagnosed CI/feedback issue this fix responds
  to, prior conclusions, and suspected findings. Give the review a capability
  tier adequate for judgment: it inherits the session's tier by default, and a
  review that missed a defect a later cycle surfaces escalates one tier instead
  of rerunning identically. The reviewer receives evidence and contracts, never
  conclusions — if the invocation being written steers the answer ("do not
  flag", "this is fine", a pre-judged severity), stop and rewrite it. The
  pressure is sharpest immediately after authoring a fix, when it is tempting to
  dispatch the re-review already knowing what it should say; a steered reviewer
  returns confirmation, not review. Prefer one well-briefed re-review to several
  thin ones; each fresh review pass costs a full three-lens sequence.
- **`decide`**: apply
  [the consumption disciplines](review-suite/consumption-disciplines.md) to
  every finding `review-fix-loop` selects — verify it against the codebase
  before implementing it, clarify every unclear finding before implementing any,
  never perform agreement, and accept only a finding that is material and within
  `change_contract.allowed_remediation_scope`. A finding whose correct fix would
  exceed that scope returns `expands_scope` and lets `review-fix-loop` stop as
  `blocked/scope_decision_required` — surface it for the caller to disposition
  immediately rather than silently expanding the PR.
- **`apply_fix`**: implement the smallest coherent accepted remediation. When
  this port is about to consume the invocation's last remaining fix cycle,
  replace the incumbent implementer rather than continuing it: dispatch a fresh
  context one capability tier above the incumbent's, or a fresh context at the
  same tier when no higher tier is available, briefed with the surviving finding
  and a summary of what prior attempts tried and why they failed, not the full
  transcript. When a fix fails repeatedly and `superpowers:systematic-debugging`
  is available in the session skill listing, load it as the escalated
  implementer's recommended diagnosis method; when the peer is not in the
  listing, the escalated implementer diagnoses from logs and evidence without
  comment.
- **validation ports**: run this skill's separately approved focused and full
  validation commands and classify a candidate-attributable failure as tractable
  remediation input exactly as [CI and feedback decisions](ci-and-feedback.md)
  already requires for a branch-caused failure.

## Resuming an interrupted invocation

`review-fix-loop` resumes from live repository and checkpoint state without
requiring an uninterrupted transcript. Before constructing a new invocation,
check for an existing durable checkpoint under
`<git-common-directory>/review-fix-loop/checkpoints/`:

- If one exists for this exact repository, branch, and candidate identity,
  reconcile and resume it rather than starting a fresh invocation, keeping its
  original `invocation_id` and fix-cycle budget. A reconciliation failure (an
  active lock holder, a dirty candidate, or live head/base/remote state that
  cannot be reconciled with the checkpoint) is `blocked/checkpoint_mismatch` or
  `blocked/candidate_busy` — preserve the checkpoint and candidate for
  inspection rather than discarding it. Reread the live PR head first: a
  checkpoint recorded against a remote head this skill's own watcher has since
  observed advance is stale evidence, not a resumable invocation.
- If none exists, construct a fresh invocation from live repository and PR state
  alone, bound to the exact current local head and comparison base.

## Terminal result mapping

Validate the returned terminal result against `review-fix-loop`'s own schema and
reread live GitHub PR state before mapping:

- `converged` — the final head's review is `clean`, required validation passed,
  `write_isolation` was `enforced` throughout, and the exact expected-old
  fast-forward publish landed and read back correctly:
  `publication.status: published` and `unpushed_commits` is empty. Restart every
  remote gate (CI, human/connector review, threads) invalidated by the new head
  and resume the ordinary
  [snapshot processing order](../SKILL.md#process-each-snapshot) from the
  published candidate.
- `changes_remaining` maps to `blocked`. `publication.status` is `withheld` —
  remediation stopped before convergence, so no push was attempted. Preserve the
  local candidate: every commit `review-fix-loop` made remains locally committed
  and is reported in `unpushed_commits`. Report the exact `reason`
  (`cycle_budget_exhausted`, `oscillation`, `expanding_findings`,
  `repeated_failed_attempt`, or `current_candidate_validation_failure` —
  `repeated_finding` is in `review-fix-loop`'s general schema but is
  deliberately never one of `update_pr`'s own automatic stop reasons),
  `unresolved_or_deferred_findings`, and `operator_action`. Surface the retained
  unpushed commits prominently in the terminal report per
  [Return one terminal handoff](../SKILL.md#return-one-terminal-handoff) — the
  PR still shows its prior head, so an operator reading only GitHub would not
  otherwise know a fix exists.
- `blocked` maps to `blocked` with the exact reason, current candidate, and
  `operator_action`. `missing_capability` and `reviewer_integrity_failure` fold
  into this skill's existing "treat as a failed local gate" rule for a missing
  dependency or reviewer mutation. `scope_decision_required` and
  `operator_input_required` fold into feedback requiring clarification before a
  fix proceeds. Three reasons are specific to `update_pr` and need a safe
  watcher transition, not merely a blocked report:
  - `missing_authority` — the publication target or a remote-iteration grant
    failed to resolve before any lock or mutation; reconcile the PR's recorded
    head repository/ref against this skill's own resolved source binding before
    retrying.
  - `remote_advanced` — the remote head observably moved away from the
    invocation's `expected_old_head_sha`, either mid-loop or at publish time.
    This means another process pushed to the PR while this delegation ran.
    Reread the live PR head independently of the stale invocation state before
    doing anything else: if the competing head already carries an equivalent or
    superseding fix, treat it as the current candidate and restart ordinary
    watching from it rather than re-attempting this delegation's now-stale local
    commits; if it does not, preserve this delegation's local commits as
    `unpushed_commits` and stop for operator reconciliation rather than forcing
    a competing push.
  - `publication_failed` — the remote was unreachable, the push failed for a
    reason other than a losing race, or the post-push readback did not match.
    Treat this as a transient-infrastructure classification per
    [CI and feedback decisions](ci-and-feedback.md): reread the live PR head to
    confirm nothing actually landed, then retry the same converged local
    candidate's publish rather than re-running the review.

Never translate a stale, malformed, or invocation-mismatched terminal result
into `converged`. Read `review_records` and `unresolved_or_deferred_findings`
directly from the terminal result for the per-cycle finding history; do not
reconstruct a separate resolved/unresolved/superseded ledger on top of it.

## Forward evaluation integrity

Exercise this composition with raw live-shaped PR, diff, resulting-tree, check,
review, comment, thread, and worktree artifacts. Exclude implementation
transcripts, intended fixes, expected outputs, suspected findings, and prior
conclusions. Treat contaminated evidence as invalid and rerun the evaluation
with a fresh isolated reviewer or worker context.
