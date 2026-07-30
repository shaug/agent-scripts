#!/usr/bin/env python3
"""Reviewer isolation and complete-review orchestration for `review-fix-loop`.

This module implements the design's "Review execution" and "Reviewer write
prevention" sections (`design/review-fix-loop.md`) and workflow step 3
("Review"): resolving the fixed set of lenses a complete review must cover,
resolving which execution mode (`fresh_subagent` default or an explicit
`in_agent_override`) a given invocation actually gets, detecting an attempted
reviewer mutation from before/after worktree snapshots, building one
checkpoint-shaped `review_records` entry per review pass, and normalizing raw
findings into one deterministic order for later fix-cycle selection.

It intentionally has no third-party dependencies, matching the convention
already used by `skills/review-fix-loop/scripts/validate.py` and by the
bundled `references/review-suite/validate.py` this module imports: a skill
folder is the unit of distribution, so its scripts must work standalone
wherever the skill is installed.

This module does not run a subagent, spawn a process, or shell out to Git.
Actually creating a fresh reviewer context, restricting its tool surface, and
capturing real worktree state are host/runtime actions the executing agent
performs by following `references/reviewer-orchestration.md`; this module only
supplies the deterministic, testable decisions and data transformations that
sit around that action. It also does not decide which finding to fix or apply
any fix — the design's "Decide" and "Fix" workflow steps (4 and 5) and the
`accepted`/`rejected`/`deferred` disposition of a finding remain a later
child's responsibility (see design's rollout order); `select_next_finding`
only identifies which finding a cycle *would* target next in a stable,
reproducible order.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

HERE = Path(__file__).resolve().parent
REVIEW_SUITE_VALIDATE_PATH = HERE.parent / "references" / "review-suite" / "validate.py"

_SPEC = importlib.util.spec_from_file_location(
    "review_fix_loop_bundled_review_suite_validate", REVIEW_SUITE_VALIDATE_PATH
)
assert _SPEC and _SPEC.loader
REVIEW_SUITE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(REVIEW_SUITE)

# Sourced from the bundled contract's own constant rather than hand-copied, so
# this module cannot silently drift from the schema/semantics that actually
# enforce it (`_check_aggregate_clean_lens_executions` in the bundled
# `validate.py`).
REQUIRED_LENSES: tuple[str, ...] = REVIEW_SUITE.REQUIRED_AGGREGATE_LENSES

SEVERITY_ORDER = {"blocking": 0, "strong_recommendation": 1, "defer": 2}
GATING_SEVERITIES = frozenset({"blocking", "strong_recommendation"})
WORKTREE_CATEGORIES = ("tracked", "staged", "unstaged", "untracked", "ignored")

# The literal prohibitions every reviewer briefing must carry. Acceptance
# criterion: "Reviewer instructions explicitly prohibit worktree mutation and
# implementation." Keeping this as one shared tuple means the same wording
# reaches a fresh subagent and an explicitly authorized in-agent override
# alike, and a test can assert on the exact prohibitions in force rather than
# on prose that might drift between the two paths.
REVIEWER_PROHIBITIONS: tuple[str, ...] = (
    "Report findings only; do not implement, edit, or otherwise change any "
    "file in this worktree or any other.",
    "Never stage, commit, amend, rebase, or push any ref in this worktree or "
    "any other.",
    "Never run a tool or command that writes to the working tree, the index, "
    "or any Git ref; use read-only inspection and validation commands only.",
    "Do not resolve conflicts, run formatters or codemods, or apply any "
    "proposed fix, including one you propose yourself.",
)


class ReviewIntegrityError(ValueError):
    """A raw review-code-change result cannot be trusted for this cycle.

    Raised by `build_review_record` when `evaluate_review_result` finds the
    result untrustworthy: not schema-valid, not cross-field consistent (this
    includes the bundled contract's own aggregate-`clean` lens-execution
    completeness rule), or not bound to the exact head and comparison base
    this cycle captured. The caller must treat this like any other
    incomplete-evidence stop; there is no partially-trusted fallback record.
    """

    def __init__(self, errors: Sequence[str]):
        super().__init__("; ".join(errors))
        self.errors = list(errors)


def resolve_review_lenses() -> tuple[str, ...]:
    """Return the fixed set of lenses a complete review must cover.

    `review-fix-loop` has no selectable lens subset: design states the
    complete repository review suite is its "sole initial review mode," and
    the invocation schema has no field for requesting a different one. This
    function exists so every caller and test names one canonical source for
    that fixed set instead of hand-copying the three lens names and risking
    drift from the contract that actually enforces them.
    """
    return REQUIRED_LENSES


def evaluate_review_result(
    result: Mapping[str, Any], expected_head: str, expected_base: str
) -> list[str]:
    """Return rejection reasons for a raw review-code-change result.

    Empty means the result is trustworthy evidence for exactly this cycle's
    head and comparison base: schema-valid, cross-field consistent, and bound
    to `expected_head`/`expected_base` at both the result's own candidate and
    every lens execution it records.

    Unlike a plain "accept only clean" gate, this accepts any verdict —
    `changes_required` and `blocked` are the ordinary outcome of most review
    cycles, not failures of this function. A `changes_required` result is not
    required to carry lens executions for every lens: the orchestration
    protocol stops the sequence at the first gating finding, so a partial
    `lens_executions` list is expected there. Completeness is required, and
    enforced here via the bundled contract's own
    `_check_aggregate_clean_lens_executions`, only for a `clean` verdict —
    this is exactly the acceptance criterion "Reviewer output is rejected if
    required lenses or evidence are incomplete."
    """
    errors = [
        f"schema: {error}" for error in REVIEW_SUITE.validate_result(dict(result))
    ]
    if errors:
        # A schema-level rejection already explains why the result is
        # untrustworthy; do not layer confusing candidate-binding errors on
        # top of a document that is not even shape-valid.
        return errors
    return _candidate_binding_errors(result, expected_head, expected_base)


def _candidate_binding_errors(
    result: Mapping[str, Any], expected_head: str, expected_base: str
) -> list[str]:
    """Return binding errors a schema-only check cannot express.

    Shared by `evaluate_review_result` and `evaluate_review_pair`, both of
    which have already confirmed `result` is schema-valid before calling
    this.
    """
    errors: list[str] = []
    if result.get("lens") != "aggregate":
        errors.append(f"lens: expected an aggregate result, got {result.get('lens')!r}")

    candidate = result.get("candidate") or {}
    # A `blocked` result may legitimately omit candidate identity entirely
    # (the shared contract allows this when the caller could not establish
    # it); only compare when the result actually asserts some identity, so an
    # empty `blocked` candidate is not mistaken for a stale-candidate
    # mismatch.
    if (
        candidate.get("head_sha") is not None
        or candidate.get("comparison_base_sha") is not None
    ):
        if (
            candidate.get("head_sha") != expected_head
            or candidate.get("comparison_base_sha") != expected_base
        ):
            errors.append(
                "candidate: result is not bound to the current candidate "
                f"(expected head {expected_head} / base {expected_base}, got "
                f"head {candidate.get('head_sha')!r} / "
                f"base {candidate.get('comparison_base_sha')!r})"
            )

    for execution in result.get("lens_executions") or []:
        if not isinstance(execution, dict):
            continue
        if (
            execution.get("head_sha") != expected_head
            or execution.get("comparison_base_sha") != expected_base
        ):
            errors.append(
                f"lens_executions: {execution.get('lens')!r} execution is not "
                "bound to the current candidate"
            )

    return errors


def evaluate_review_pair(
    packet: Mapping[str, Any],
    result: Mapping[str, Any],
    expected_head: str,
    expected_base: str,
) -> list[str]:
    """Return rejection reasons across the packet supplied and its result.

    `evaluate_review_result` alone can reject an incomplete or misbound
    *result*, but it never sees the *packet* review-fix-loop actually
    supplied to the reviewer, so it cannot by itself catch a `clean` verdict
    paired with a packet whose own required focused or full validation entry
    was `failed` or `unavailable` — exactly the "or evidence are incomplete"
    half of the acceptance criterion, distinct from lens completeness. This
    reuses the bundled contract's own `validate_pair`, which enforces that
    pairing rule (`_check_clean_requires_passing_validation`) alongside
    packet/result candidate-identity consistency, then adds the same
    caller-expected-candidate binding `evaluate_review_result` checks.

    Prefer this over `evaluate_review_result` whenever the packet that was
    actually handed to the reviewer is available; use `evaluate_review_result`
    only when it is not (for example, when re-validating a previously
    recorded result without retaining its packet).
    """
    pair_errors = [
        f"pair: {error}"
        for error in REVIEW_SUITE.validate_pair(dict(packet), dict(result))
    ]
    if pair_errors:
        return pair_errors
    return _candidate_binding_errors(result, expected_head, expected_base)


def resolve_review_execution_mode(
    mode: str,
    *,
    override_authorization: str | None = None,
    host_supports_fresh_subagent: bool = True,
) -> dict[str, Any]:
    """Resolve the review-execution mode this host actually grants.

    `mode` and `override_authorization` come from a validated invocation's
    `review_execution` object (`validate_invocation` already rejects
    `in_agent_override` without `override_authorization`, and
    `fresh_subagent` carrying one); this function assumes that invariant
    already holds and resolves the one thing schema validation cannot decide:
    whether *this* host can actually honor `fresh_subagent`.

    Returns a dict with `independence` (`"fresh_subagent"`,
    `"in_agent_override"`, or `None` when blocked), `authorized_by` (the
    recorded `override_authorization`, or `None`), and `blocked_reason`
    (`None`, or `"missing_capability"`).

    - `in_agent_override` is always honored when authorized, regardless of
      host capability: an explicit override does not require the fresh path
      to be unavailable first.
    - `fresh_subagent` is honored only when `host_supports_fresh_subagent` is
      true. Design states there is "no automatic fallback": an unsupported
      host with no override returns `missing_capability` rather than quietly
      running in-agent — this is the acceptance criterion "In-agent execution
      occurs only when explicitly requested."
    """
    if mode == "in_agent_override":
        return {
            "independence": "in_agent_override",
            "authorized_by": override_authorization,
            "blocked_reason": None,
        }
    if mode == "fresh_subagent":
        if host_supports_fresh_subagent:
            return {
                "independence": "fresh_subagent",
                "authorized_by": None,
                "blocked_reason": None,
            }
        return {
            "independence": None,
            "authorized_by": None,
            "blocked_reason": "missing_capability",
        }
    raise ValueError(f"unknown review_execution mode: {mode!r}")


def generate_reviewer_identity(
    independence: str, sequence: int, *, explicit: str | None = None
) -> str:
    """Return this review pass's reviewer identity.

    Design requires "different reviewer identities per head" so a fresh
    subagent's freshness is actually observable, not merely asserted. Default
    identities follow the `<independence>-review-<sequence>` shape already
    used by `references/examples/*` (for example
    `fresh-subagent-review-1`/`fresh-subagent-review-2`); an explicit identity
    — a real subagent or session ID a host can supply — always wins.
    """
    if explicit:
        return explicit
    if sequence < 1:
        raise ValueError(f"sequence must be >= 1, got {sequence}")
    return f"{independence.replace('_', '-')}-review-{sequence}"


def detect_worktree_mutation(
    before: Mapping[str, Any], after: Mapping[str, Any]
) -> list[str]:
    """Return mutation descriptions found between two worktree snapshots.

    `before`/`after` carry the same `tracked`/`staged`/`unstaged`/`untracked`/
    `ignored` path lists as every other worktree-state shape in this contract
    family, plus an optional `head_sha`. This implements the design's
    "before/after capture of HEAD, refs, index, tracked, staged, unstaged,
    untracked, and ignored state" tier of reviewer write prevention.

    An empty return means no attributable change was observed by *this*
    check; it does not by itself certify write isolation — design also
    requires the stronger filesystem-boundary and restricted-tool-surface
    controls this function cannot see. A non-empty return means the cycle
    must fail closed: `build_review_record` forces `write_isolation:
    "violated"` whenever any mutation is passed to it, and
    `validate.py`'s `_check_converged_requires_clean_evidence` already
    rejects `converged` for any review record with a non-empty
    `mutation_attempts`, so a detected mutation here propagates all the way to
    a rejected cycle rather than being silently tolerated.
    """
    mutations: list[str] = []
    before_head = before.get("head_sha")
    after_head = after.get("head_sha")
    if before_head != after_head:
        mutations.append(f"head_sha advanced from {before_head!r} to {after_head!r}")
    for category in WORKTREE_CATEGORIES:
        before_paths = set(before.get(category) or [])
        after_paths = set(after.get(category) or [])
        if before_paths != after_paths:
            added = sorted(after_paths - before_paths)
            removed = sorted(before_paths - after_paths)
            detail = []
            if added:
                detail.append(f"added {added}")
            if removed:
                detail.append(f"removed {removed}")
            mutations.append(f"{category}: " + "; ".join(detail))
    return mutations


def build_review_record(
    *,
    sequence: int,
    result: Mapping[str, Any],
    expected_head: str,
    expected_base: str,
    independence: str,
    reviewer_identity: str,
    mutation_attempts: Sequence[str] = (),
    packet: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one checkpoint-shaped `review_records` entry from a raw result.

    Fails closed: raises `ReviewIntegrityError` — never returns a partially
    trusted record — when `result` is not schema-valid, cross-field
    consistent, or bound to `expected_head`/`expected_base`. When `packet` is
    supplied (the raw evidence packet this cycle actually handed to the
    reviewer), also fails closed when that packet's own required focused or
    full validation entry cannot back a `clean` verdict
    (`evaluate_review_pair`); when it is omitted, only `evaluate_review_result`
    runs, so a `clean` result whose packet validation was actually
    unavailable would not be caught here — always pass `packet` when it is
    available.

    Any non-empty `mutation_attempts` forces `write_isolation: "violated"`
    regardless of the aggregate verdict: design states "an attempted
    prohibited mutation invalidates the review even if the runtime blocks
    it," so a clean-looking result from a reviewer that touched the worktree
    still is not enforced write isolation.

    `finding_dispositions` starts empty: disposing a finding as
    `accepted`/`rejected`/`deferred` is the loop's "Decide" workflow step (4),
    which this ticket does not implement (see design's rollout order — this
    child covers "reviewer isolation and complete-review orchestration," step
    3 "Review"). A later caller that does run Decide populates this same
    field afterward with the shape it already reserves.
    """
    if packet is not None:
        errors = evaluate_review_pair(packet, result, expected_head, expected_base)
    else:
        errors = evaluate_review_result(result, expected_head, expected_base)
    if errors:
        raise ReviewIntegrityError(errors)

    return {
        "sequence": sequence,
        "head_sha": expected_head,
        "comparison_base_sha": expected_base,
        "review_independence": independence,
        "reviewer_identity": reviewer_identity,
        "write_isolation": "violated" if mutation_attempts else "enforced",
        "aggregate_verdict": result["verdict"],
        "finding_dispositions": [],
        "mutation_attempts": list(mutation_attempts),
    }


