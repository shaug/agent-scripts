from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = SKILL_ROOT.parents[1]


def read(path: Path) -> str:
    return path.read_text()


def compact(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


class ImplementTicketContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = read(SKILL_ROOT / "SKILL.md")
        cls.github = read(SKILL_ROOT / "references" / "github.md")
        cls.linear = read(SKILL_ROOT / "references" / "linear.md")
        cls.gates = read(SKILL_ROOT / "references" / "review-and-merge-gates.md")
        cls.handoff = read(SKILL_ROOT / "references" / "babysit-pr-handoff.md")
        cls.result = read(SKILL_ROOT / "references" / "cleanup-and-result.md")
        cls.babysit_skill = read(REPOSITORY_ROOT / "skills" / "babysit-pr" / "SKILL.md")
        cls.babysit_ci = read(
            REPOSITORY_ROOT
            / "skills"
            / "babysit-pr"
            / "references"
            / "ci-and-feedback.md"
        )
        cls.skill_compact = compact(cls.skill)
        cls.github_compact = compact(cls.github)
        cls.linear_compact = compact(cls.linear)
        cls.gates_compact = compact(cls.gates)
        cls.handoff_compact = compact(cls.handoff)
        cls.result_compact = compact(cls.result)
        cls.eval_contract = compact(
            read(SKILL_ROOT / "evals" / "cases.json")
            + read(SKILL_ROOT / "evals" / "results.json")
        )
        cls.all_contract = compact(
            cls.skill + cls.github + cls.linear + cls.gates + cls.handoff + cls.result
        )
        cls.cases = {
            item["id"]: item
            for item in json.loads(read(SKILL_ROOT / "evals" / "cases.json"))
        }
        cls.results = {
            item["case_id"]: item
            for item in json.loads(read(SKILL_ROOT / "evals" / "results.json"))
        }

    def test_frontmatter_and_product_neutral_contract(self):
        self.assertTrue(self.skill.startswith("---\nname: implement-ticket\n"))
        self.assertNotIn("Codex", self.all_contract)
        self.assertNotIn("OpenAI", self.all_contract)
        self.assertNotIn("Codex", self.eval_contract)
        self.assertNotIn("OpenAI", self.eval_contract)
        self.assertNotIn("code-review-pro", self.all_contract)
        self.assertIn("compatible agentic runtime", self.skill)
        self.assertIn(
            "`implement-ticket`, repository-owned `review-code-change`, and repository-owned `babysit-pr` by stable skill name",
            self.skill_compact,
        )
        self.assertIn(
            "worker and subagent describe possible isolated execution roles",
            self.skill_compact,
        )
        self.assertIn(
            "does not constrain the operating contract",
            self.skill_compact,
        )

    def test_scope_is_exactly_one_ticket(self):
        self.assertIn("one ticket per branch, worktree, and PR", self.skill_compact)
        self.assertIn("do not select or implement it", self.skill_compact)
        self.assertIn("Never claim whole-epic acceptance", self.skill_compact)
        self.assertIn("parent and sibling context as evidence", self.skill_compact)
        self.assertIn(
            "canonical owner of generic single-ticket readiness",
            self.skill_compact,
        )
        self.assertIn(
            "`implement-epic` consumes this contract",
            self.skill_compact,
        )
        self.assertNotIn("implement-epic-sequence", self.skill_compact)

    def test_epic_routing_is_pre_mutation_and_acyclic(self):
        self.assertIn("Guard whole-epic scope before mutation", self.skill_compact)
        self.assertIn("Treat a named child of an epic", self.skill_compact)
        self.assertIn("Do not invoke or require `implement-epic`", self.skill_compact)
        self.assertIn(
            "implement-ticket:requires-epic:<tracker>:<ticket-id>",
            self.all_contract,
        )
        self.assertIn("routing cycle detected", self.all_contract)

    def test_readiness_fails_closed_without_widening_scope(self):
        self.assertIn("no unresolved native blocker", self.skill_compact)
        self.assertIn(
            "closed, canceled, or not-planned prerequisite", self.skill_compact
        )
        self.assertIn("never absorb that sibling", self.skill_compact)
        self.assertIn("require explicit ownership transfer", self.skill_compact)
        self.assertIn(
            "never claim its candidate as this run's `ready_pr`", self.github_compact
        )

    def test_authority_does_not_expand(self):
        self.assertIn("ready PR only", self.skill_compact)
        self.assertIn("merge after gates", self.skill_compact)
        self.assertIn("merge plus manual transition", self.skill_compact)
        self.assertIn(
            "parent closure always require separate explicit authority",
            self.all_contract,
        )
        self.assertIn(
            "When merge authority is unclear, stop at a ready PR", self.skill_compact
        )
        self.assertIn(
            "automatic ticket transition caused by the selected closing syntax",
            self.skill_compact,
        )
        self.assertIn(
            "disclose the consequence in the resolved completion policy",
            self.github_compact,
        )

    def test_review_and_babysit_dependencies_fail_before_mutation(self):
        self.assertIn("both `review-code-change` and `babysit-pr`", self.skill_compact)
        self.assertIn("before creating a branch, worktree", self.skill_compact)
        self.assertIn("Return `blocked` before mutation", self.skill_compact)
        self.assertIn("private PR loop", self.skill_compact)
        self.assertIn("Do not substitute another skill", self.gates_compact)
        self.assertIn(
            "fresh or minimally inherited read-only context", self.gates_compact
        )
        self.assertIn("Exclude the implementation transcript", self.gates_compact)
        self.assertIn("at most three full fix/re-review cycles", self.gates_compact)
        self.assertIn("Treat any mutation as an integrity failure", self.gates_compact)

    def test_initial_review_and_candidate_integrity_are_preserved(self):
        self.assertIn(
            "fresh or minimally inherited read-only context", self.gates_compact
        )
        self.assertIn(
            "initial review is clean for the exact live head", self.gates_compact
        )
        self.assertIn("current-candidate non-merge gate", self.handoff_compact)
        self.assertIn("Never pass expected findings", self.handoff_compact)

    def test_post_publication_lifecycle_has_one_canonical_owner(self):
        self.assertIn("sole canonical owner", self.handoff_compact)
        self.assertIn("After handoff, `babysit-pr` owns", self.handoff_compact)
        self.assertIn("Do not reproduce those mechanics", self.handoff_compact)
        self.assertIn("Diagnose CI and feedback", self.babysit_skill)
        self.assertIn("Classify CI failures", self.babysit_ci)
        self.assertNotIn("gh run rerun", self.all_contract)
        self.assertNotIn("failed-job log endpoint", self.all_contract)
        self.assertNotIn("connector feedback passes", self.all_contract)

    def test_handoff_policy_authority_and_results_are_explicit(self):
        for field in (
            "ticket identity",
            "worktree",
            "exact head SHA",
            "exact base SHA",
            "validation commands",
            "review-cycle budget",
            "exclusive mutation ownership",
        ):
            self.assertIn(field, self.handoff_compact)
        self.assertIn(
            "`ready PR only` invokes `babysit-pr` with `ready_to_merge`",
            self.handoff_compact,
        )
        self.assertIn(
            "`merge after gates` invokes it with `merge_when_ready`",
            self.handoff_compact,
        )
        self.assertIn("never uses `watch_until_closed`", self.handoff_compact)
        for source, target in (
            ("ready_to_merge", "ready_pr"),
            ("merged", "merged"),
            ("closed", "blocked"),
            ("blocked", "blocked"),
        ):
            self.assertIn(f"`{source}` maps to `{target}`", self.handoff_compact)
        self.assertIn("PR closed without merge", self.handoff_compact)

    def test_dependency_graph_is_acyclic_and_epic_is_transitive(self):
        self.assertIn("dependency graph is deliberately acyclic", self.skill_compact)
        self.assertIn(
            "`babysit-pr` must never invoke `implement-ticket`", self.skill_compact
        )
        self.assertIn("Do not re-enter this skill", self.skill_compact)

    def test_forward_evaluation_context_is_raw_and_uncontaminated(self):
        for artifact in (
            "ticket",
            "repository-instruction",
            "PR",
            "diff",
            "resulting-tree",
            "check",
            "review",
            "comment",
            "thread",
            "worktree",
        ):
            self.assertIn(artifact, self.handoff)
        self.assertIn("Exclude implementation transcripts", self.handoff)
        self.assertIn("Treat contaminated evidence as invalid", self.handoff_compact)

    def test_tracker_and_pr_host_ownership_are_separate(self):
        self.assertIn("same-numbered GitHub issue", self.github_compact)
        self.assertIn("Linear owns the ticket", self.github_compact)
        self.assertIn("Resolve repository, PR host", self.linear_compact)
        self.assertIn("Do not close or verify the parent epic", self.linear_compact)

    def test_cleanup_and_result_contract_are_complete(self):
        for state in ("ready_pr", "merged", "blocked", "requires_epic"):
            self.assertIn(state, self.result_compact)
        self.assertIn(
            "tracked, staged, unstaged, untracked, and ignored", self.result_compact
        )
        self.assertIn("Never force removal", self.result_compact)
        self.assertIn("Do not close a parent epic", self.result_compact)
        self.assertIn(
            "affected native dependency relationships were reread after the transition",
            self.result_compact,
        )
        self.assertIn("report newly unblocked work", self.github_compact)
        self.assertIn("report newly unblocked work", self.linear_compact)

    def test_forward_cases_cover_required_boundaries(self):
        required = {
            "standalone-ready-pr",
            "authorized-merge-cleanup",
            "named-epic-child-only",
            "open-native-blocker",
            "closed-prerequisite-outcome-missing",
            "sibling-outcome-missing",
            "canonical-pr-owned-elsewhere",
            "correctness-fix-and-rereview",
            "clean-local-review-remote-pending",
            "unrelated-base-drift-retained",
            "linear-ticket-github-pr",
            "epic-with-children",
            "undecomposed-epic",
            "explicit-child-not-redirected",
            "missing-implement-epic",
            "repeated-epic-handoff",
            "equivalent-isolated-context-profile",
            "missing-review-code-change",
            "missing-isolation-capability",
            "missing-asynchronous-wait",
            "missing-babysit-pr",
            "published-feedback-postfix-rereview",
            "branch-ci-postfix-rereview",
            "flaky-infrastructure-no-mutation",
            "unauthorized-human-response",
            "stale-connector-verdict",
            "relevant-base-drift-reset",
            "external-head-change",
            "closed-without-merge",
            "malformed-babysitter-result",
            "delegated-mutation-ownership",
            "resumed-pr-deduplicates",
        }
        self.assertEqual(required, set(self.cases))
        self.assertEqual(required, set(self.results))

    def test_forward_results_enforce_routing_and_authority(self):
        self.assertEqual(
            "ready_pr", self.results["standalone-ready-pr"]["terminal_state"]
        )
        self.assertEqual(
            "blocked",
            self.results["canonical-pr-owned-elsewhere"]["terminal_state"],
        )
        self.assertEqual(
            "blocked", self.results["sibling-outcome-missing"]["terminal_state"]
        )
        self.assertEqual(
            "requires_epic",
            self.results["missing-implement-epic"]["terminal_state"],
        )
        self.assertEqual(
            "blocked", self.results["repeated-epic-handoff"]["terminal_state"]
        )
        self.assertEqual(
            "ready_pr",
            self.results["equivalent-isolated-context-profile"]["terminal_state"],
        )
        for case_id in (
            "missing-review-code-change",
            "missing-babysit-pr",
            "missing-isolation-capability",
            "missing-asynchronous-wait",
        ):
            self.assertEqual("blocked", self.results[case_id]["terminal_state"])
        self.assertIn(
            "do not merge",
            self.results["clean-local-review-remote-pending"]["required_actions"],
        )
        self.assertEqual(
            "blocked", self.results["closed-without-merge"]["terminal_state"]
        )
        self.assertEqual(
            "blocked", self.results["malformed-babysitter-result"]["terminal_state"]
        )

    def test_ui_metadata_matches_skill(self):
        metadata = read(SKILL_ROOT / "agents" / "openai.yaml")
        self.assertIn('display_name: "Implement Ticket"', metadata)
        self.assertIn("$implement-ticket", metadata)


if __name__ == "__main__":
    unittest.main()
