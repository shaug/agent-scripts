#!/usr/bin/env python3
"""Deterministic fresh-process stand-in for a compatible agent runtime."""

from __future__ import annotations

import json
import os
import re
import sys

ACTION_VOCABULARY = (
    "accept_mechanical_exception",
    "diagnose_dirty_tree",
    "diagnose_source_behind_base",
    "document_exception_evidence",
    "escalate_material_decision",
    "preserve_validated_order",
    "publish_without_merge",
    "refuse_dirty_source",
    "refuse_reorder_or_renumber",
    "refuse_source_behind_base",
    "request_guardrail_decision",
    "separate_rename_from_behavior",
    "split_by_subsystem",
    "stop_for_oversized_changeset",
    "stop_on_plan_conflict",
    "withhold_merge",
)


def compact(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def action_result(payload: dict) -> dict:
    target = payload.get("target_skill")
    contract = compact(
        payload.get("skill_prompt", "")
        + "\n"
        + "\n".join((payload.get("contract_documents") or {}).values())
    )
    required_contract = (
        "independently reviewable",
        "mechanical refactors",
        "not silently reordered or renumbered",
        "publish authority does not permit merging",
        "source is behind the base",
    )
    if target != "carve-changesets" or not all(
        fragment in contract for fragment in required_contract
    ):
        return {
            "target_skill": target,
            "terminal_state": "blocked",
            "actions": [],
        }

    request = compact(payload.get("request", ""))
    scenario = payload.get("scenario") or {}
    state = compact(" ".join(str(value) for value in scenario.values()))
    actions: list[str]
    terminal_state: str

    if "dirty" in state:
        terminal_state = "blocked"
        actions = ["diagnose_dirty_tree", "refuse_dirty_source"]
    elif "behind base" in state and "two-part override" not in state:
        terminal_state = "blocked"
        actions = ["diagnose_source_behind_base", "refuse_source_behind_base"]
    elif "validated plan" in state and "conflicts" in state:
        terminal_state = "blocked"
        actions = ["escalate_material_decision", "stop_on_plan_conflict"]
    elif "validated changesets" in state and (
        "renumber" in request or "reorder" in request
    ):
        terminal_state = "blocked"
        actions = ["preserve_validated_order", "refuse_reorder_or_renumber"]
    elif "publish authority" in state and "merge authority is withheld" in state:
        terminal_state = "prs_open"
        actions = ["publish_without_merge", "withhold_merge"]
    elif "explicit mechanical exception" in state:
        terminal_state = "plan_ready"
        actions = ["accept_mechanical_exception", "document_exception_evidence"]
    elif "oversized" in state:
        terminal_state = "blocked"
        actions = ["request_guardrail_decision", "stop_for_oversized_changeset"]
    elif "rename-only" in state:
        terminal_state = "plan_ready"
        actions = ["separate_rename_from_behavior"]
    elif "independent subsystems" in state:
        terminal_state = "plan_ready"
        actions = ["split_by_subsystem"]
    else:
        terminal_state = "blocked"
        actions = []

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
