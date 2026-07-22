#!/usr/bin/env python3
"""Deterministic fresh-process stand-in for a compatible agent runtime.

This is a simulation, not a model evaluation: it hand-codes the decisions a
compliant runtime must make so the forward harness and grading stay
deterministic. It cannot detect a model misreading the skill; use
`claude_executor.py` (or another real-runtime executor) via
`run_forward.py --executor` for behavioral coverage.
"""

from __future__ import annotations

import json
import os
import re
import sys


def compact(text: str) -> str:
    """Normalize whitespace so Markdown reflows do not break matching."""
    return re.sub(r"\s+", " ", text)


def action_result(payload: dict) -> dict:
    target = payload["target_skill"]
    prompt = compact(payload["skill_prompt"])
    required_contract = {
        "implement-ticket": (
            "`review-code-change` and `babysit-pr` are available",
            "Map `ready PR only` to `ready_to_merge`",
            "`prs_open`",
            "`ready_prs`",
            "Normal ticket execution never uses `watch_until_closed`",
        ),
        "implement-epic": (
            "Do not make this skill invoke",
            "`carve-changesets` itself",
            "`ready_pr`",
            "`ready_prs`",
        ),
    }[target]
    if not all(compact(fragment) in prompt for fragment in required_contract):
        return {
            "target_skill": target,
            "terminal_state": "blocked",
            "actions": ["skill_contract_incomplete"],
        }

    artifacts = payload["artifacts"]
    ticket = artifacts["ticket"]
    pr = artifacts["pr"]
    checks = artifacts["checks"]
    reviews = artifacts["reviews"]
    worktree = artifacts["worktree"]
    handoff = artifacts["handoff"]
    authority = payload.get("authority") or {}
    capabilities = payload.get("capabilities") or {}
    actions = []

    if target == "implement-epic":
        if handoff.get("stack_child_result"):
            return {
                "target_skill": target,
                "terminal_state": "mixed_ticket_results",
                "actions": [
                    "verify_stack_topology",
                    "verify_each_pr_gate",
                    "verify_full_stack_on_base",
                    "do_not_own_decomposition_mechanics",
                    "refresh_graph_after_merged_only",
                ],
            }
        return {
            "target_skill": target,
            "terminal_state": "mixed_ticket_results",
            "actions": [
                "consume_ticket_states_unchanged",
                "do_not_invoke_babysit_pr_directly",
                "refresh_graph_after_merged_only",
            ],
        }

    if ticket.get("whole_epic"):
        return {
            "target_skill": target,
            "terminal_state": "requires_epic",
            "actions": [
                "route_before_ticket_dependencies",
                "perform_no_mutation",
            ],
        }

    if not capabilities.get("babysit_pr"):
        return {
            "target_skill": target,
            "terminal_state": "blocked",
            "actions": ["fail_before_mutation", "name_missing_babysit_pr"],
        }

    if artifacts["diff"].get("guardrail") == "oversized" and not capabilities.get(
        "carve_changesets"
    ):
        return {
            "target_skill": target,
            "terminal_state": "blocked",
            "actions": ["stop_before_publication", "name_missing_carve_changesets"],
        }

    if not handoff.get("result_well_formed", True) or handoff.get("result_stale"):
        return {
            "target_skill": target,
            "terminal_state": "blocked",
            "actions": ["reject_stale_or_malformed_result", "reread_live_pr"],
        }

    if artifacts["diff"].get("guardrail") == "oversized":
        actions.append("record_guardrail_evidence")
        if handoff.get("rubric") == "ticket_split":
            return {
                "target_skill": target,
                "terminal_state": "blocked",
                "actions": actions
                + [
                    "route_to_tracker_split",
                    "stop_before_publication",
                    "do_not_invoke_carve_changesets",
                ],
            }
        if not authority.get("decompose_oversized"):
            return {
                "target_skill": target,
                "terminal_state": "blocked",
                "actions": actions
                + [
                    "stop_before_publication",
                    "do_not_publish_monolithic_pr",
                    "do_not_invoke_carve_changesets",
                ],
            }
        if handoff.get("mid_stack_redesign"):
            return {
                "target_skill": target,
                "terminal_state": "blocked",
                "actions": actions
                + [
                    "preserve_partial_stack",
                    "report_mid_stack_redesign",
                    "do_not_rewrite_merged_history",
                ],
            }
        if handoff.get("carve_terminal") == "prs_open":
            stack_count = handoff.get("stack_count")
            if not (
                pr.get("state") == "multiple_open"
                and pr.get("mergeable") is True
                and isinstance(stack_count, int)
                and stack_count > 0
                and handoff.get("topology") == "verified"
                and handoff.get("closing_syntax") == "final_only"
                and checks.get("status") == "success"
                and reviews.get("per_changeset") == "clean"
            ):
                return {
                    "target_skill": target,
                    "terminal_state": "blocked",
                    "actions": [
                        "reject_stale_or_malformed_result",
                        "reread_live_pr",
                    ],
                }
            return {
                "target_skill": target,
                "terminal_state": "ready_prs",
                "actions": actions
                + [
                    "invoke_carve_changesets",
                    "skip_direct_babysit_handoff",
                    "place_closing_syntax_final_pr_only",
                    "verify_stack_topology",
                    "verify_each_pr_gate",
                ],
            }

    if pr.get("state") == "closed" and not pr.get("merged"):
        return {
            "target_skill": target,
            "terminal_state": "blocked",
            "actions": ["preserve_artifacts", "report_closed_without_merge"],
        }

    if handoff.get("delegated"):
        if not handoff.get("exclusive_transfer"):
            return {
                "target_skill": target,
                "terminal_state": "blocked",
                "actions": ["reject_concurrent_mutation"],
            }
        actions.append("transfer_exclusive_mutation_ownership")

    if reviews.get("human_response_required") and not authority.get("reply"):
        return {
            "target_skill": target,
            "terminal_state": "blocked",
            "actions": ["do_not_reply_or_resolve", "preserve_feedback_gate"],
        }

    if reviews.get("connector_head") not in (None, pr.get("head")):
        return {
            "target_skill": target,
            "terminal_state": "blocked",
            "actions": ["reject_stale_connector_verdict"],
        }

    if handoff.get("resumed"):
        actions.extend(["adopt_verified_canonical_pr", "deduplicate_prior_actions"])

    if pr.get("external_head_change"):
        actions.extend(
            [
                "revalidate_candidate_identity",
                "invalidate_head_bound_evidence",
                "rebuild_remote_gates",
            ]
        )

    if artifacts["repository"].get("tracker") == "linear":
        actions.append("preserve_tracker_pr_host_separation")

    if artifacts["diff"].get("base_drift") == "unrelated":
        actions.append("retain_only_proven_unaffected_evidence")
    elif artifacts["diff"].get("base_drift") == "relevant":
        actions.extend(
            [
                "invalidate_drift_affected_evidence",
                "revalidate_commit_push",
                "fresh_review_code_change",
                "rebuild_remote_gates",
            ]
        )

    if (
        reviews.get("published_fix_required")
        or checks.get("classification") == "branch_caused"
    ):
        actions.extend(
            [
                "ticket_scoped_fix",
                "revalidate_commit_push",
                "fresh_review_code_change",
                "rebuild_remote_gates",
            ]
        )
    elif checks.get("classification") == "infrastructure":
        actions.extend(["retry_diagnosed_run_only", "make_no_code_mutation"])

    if not worktree.get("exclusive_owner", True):
        return {
            "target_skill": target,
            "terminal_state": "blocked",
            "actions": actions + ["reject_concurrent_mutation"],
        }

    if authority.get("merge"):
        actions.extend(
            [
                "invoke_merge_when_ready",
                "verify_merge_live",
                "caller_verifies_mainline_tracker_cleanup",
            ]
        )
        terminal_state = "merged"
    else:
        actions.extend(["invoke_ready_to_merge", "verify_non_merge_gates"])
        terminal_state = "ready_pr"

    return {
        "target_skill": target,
        "terminal_state": terminal_state,
        "actions": sorted(set(actions)),
    }


def main() -> int:
    payload = json.load(sys.stdin)
    result = action_result(payload)
    result["executor_pid"] = os.getpid()
    json.dump(result, sys.stdout, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