def normalize_findings(findings: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return `findings` in one deterministic, input-order-independent order.

    Sorted by severity (`blocking` before `strong_recommendation` before
    `defer`), then lens name, then stable finding `id`. `review-code-change`
    does not guarantee any particular ordering across lenses or review
    passes; without a canonical order, the loop's finding-to-fix linkage and
    checkpoint replay could disagree from one run to the next even given
    byte-identical review evidence — this is the scope item "normalize
    findings for deterministic selection and checkpointing."

    This is a pure reordering: every input mapping is shallow-copied, never
    mutated or dropped (the bundled contract already rejects duplicate
    finding ids upstream, in `validate_result`).
    """

    def sort_key(finding: Mapping[str, Any]) -> tuple[int, str, str]:
        return (
            SEVERITY_ORDER.get(finding.get("severity"), len(SEVERITY_ORDER)),
            str(finding.get("lens", "")),
            str(finding.get("id", "")),
        )

    return [dict(finding) for finding in sorted(findings, key=sort_key)]


def select_next_finding(findings: Iterable[Mapping[str, Any]]) -> dict[str, Any] | None:
    """Return the one finding a fix cycle would target next, or `None`.

    Deterministically the first gating (`blocking` or `strong_recommendation`)
    entry of `normalize_findings`'s canonical order. `defer` findings are
    never selected: they are real concerns intentionally kept out of the
    active cycle, per the shared review contract's severity semantics.

    Selecting a finding is not disposing or fixing it — see
    `build_review_record`'s docstring for why `finding_dispositions` and
    fix application remain a later child's responsibility.
    """
    for finding in normalize_findings(findings):
        if finding.get("severity") in GATING_SEVERITIES:
            return finding
    return None


def build_reviewer_briefing(
    *, independence: str, head_sha: str, comparison_base_sha: str
) -> str:
    """Return the literal instruction text handed to one review pass.

    Acceptance criterion: "Reviewer instructions explicitly prohibit worktree
    mutation and implementation." This is the actual text a caller embeds in
    the fresh subagent's (or, under an explicit override, the in-agent)
    prompt immediately before invoking `review-code-change`, so the
    prohibition travels with every review pass instead of living only in a
    document a caller might forget to consult.
    """
    lines = [
        "You are running the complete repository-owned review-code-change "
        f"sequence for candidate {head_sha} against comparison base "
        f"{comparison_base_sha}.",
        f"Execution context: {independence}.",
        *REVIEWER_PROHIBITIONS,
        "Invoke review-code-change with only the supplied raw evidence "
        "packet; do not consult any implementation transcript, intended fix, "
        "prior conclusion, or suspected finding.",
    ]
    return "\n".join(lines)
