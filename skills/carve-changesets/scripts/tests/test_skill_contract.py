"""Load-bearing contract invariants for the carve-changesets skill prose.

Checks stable identifiers only — bundled file layout and the named consumption
disciplines its review communication runs on — not phrasing. Mechanics are
covered by the sibling modules in this directory.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]


def compact(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


class CarveChangesetsContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = compact((SKILL_ROOT / "SKILL.md").read_text())

    def test_review_communication_references_the_bundled_disciplines(self):
        self.assertIn("consumption-disciplines.md", self.skill)
        self.assertIn("Review communication runs on", self.skill)

    def test_the_four_disciplines_are_named_at_the_seam(self):
        for discipline in (
            "verify each finding against the codebase before implementing it",
            "clarify every unclear finding before implementing any",
            "never perform agreement in a reply",
            "implement blocking before simple before complex",
        ):
            self.assertIn(discipline, self.skill)

    def test_changeset_review_dispatch_carries_integrity_tier_and_turn_count(self):
        self.assertIn("receives evidence and contracts, never conclusions", self.skill)
        self.assertIn("stop and rewrite it", self.skill)
        self.assertIn("returns confirmation, not review", self.skill)
        self.assertIn("capability tier adequate for judgment", self.skill)
        self.assertIn("Prefer one well-briefed review per changeset", self.skill)

    def test_tier_guidance_names_no_product_or_model(self):
        for banned in ("gpt", "claude-", "opus", "sonnet", "haiku", "gemini"):
            self.assertNotIn(banned, self.skill.lower())

    def test_the_bundled_copy_exists(self):
        self.assertTrue(
            (
                SKILL_ROOT
                / "references"
                / "review-suite"
                / "consumption-disciplines.md"
            ).is_file()
        )


if __name__ == "__main__":
    unittest.main()
