#!/usr/bin/env python3
"""Fallback tier: ask a model which skill a prompt triggers, from descriptions alone.

The model sees the catalog of skill descriptions and one prompt, and answers
with the skill it would route to, or `none`. It never sees the expected answer,
the case's kind, or which skill the case was filed under.

This tier exists because the primary `headless` tier depends on unverified
harness behavior — whether headless CLI output reliably reports which skill was
invoked. Per issue #136 the fallback therefore applies to the whole runner, not
only to cross-collision cases.

Following the micro-test protocol in `docs/skill-authoring.md`, each prompt is
asked `--repetitions` times (default 5) in independent processes, the majority
answer wins, and the agreement fraction is recorded so a 3/5 result is never
reported as though it were 5/5.

Requires the `claude` CLI on PATH. Reads one result-blind packet on stdin,
writes one JSON object on stdout.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter

NONE_ANSWER = "none"


def build_prompt(payload: dict) -> str:
    catalog = "\n\n".join(
        f"- {entry['skill']}: {entry['description']}" for entry in payload["catalog"]
    )
    names = ", ".join(entry["skill"] for entry in payload["catalog"])
    return "\n".join(
        [
            "You are the router that decides which skill, if any, a user's",
            "request should load. Below is the complete catalog of available",
            "skills with their trigger descriptions, followed by one user",
            "request.",
            "",
            "## Catalog",
            catalog,
            "",
            "## User request",
            payload["prompt"],
            "",
            "## Answer format",
            f"Reply with exactly one name from this list: {names}, or the word",
            f"'{NONE_ANSWER}' if no skill in the catalog should be loaded.",
            "Reply with the bare name and nothing else — no prose, no punctuation.",
        ]
    )


def run_claude(prompt: str, claude_bin: str, model: str | None) -> str:
    command = [claude_bin, "-p", "--output-format", "json"]
    if model:
        command.extend(["--model", model])
    completed = subprocess.run(
        command, input=prompt, text=True, capture_output=True, check=False
    )
    if completed.returncode:
        raise RuntimeError(
            f"claude exited {completed.returncode}: {completed.stderr.strip()}"
        )
    envelope = json.loads(completed.stdout)
    result = envelope.get("result")
    if not isinstance(result, str):
        raise RuntimeError("claude --output-format json returned no result text")
    return result


def parse_answer(text: str, known: set[str]) -> str | None:
    """Map a model reply onto a catalog name or None, without guessing."""
    cleaned = re.sub(r"[^a-z0-9:_-]+", " ", text.strip().lower()).strip()
    for token in cleaned.split():
        if token in known:
            return token
        if token == NONE_ANSWER:
            return None
    # A reply naming nothing recognisable is not evidence of "no skill"; it is
    # an unusable answer, and recording it as `none` would silently convert a
    # broken response into a passing negative case.
    raise RuntimeError(f"unrecognised router answer: {text.strip()[:200]!r}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claude-bin", default="claude")
    parser.add_argument("--model", default=None)
    parser.add_argument("--repetitions", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = json.load(sys.stdin)
    known = {entry["skill"] for entry in payload["catalog"]}
    prompt = build_prompt(payload)

    answers: list[str | None] = []
    for _ in range(args.repetitions):
        answers.append(
            parse_answer(run_claude(prompt, args.claude_bin, args.model), known)
        )

    votes = Counter(answer or NONE_ANSWER for answer in answers)
    winner, count = votes.most_common(1)[0]
    json.dump(
        {
            "selected_skill": None if winner == NONE_ANSWER else winner,
            "tier": "description",
            "repetitions": args.repetitions,
            "agreement": count / args.repetitions,
            "votes": dict(votes),
        },
        sys.stdout,
        sort_keys=True,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
