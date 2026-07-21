#!/usr/bin/env python3
"""Real-runtime forward-evaluation executor backed by Claude Code headless mode.

Reads one result-blind evaluation packet as JSON on stdin (the shape built by
`run_forward.py`), asks a fresh `claude -p` process to act as the target
skill's runtime, and prints one JSON result to stdout:

    {"target_skill": ..., "terminal_state": ..., "actions": [...]}

The evaluated model receives the skill prompt, the request, and raw scenario
artifacts, plus the closed action vocabulary below so its choices are gradable
against `forward_expectations.json`. It never sees fixture identity or any
expectations. Requires the `claude` CLI on PATH (override with --claude-bin).

Usage:
    python3 run_forward.py --executor "python3 claude_executor.py"
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

TERMINAL_STATES = (
    "ready_pr",
    "merged",
    "blocked",
    "requires_epic",
    "mixed_ticket_results",
)

# Closed vocabulary shared with fixture_executor.py and
# forward_expectations.json. Grading is multiple-choice by design: the model
# must decide which obligations apply, not invent matching strings.
ACTION_VOCABULARY = (
    "adopt_verified_canonical_pr",
    "caller_verifies_mainline_tracker_cleanup",
    "consume_ticket_states_unchanged",
    "deduplicate_prior_actions",
    "do_not_invoke_babysit_pr_directly",
    "do_not_reply_or_resolve",
    "fail_before_mutation",
    "fresh_review_code_change",
    "invalidate_drift_affected_evidence",
    "invalidate_head_bound_evidence",
    "invoke_merge_when_ready",
    "invoke_ready_to_merge",
    "make_no_code_mutation",
    "name_missing_babysit_pr",
    "perform_no_mutation",
    "preserve_artifacts",
    "preserve_feedback_gate",
    "preserve_tracker_pr_host_separation",
    "rebuild_remote_gates",
    "refresh_graph_after_merged_only",
    "reject_concurrent_mutation",
    "reject_stale_connector_verdict",
    "reject_stale_or_malformed_result",
    "report_closed_without_merge",
    "reread_live_pr",
    "retain_only_proven_unaffected_evidence",
    "retry_diagnosed_run_only",
    "revalidate_candidate_identity",
    "revalidate_commit_push",
    "route_before_ticket_dependencies",
    "ticket_scoped_fix",
    "transfer_exclusive_mutation_ownership",
    "verify_merge_live",
    "verify_non_merge_gates",
)


def build_prompt(payload: dict) -> str:
    return "\n".join(
        [
            "You are the runtime executing the agent skill below for one",
            "scenario. Decide how a fully compliant runtime must terminate",
            "and which obligations apply. Do not perform any real tool",
            "actions; reason from the artifacts alone.",
            "",
            "## Skill",
            payload["skill_prompt"],
            "",
            "## Request",
            payload["request"],
            "",
            "## Granted authority (JSON)",
            json.dumps(payload.get("authority") or {}, sort_keys=True),
            "",
            "## Available capabilities (JSON)",
            json.dumps(payload.get("capabilities") or {}, sort_keys=True),
            "",
            "## Scenario artifacts (JSON)",
            json.dumps(payload["artifacts"], indent=2, sort_keys=True),
            "",
            "## Answer format",
            "Return ONLY one JSON object, no prose and no code fence:",
            '{"target_skill": "' + payload["target_skill"] + '",',
            ' "terminal_state": <one of ' + json.dumps(list(TERMINAL_STATES)) + ">,",
            ' "actions": <every applicable value from this closed vocabulary>}',
            json.dumps(list(ACTION_VOCABULARY), indent=2),
        ]
    )


def extract_json_object(text: str) -> dict:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("executor model returned no JSON object")
    return json.loads(candidate[start : end + 1])


def run_claude(prompt: str, claude_bin: str, model: str | None) -> dict:
    command = [claude_bin, "-p", "--output-format", "json"]
    if model:
        command.extend(["--model", model])
    completed = subprocess.run(
        command,
        input=prompt,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(
            f"claude exited {completed.returncode}: {completed.stderr.strip()}"
        )
    envelope = json.loads(completed.stdout)
    result_text = envelope.get("result")
    if not isinstance(result_text, str):
        raise RuntimeError("claude --output-format json returned no result text")
    return extract_json_object(result_text)


def normalize(payload: dict, observed: dict) -> dict:
    actions = observed.get("actions")
    if not isinstance(actions, list):
        actions = []
    return {
        "target_skill": observed.get("target_skill") or payload["target_skill"],
        "terminal_state": observed.get("terminal_state"),
        "actions": sorted(
            {str(action) for action in actions if str(action) in ACTION_VOCABULARY}
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claude-bin", default="claude")
    parser.add_argument(
        "--model",
        default=None,
        help="Optional model override passed to `claude --model`",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = json.load(sys.stdin)
    observed = run_claude(build_prompt(payload), args.claude_bin, args.model)
    json.dump(normalize(payload, observed), sys.stdout, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
