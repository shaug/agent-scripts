"""Verify skill-bundled review-suite contract copies match the canonical source.

Each review skill bundles the canonical contract and schemas under
`references/review-suite/` so the skill remains self-contained when installed
outside this repository. `just sync-contracts` refreshes the copies; this test
fails when any copy drifts from the canonical file.
"""

from __future__ import annotations

import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
REVIEW_SUITE = REPOSITORY_ROOT / "review-suite"
BUNDLING_SKILLS = (
    "review-code-change",
    "review-correctness",
    "review-code-simplicity",
    "review-solution-simplicity",
)
CANONICAL_FILES = {
    "CONTRACT.md": REVIEW_SUITE / "CONTRACT.md",
    "review-packet.schema.json": REVIEW_SUITE
    / "contracts"
    / "review-packet.schema.json",
    "review-result.schema.json": REVIEW_SUITE
    / "contracts"
    / "review-result.schema.json",
}


class BundledContractTests(unittest.TestCase):
    def test_every_review_skill_bundles_identical_contract_copies(self):
        for skill in BUNDLING_SKILLS:
            bundle = REPOSITORY_ROOT / "skills" / skill / "references" / "review-suite"
            for name, canonical in CANONICAL_FILES.items():
                bundled = bundle / name
                with self.subTest(skill=skill, file=name):
                    self.assertTrue(
                        bundled.exists(),
                        f"{bundled} is missing; run `just sync-contracts`",
                    )
                    self.assertEqual(
                        canonical.read_bytes(),
                        bundled.read_bytes(),
                        f"{bundled} drifted from {canonical}; "
                        "run `just sync-contracts`",
                    )


if __name__ == "__main__":
    unittest.main()
