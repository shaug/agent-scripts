"""Load-bearing contract invariants for the babysit-pr skill.

These tests intentionally check only stable identifiers — skill names,
terminal states, policy tokens, dependency names, file layout, and
neutrality — not prose phrasing. Behavior is covered by
test_gh_pr_watch.py and the evaluation data under evals/.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = SKILL_ROOT.parents[1]


def read(relative_path):
    return (SKILL_ROOT / relative_path).read_text()


def compact(value):
    return re.sub(r"\s+", " ", value).strip()


class BabysitPrContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = read("SKILL.md")
        cls.github = read("references/github.md")
        cls.decisions = read("references/ci-and-feedback.md")
        cls.upstream = read("references/upstream.md")
        cls.watcher = read("scripts/gh_pr_watch.py")
        cls.contract = compact(cls.skill + cls.github + cls.decisions)
        cls.cases = {item["id"]: item for item in json.loads(read("evals/cases.json"))}
        cls.expectations = {
            item["case_id"]: item
            for item in json.loads(read("evals/expectations.json"))
        }

    def test_frontmatter_and_runtime_neutral_contract(self):
        self.assertTrue(self.skill.startswith("---\nname: babysit-pr\n"))
        self.assertNotIn("Codex", self.contract)
        self.assertNotIn("REVIEW_BOT_LOGIN_KEYWORDS", self.watcher)
        self.assertNotIn("/tmp/codex", self.watcher)

    def test_re_review_dispatch_carries_integrity_tier_and_turn_count(self):
        skill = compact(self.skill)
        self.assertIn(
            "The reviewer receives evidence and contracts, never conclusions", skill
        )
        self.assertIn("stop and rewrite it", skill)
        self.assertIn("returns confirmation, not review", skill)
        self.assertIn("capability tier adequate for judgment", skill)
        self.assertIn("Prefer one well-briefed re-review", skill)

    def test_tier_guidance_names_no_product_or_model(self):
        for banned in ("gpt", "claude-", "opus", "sonnet", "haiku", "gemini"):
            self.assertNotIn(banned, compact(self.skill).lower())

    def test_completion_policies_and_terminal_states_are_stable(self):
        for policy in (
            "ready_to_merge",
            "merge_when_ready",
            "watch_until_closed",
        ):
            self.assertIn(policy, self.contract)
            self.assertIn(policy, self.watcher)
        for state in ("ready_to_merge", "merged", "closed", "blocked"):
            self.assertIn(state, self.skill)

    def test_review_dependency_is_repository_owned(self):
        self.assertIn("review-code-change", self.contract)

    def test_watcher_paths_are_skill_relative(self):
        self.assertNotIn("skills/babysit-pr/scripts", self.skill)
        self.assertNotIn("skills/babysit-pr/scripts", self.github)
        self.assertIn("scripts/gh_pr_watch.py", self.skill)

    def test_upstream_is_pinned_and_licensed(self):
        self.assertIn("a770e5b8470d3320eb53a56a286ea4a0a70a1f59", self.upstream)
        self.assertIn("Apache License 2.0", self.upstream)
        self.assertTrue((SKILL_ROOT / "LICENSE.apache-2.0").is_file())
        self.assertNotIn("raw.githubusercontent.com", self.watcher)

    def test_eval_cases_and_expectations_stay_paired(self):
        self.assertTrue(self.cases)
        self.assertEqual(set(self.cases), set(self.expectations))

    def test_eval_expectations_preserve_authority_boundaries(self):
        self.assertEqual(
            "ready_to_merge",
            self.expectations["ready-without-merge"]["terminal_state"],
        )
        self.assertEqual(
            "merged", self.expectations["authorized-merge"]["terminal_state"]
        )
        self.assertEqual(
            "closed", self.expectations["closed-without-merge"]["terminal_state"]
        )
        self.assertEqual(
            "blocked", self.expectations["missing-capability"]["terminal_state"]
        )

    def test_review_result_contract_violations_block_the_final_gate(self):
        for case_id in (
            "stale-review-schema-version-blocks-final-gate",
            "malformed-review-result-blocks-final-gate",
            "green-ci-alone-insufficient-without-valid-review",
        ):
            self.assertEqual("blocked", self.expectations[case_id]["terminal_state"])
        self.assertIn("references/review-suite/CONTRACT.md", self.contract)
        self.assertIn("scripts/review_gate.py", self.contract)
        self.assertIn("schema_version", self.decisions + self.skill)
        self.assertIn(
            "never satisfied by green CI or connector approval alone", self.contract
        )

    def test_runtime_adapters_exist_for_both_products(self):
        self.assertIn('display_name: "Babysit PR"', read("agents/openai.yaml"))
        self.assertIn("Claude Code adapter", read("agents/claude-code.md"))


class ConsumptionDisciplineTests(unittest.TestCase):
    """The feedback loop metabolizes findings through the bundled disciplines."""

    @classmethod
    def setUpClass(cls):
        cls.skill = compact(read("SKILL.md"))

    def test_feedback_loop_references_the_bundled_disciplines(self):
        self.assertIn("consumption-disciplines.md", self.skill)
        self.assertTrue(
            (
                SKILL_ROOT
                / "references"
                / "review-suite"
                / "consumption-disciplines.md"
            ).is_file()
        )

    def test_replies_never_perform_agreement(self):
        self.assertIn("never perform agreement", self.skill)
        self.assertIn(
            "no thanks, no praise for the catch, no affirming a finding before "
            "checking it",
            self.skill,
        )

    def test_unclear_feedback_is_clarified_before_any_fix_is_pushed(self):
        self.assertIn(
            "Clarify every unclear finding in-thread before pushing any fix",
            self.skill,
        )

    def test_accepted_findings_are_ordered_and_validated_individually(self):
        self.assertIn(
            "blocking first, then simple, then complex, validating each on its own",
            self.skill,
        )

    def test_systematic_debugging_is_availability_conditioned_with_silent_fallback(
        self,
    ):
        self.assertIn(
            "`superpowers:systematic-debugging` is available in the session skill "
            "listing",
            self.skill,
        )
        self.assertIn(
            "When the peer is not in the listing, diagnose from logs and evidence "
            "without comment",
            self.skill,
        )
        self.assertIn("blocked-with-evidence terminal", self.skill)
        # The peer must not appear in any fail-closed capability requirement.
        capabilities = self.skill.split("## Require compatible capabilities", 1)[1]
        capabilities = capabilities.split("##", 1)[0]
        self.assertNotIn("systematic-debugging", capabilities)

    def test_rationalization_table_covers_the_certified_seed_entries(self):
        for rationalization in (
            "The fix was trivial, re-validation can be skipped",
            "This CI failure looks flaky",
        ):
            self.assertIn(rationalization, self.skill)
        self.assertIn(
            "invalidate and rebuild every affected head-bound gate", self.skill
        )
        self.assertIn(
            "Do not call a failure flaky merely because a rerun might be convenient",
            compact(read("references/ci-and-feedback.md")),
        )


if __name__ == "__main__":
    unittest.main()
