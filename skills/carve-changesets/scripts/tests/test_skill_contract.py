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
        cls.handoff = compact(
            (SKILL_ROOT / "references" / "review-fix-loop-handoff.md").read_text()
        )
        cls.suite_handoffs = compact(
            (SKILL_ROOT / "references" / "suite-handoffs.md").read_text()
        )

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

    def test_skill_delegates_the_per_changeset_review_and_fix_loop(self):
        self.assertIn("review-fix-loop", self.skill)
        self.assertIn("publication.policy: local_commit", self.skill)
        self.assertIn("review-fix-loop-handoff.md", self.skill)
        self.assertNotIn(
            "Construct and run the required `review-code-change`", self.skill
        )

    def test_changeset_review_dispatch_carries_integrity_tier_and_turn_count(self):
        self.assertIn(
            "receives evidence and contracts, never conclusions", self.handoff
        )
        self.assertIn("stop and rewrite it", self.handoff)
        self.assertIn("returns confirmation, not review", self.handoff)
        self.assertIn("capability tier adequate for judgment", self.handoff)
        self.assertIn("Prefer one well-briefed review per changeset", self.handoff)

    def test_handoff_sequences_invocations_in_chain_order(self):
        self.assertIn("One invocation per changeset, in chain order", self.handoff)
        self.assertIn(
            "changeset *i*'s invocation is not constructed until changeset *i - 1*'s",
            self.handoff,
        )

    def test_handoff_maps_every_terminal_state(self):
        for state in ("converged", "changes_remaining", "blocked"):
            self.assertIn(f"`{state}`", self.handoff)
        for reason in (
            "cycle_budget_exhausted",
            "scope_decision_required",
            "reviewer_integrity_failure",
        ):
            self.assertIn(reason, self.handoff)

    def test_published_pr_lifecycle_is_unchanged_and_retained(self):
        self.assertIn("babysit-pr", self.suite_handoffs)
        self.assertIn("must not run a", self.suite_handoffs)
        self.assertNotIn(
            "review-code-change` and `babysit-pr` skills", self.suite_handoffs
        )

    def test_tier_guidance_names_no_product_or_model(self):
        for banned in ("gpt", "claude-", "opus", "sonnet", "haiku", "gemini"):
            self.assertNotIn(banned, self.skill.lower())
            self.assertNotIn(banned, self.handoff.lower())

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
