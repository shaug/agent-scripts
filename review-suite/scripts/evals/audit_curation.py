#!/usr/bin/env python3
"""Audit connector-outcome curation records and promotion decisions.

Checks, in order:

1. every curation record's schema, disclosure guardrail, reviewer/private
   separation, and disposition semantics (`curation.validate_record`);
2. cross-record referential integrity for `duplicate_of` (`curation.load_records`);
3. every promotion decision's schema and cross-record rules
   (`curation.validate_promotion_decision`), including which dispositions may
   support a positive or negative case, representativeness for a global rubric
   change, and that a repository-instruction change only ever targets an
   existing repository-owned instruction file.

Exit status is 0 when every curation record and promotion decision can be
trusted and 1 otherwise. This command never scrapes GitHub, never mutates an
external review thread, and never launches a model.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from evals import curation
else:
    from . import curation


def audit(
    records_root: Path | None = None, promotions_root: Path | None = None
) -> list[str]:
    """Return every reason the curation set cannot be trusted, or an empty list."""
    try:
        record_set = curation.load_records(records_root)
    except curation.CurationError as error:
        return [str(error)]

    errors: list[str] = []
    promotions_root = (
        Path(promotions_root) if promotions_root else curation.DEFAULT_PROMOTIONS
    )
    if promotions_root.is_dir():
        for path in sorted(promotions_root.glob("*.json")):
            try:
                document = curation._load_json(path)
            except curation.CurationError as error:
                errors.append(str(error))
                continue
            errors.extend(
                f"{path.name}: {error}"
                for error in curation.validate_promotion_decision(
                    document, record_set.records
                )
            )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--records",
        type=Path,
        default=None,
        help="curation records directory (default: review-suite/evals/curation/records)",
    )
    parser.add_argument(
        "--promotions",
        type=Path,
        default=None,
        help=(
            "promotion decisions directory "
            "(default: review-suite/evals/curation/promotions)"
        ),
    )
    args = parser.parse_args(argv)

    errors = audit(args.records, args.promotions)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        print(f"curation audit failed with {len(errors)} error(s)", file=sys.stderr)
        return 1
    print("curation audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
