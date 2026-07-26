#!/usr/bin/env python3
"""Audit the replay corpus without launching any model.

Checks, in order:

1. corpus index, expectation, and provenance schemas;
2. cross-field expectation semantics and packet validity agreement;
3. reviewer/private separation, orphaned files, and reviewer-prompt wording
   (all inherited from `corpus.load_corpus`, which the runner shares);
4. case identifiers and reviewer-visible filenames for outcome-revealing
   tokens; and
5. the complete executor request that each case would produce, structurally
   and textually, for private expectation or provenance leakage.

Exit status is 0 when the corpus can be trusted for a blind evaluation and 1
otherwise. This command never spawns an executor and never costs money.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from evals import corpus, grader, protocol, runner
else:
    from . import corpus, grader, protocol, runner


def audit(corpus_root: Path | None) -> list[str]:
    """Return every reason the corpus cannot be trusted, or an empty list."""
    try:
        loaded = corpus.load_corpus(corpus_root)
    except corpus.CorpusError as error:
        return [str(error)]

    # `load_corpus` already rejected an outcome-hinting reviewer prompt, so
    # every caller inherits that gate from one place.
    errors: list[str] = []
    if loaded.grader_version != grader.GRADER_VERSION:
        errors.append(
            f"corpus grader_version {loaded.grader_version!r} does not match the "
            f"shipped grader {grader.GRADER_VERSION!r}"
        )
    try:
        skill_prompt = runner.target_skill_prompt(loaded.target_skill)
    except runner.ConfigurationError as error:
        return errors + [str(error)]

    documents = runner.contract_documents()
    for case in loaded.cases:
        request = protocol.build_request(
            case_id=case.case_id,
            target_skill=loaded.target_skill,
            skill_prompt=skill_prompt,
            contract_documents=documents,
            instructions=case.instructions,
            packet=case.packet,
            run_number=1,
            suite_commit="audit",
            corpus_version=loaded.corpus_version,
            started_at="audit",
        )
        errors.extend(
            f"{case.case_id}: {error}"
            for error in protocol.audit_request(
                request,
                case_id=case.case_id,
                expectation=case.expectation,
                provenance=case.provenance,
            )
        )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=None)
    args = parser.parse_args(argv)

    errors = audit(args.corpus)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        print(f"corpus audit failed with {len(errors)} error(s)", file=sys.stderr)
        return 1
    print("corpus audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
