#!/usr/bin/env python3
"""Real-runtime replay executor backed by Claude Code headless mode.

Reads one result-blind request on stdin, asks a fresh `claude -p` process to
perform the review described by the target skill prompt and the raw packet, and
writes one protocol response on stdout. It never sees expected findings, case
names, or grader data, because the runner never puts them in the request.

Product-specific launch details stay here. The core protocol in `protocol.py`
knows nothing about Claude, so another runtime only needs its own adapter.

Usage:
    just eval-review-suite "python3 review-suite/scripts/evals/claude_executor.py"
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from evals import protocol
else:
    from . import protocol

EXECUTOR_NAME = "review-suite-claude-executor"
EXECUTOR_VERSION = "1.0"


def build_prompt(request: dict[str, Any]) -> str:
    """Render the reviewer-visible request as one headless prompt."""
    documents = "\n\n".join(
        f"### {name}\n\n{text}"
        for name, text in sorted(request["contract_documents"].items())
    )
    return "\n".join(
        [
            "You are a read-only reviewer executing the skill below for one",
            "candidate. Do not run tools, modify files, or inspect any",
            "repository. Reason only from the artifacts supplied here.",
            "",
            "## Skill",
            request["skill_prompt"],
            "",
            "## Review suite contracts",
            documents,
            "",
            "## Instructions",
            request["instructions"],
            "",
            "## Review packet (JSON)",
            json.dumps(request["packet"], indent=2, sort_keys=True),
            "",
            "## Answer format",
            "Return ONLY one JSON object conforming to",
            "review-result.schema.json, with no prose and no code fence. Bind",
            "it to this candidate identity:",
            json.dumps(request["run"]["candidate"], sort_keys=True),
        ]
    )


def extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("the runtime returned no JSON object")
    value = json.loads(candidate[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("the runtime returned a non-object JSON value")
    return value


def run_claude(
    prompt: str, *, claude_bin: str, model: str | None
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run one fresh headless process and return (review result, envelope)."""
    command = [claude_bin, "-p", "--output-format", "json"]
    if model:
        command.extend(["--model", model])
    completed = subprocess.run(
        command, input=prompt, capture_output=True, text=True, check=False
    )
    if completed.returncode:
        raise RuntimeError(
            f"{claude_bin} exited {completed.returncode}: "
            f"{completed.stderr.strip()[-500:]}"
        )
    envelope = json.loads(completed.stdout)
    if not isinstance(envelope, dict):
        raise RuntimeError("headless output was not one JSON object")
    result_text = envelope.get("result")
    if not isinstance(result_text, str):
        raise RuntimeError("headless output carried no result text")
    return extract_json_object(result_text), envelope


#: Every input-side token field the runtime reports. Under prompt caching the
#: uncached `input_tokens` count is a tiny residue - a real prompt carrying the
#: skill closure, the contracts, and a packet reports almost all of its tokens
#: as cache creation or cache read. Totalling only `input_tokens` understated a
#: measured 16456-token prompt as 2, so the cost envelope a baseline freezes
#: must be built from all three.
INPUT_TOKEN_FIELDS = (
    "input_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)


def _number(value: Any) -> float | int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def model_from(envelope: dict[str, Any]) -> str | None:
    """Resolve the model identity the runtime actually used.

    Headless output carries no top-level `model` string; it reports
    `modelUsage` as a mapping keyed by model identifier. Treating that mapping as
    a string silently dropped model identity from every recorded attempt, which
    would make a frozen baseline stratum incomparable.
    """
    model = envelope.get("model")
    if isinstance(model, str) and model.strip():
        return model
    usage_by_model = envelope.get("modelUsage")
    if isinstance(usage_by_model, dict):
        names = sorted(str(name) for name in usage_by_model if str(name).strip())
        if names:
            # More than one model can contribute to a single turn; record all.
            return ",".join(names)
    return None


def usage_from(envelope: dict[str, Any]) -> dict[str, Any] | None:
    """Map whatever usage the runtime reported into the protocol shape."""
    reported = envelope.get("usage") or {}
    usage: dict[str, Any] = {}
    if isinstance(reported, dict):
        input_values = [
            value
            for value in (_number(reported.get(field)) for field in INPUT_TOKEN_FIELDS)
            if value is not None
        ]
        if input_values:
            usage["input_tokens"] = sum(input_values)
        output = _number(reported.get("output_tokens"))
        if output is not None:
            usage["output_tokens"] = output
    cost = _number(envelope.get("total_cost_usd"))
    if cost is not None:
        usage["cost_usd"] = cost
    return usage or None


def respond(request: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    executor = {
        "name": EXECUTOR_NAME,
        "version": EXECUTOR_VERSION,
        "runtime": Path(args.claude_bin).name,
    }
    if args.model:
        executor["model"] = args.model
    try:
        result, envelope = run_claude(
            build_prompt(request), claude_bin=args.claude_bin, model=args.model
        )
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        return {
            "protocol_version": protocol.PROTOCOL_VERSION,
            "outcome": "runtime_failure",
            "simulation": False,
            "executor": executor,
            "failure": {"reason": str(error)},
        }

    # Required identity, so fail closed rather than record an attempt that
    # cannot say which model answered. `--model` is an acceptable source; a
    # silently absent model is not.
    resolved_model = model_from(envelope) or args.model
    if not resolved_model:
        return {
            "protocol_version": protocol.PROTOCOL_VERSION,
            "outcome": "runtime_failure",
            "simulation": False,
            "executor": executor,
            "failure": {
                "reason": (
                    "the runtime reported no model identity; refusing to record "
                    "an attempt that cannot name the model that answered"
                )
            },
        }
    executor["model"] = resolved_model
    response: dict[str, Any] = {
        "protocol_version": protocol.PROTOCOL_VERSION,
        "outcome": "blocked" if result.get("verdict") == "blocked" else "review_result",
        "simulation": False,
        "executor": executor,
        "result": result,
    }
    usage = usage_from(envelope)
    if usage:
        response["usage"] = usage
    return response


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claude-bin", default="claude")
    parser.add_argument("--model", default=None)
    args = parser.parse_args(argv)
    protocol.write_response(respond(protocol.read_request(), args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
