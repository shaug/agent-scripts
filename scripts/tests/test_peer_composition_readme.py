"""Contract invariants for the README's "Using beside peer skills" section.

Checks stable identifiers only — the five composition rules, the seam table's
ticket references, and the planned/landed markers — not phrasing. The section
makes claims about peer behavior and about which seams exist, and both go stale
silently, so the assertions here are the only thing that fails when they do.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
README = REPOSITORY_ROOT / "README.md"

# Seams whose ticket has merged, and seams that have not. A seam moving between
# these tuples is the edit this module exists to force.
LANDED_SEAM_TICKETS = ("#124", "#125", "#126", "#127", "#128")
PLANNED_SEAM_TICKETS = ("#131", "#134")


def compact(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def last_cell(row: str) -> str:
    """The table's status column, with mdformat's column padding removed."""
    return [cell.strip() for cell in row.strip().strip("|").split("|")][-1]


class PeerCompositionSectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        text = README.read_text()
        cls.section = text.split("## Using beside peer skills", 1)[1].split("\n## ", 1)[
            0
        ]
        cls.compact = compact(cls.section)

    def test_the_section_exists_with_its_division_of_labor(self):
        self.assertIn("Division of labor", self.compact)
        self.assertIn("Peers own in-phase methodology", self.compact)
        self.assertIn("Awareness mechanism", self.compact)
        self.assertIn("no install probe", self.compact)
        self.assertIn("never a `blocked` condition", self.compact)

    def test_all_five_composition_rules_are_present(self):
        for rule in (
            "satisfies brainstorming's design-approval gate",
            "Exactly one executor owns a unit of work",
            "Review production is house-owned inside the pipeline",
            "Only the pull-request option composes at the merge boundary",
            "Known overlaps are documented, not dodged",
        ):
            self.assertIn(rule, self.compact)

    def test_every_rule_states_its_rationale(self):
        self.assertEqual(5, self.compact.count("*Why:*"))

    def test_the_merge_boundary_matches_the_peers_three_option_menu(self):
        self.assertIn(
            "merge locally, push and create a pull request, or keep the branch",
            self.compact,
        )
        self.assertIn("only the pull-request option composes", self.compact)

    def test_the_guarantee_of_standalone_function_is_stated(self):
        self.assertIn("Nothing here degrades when a peer is absent", self.compact)

    def test_the_seam_table_marks_landed_and_planned_seams(self):
        for ticket in LANDED_SEAM_TICKETS:
            self.assertIn(f"issues/{ticket.lstrip('#')})", self.section, ticket)
        for ticket in PLANNED_SEAM_TICKETS:
            self.assertIn(f"issues/{ticket.lstrip('#')})", self.section, ticket)
        # Every table row ends in exactly one status marker.
        rows = [
            line
            for line in self.section.splitlines()
            if line.startswith("| ") and "issues/" in line
        ]
        self.assertGreaterEqual(len(rows), 9)
        for row in rows:
            with self.subTest(row=row[:60]):
                self.assertIn(
                    last_cell(row),
                    ("Landed", "Planned"),
                    "each seam row must end in a Landed or Planned marker",
                )

    def test_no_unlanded_seam_is_described_without_a_planned_marker(self):
        for line in self.section.splitlines():
            if not (line.startswith("| ") and "issues/" in line):
                continue
            for ticket in PLANNED_SEAM_TICKETS:
                if f"issues/{ticket.lstrip('#')})" in line:
                    with self.subTest(ticket=ticket):
                        self.assertEqual(
                            "Planned",
                            last_cell(line),
                            f"{ticket} has not landed and must be marked Planned",
                        )

    def test_the_unmeasured_overlap_audit_carries_its_planned_marker(self):
        self.assertIn("planned in", self.compact)
        self.assertIn("issues/136", self.section)
        self.assertIn("records reasoning rather than measurement", self.compact)

    def test_the_registry_is_named_as_the_authority(self):
        self.assertIn("docs/skill-authoring.md", self.section)
        self.assertIn(
            "is the authority when this summary and the registry disagree",
            self.compact,
        )


if __name__ == "__main__":
    unittest.main()
