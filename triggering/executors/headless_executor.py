#!/usr/bin/env python3
"""Primary tier: observe which skill a real headless session actually loads.

Where the `description` tier asks a model to reason about a catalog, this tier
runs the prompt through the headless CLI against an isolated skill
configuration and reads which skill the session reports invoking. That is the
behavior the corpus is ultimately about — routing as it happens, not routing as
a model describes it.

Whether headless output reliably reports skill invocation is unverified harness
behavior. Issue #136 records that as the reason the `description` tier applies
to the whole runner rather than only to collisions. When this executor cannot
establish which skill was invoked, it fails loudly rather than reporting `none`:
an unobservable invocation is missing evidence, and recording it as "no skill
triggered" would silently pass every negative case.

Requires the `claude` CLI on PATH. Reads one result-blind packet on stdin,
writes one JSON object on stdout.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys


def run_headless(prompt: str, claude_bin: str, model: str | None) -> dict:
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
    return json.loads(completed.stdout)


def invoked_skill(envelope: dict, known: set[str]) -> str | None:
    """Read the invoked skill from the session envelope.

    Returns the skill name, or None only when the envelope positively reports
    that no skill was used. Raises when invocation cannot be determined at all,
    which is the unverified-harness-behavior case.
    """
    for key in ("skills_used", "skills", "invoked_skills"):
        reported = envelope.get(key)
        if isinstance(reported, list):
            named = [entry for entry in reported if entry in known]
            if named:
                return named[0]
            return None
    raise RuntimeError(
        "headless output reported no skill-invocation field; this tier cannot "
        "establish which skill was loaded, so the description tier applies"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claude-bin", default="claude")
    parser.add_argument("--model", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = json.load(sys.stdin)
    known = {entry["skill"] for entry in payload["catalog"]}
    envelope = run_headless(payload["prompt"], args.claude_bin, args.model)
    json.dump(
        {
            "selected_skill": invoked_skill(envelope, known),
            "tier": "headless",
            "repetitions": 1,
            "agreement": 1.0,
        },
        sys.stdout,
        sort_keys=True,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
