"""Corpus contract, separation, and audit tests for the replay evaluator."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from evals import audit_corpus, corpus, grader, protocol  # noqa: E402

AUDIT_SCRIPT = SCRIPTS_DIR / "evals" / "audit_corpus.py"


class LayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = corpus.load_corpus()

    def test_reviewer_and_private_data_live_in_separate_trees(self):
        root = self.corpus.root
        for case in self.corpus.cases:
            with self.subTest(case=case.case_id):
                self.assertTrue(
                    (root / "reviewer" / case.case_id / "packet.json").is_file()
                )
                self.assertTrue(
                    (
                        root / "private" / "expectations" / f"{case.case_id}.json"
                    ).is_file()
                )
                self.assertTrue(
                    (root / "private" / "provenance" / f"{case.case_id}.json").is_file()
                )

    def test_no_private_file_sits_inside_the_reviewer_tree(self):
        reviewer_files = {
            path.name
            for path in (self.corpus.root / "reviewer").rglob("*")
            if path.is_file()
        }
        self.assertEqual({"PROMPT.md", "packet.json"}, reviewer_files)

    def test_case_ids_and_reviewer_filenames_hide_the_outcome(self):
        for case in self.corpus.cases:
            with self.subTest(case=case.case_id):
                self.assertEqual([], corpus.revealing_tokens(case.case_id))
                for path in (self.corpus.root / "reviewer" / case.case_id).iterdir():
                    self.assertEqual([], corpus.revealing_tokens(path.name))

    def test_reviewer_prompt_names_no_verdict_or_severity(self):
        self.assertEqual([], corpus.prompt_errors(self.corpus.root))

    def test_corpus_declares_the_shipped_grader_and_protocol_versions(self):
        self.assertEqual(grader.GRADER_VERSION, self.corpus.grader_version)
        index = json.loads((self.corpus.root / "corpus.json").read_text())
        self.assertEqual(protocol.PROTOCOL_VERSION, index["protocol_version"])

    def test_every_case_diff_is_a_parseable_patch(self):
        for case in self.corpus.cases:
            with self.subTest(case=case.case_id):
                completed = subprocess.run(
                    ["git", "apply", "--numstat"],
                    input=case.packet["candidate"]["diff"]["content"],
                    capture_output=True,
                    check=False,
                    text=True,
                )
                self.assertEqual(0, completed.returncode, completed.stderr)

    def test_the_corpus_covers_every_grading_situation_it_must_prove(self):
        verdicts = {case.expectation["expected_verdict"] for case in self.corpus.cases}
        self.assertEqual({"changes_required", "clean", "blocked"}, verdicts)
        self.assertTrue(
            any(case.expectation["accepted_non_findings"] for case in self.corpus.cases)
        )
        self.assertTrue(
            any(
                len(case.expectation["material_root_causes"]) > 1
                for case in self.corpus.cases
            )
        )


class PackagingBoundaryTests(unittest.TestCase):
    """A distributed skill bundle must never carry grading evidence."""

    def test_no_skill_bundles_any_corpus_expectation_or_provenance(self):
        private_names = {
            path.name for path in (corpus.DEFAULT_CORPUS / "private").rglob("*.json")
        }
        self.assertTrue(private_names)
        bundled = {
            path.name
            for path in (SCRIPTS_DIR.parents[1] / "skills").rglob("*")
            if path.is_file()
        }
        self.assertEqual(set(), private_names & bundled)

    def test_no_skill_bundles_the_evaluator_or_its_reviewer_artifacts(self):
        skills = SCRIPTS_DIR.parents[1] / "skills"
        for name in ("runner.py", "audit_corpus.py", "corpus.json"):
            with self.subTest(name=name):
                self.assertEqual([], list(skills.rglob(f"**/review-suite/{name}")))


class MutatedCorpusTests(unittest.TestCase):
    """Every check must actually fail on a corpus that violates it."""

    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.root = self.temp / "corpus"
        shutil.copytree(corpus.DEFAULT_CORPUS, self.root)
        self.addCleanup(shutil.rmtree, self.temp, ignore_errors=True)

    def _index(self):
        return json.loads((self.root / "corpus.json").read_text())

    def _write_index(self, index):
        (self.root / "corpus.json").write_text(json.dumps(index, indent=2))

    def _expectation_path(self, case_id):
        return self.root / "private" / "expectations" / f"{case_id}.json"

    def _load_expectation(self, case_id):
        return json.loads(self._expectation_path(case_id).read_text())

    def _write_expectation(self, case_id, document):
        self._expectation_path(case_id).write_text(json.dumps(document, indent=2))

    def assertAuditFails(self, fragment):
        errors = audit_corpus.audit(self.root)
        self.assertTrue(errors, "expected the audit to reject this corpus")
        self.assertTrue(
            any(fragment in error for error in errors),
            f"no error mentioned {fragment!r}: {errors}",
        )

    def test_missing_expectation_fails_before_any_launch(self):
        case_id = self._index()["cases"][0]
        self._expectation_path(case_id).unlink()
        self.assertAuditFails("missing")

    def test_missing_provenance_fails(self):
        case_id = self._index()["cases"][0]
        (self.root / "private" / "provenance" / f"{case_id}.json").unlink()
        self.assertAuditFails("missing")

    def test_schema_violation_fails(self):
        case_id = self._index()["cases"][0]
        expectation = self._load_expectation(case_id)
        expectation["expected_verdict"] = "probably_fine"
        self._write_expectation(case_id, expectation)
        self.assertAuditFails("expected_verdict")

    def test_provenance_without_retention_authority_fails(self):
        case_id = self._index()["cases"][0]
        path = self.root / "private" / "provenance" / f"{case_id}.json"
        document = json.loads(path.read_text())
        del document["retention_authority"]
        path.write_text(json.dumps(document, indent=2))
        self.assertAuditFails("retention_authority")

    def test_gating_expectation_without_a_root_cause_fails(self):
        case_id = next(
            item
            for item in self._index()["cases"]
            if self._load_expectation(item)["expected_verdict"] == "changes_required"
        )
        expectation = self._load_expectation(case_id)
        expectation["material_root_causes"] = []
        self._write_expectation(case_id, expectation)
        self.assertAuditFails("at least one material root cause")

    def test_outcome_revealing_case_id_fails(self):
        index = self._index()
        old = index["cases"][0]
        new = "clean-control-case"
        index["cases"][0] = new
        self._write_index(index)
        (self.root / "reviewer" / old).rename(self.root / "reviewer" / new)
        for area in ("expectations", "provenance"):
            path = self.root / "private" / area / f"{old}.json"
            document = json.loads(path.read_text())
            document["case_id"] = new
            path.rename(self.root / "private" / area / f"{new}.json")
            (self.root / "private" / area / f"{new}.json").write_text(
                json.dumps(document, indent=2)
            )
        self.assertAuditFails("reveals outcome")

    def test_outcome_revealing_reviewer_filename_fails(self):
        case_id = self._index()["cases"][0]
        (self.root / "reviewer" / case_id / "expected.json").write_text("{}")
        self.assertAuditFails("unpermitted reviewer-visible file")

    def test_expectation_copied_into_the_reviewer_tree_fails(self):
        case_id = self._index()["cases"][0]
        shutil.copyfile(
            self._expectation_path(case_id),
            self.root / "reviewer" / case_id / "notes.json",
        )
        self.assertAuditFails("unpermitted reviewer-visible file")

    def test_leaked_root_cause_text_in_a_packet_fails(self):
        case_id = next(
            item
            for item in self._index()["cases"]
            if self._load_expectation(item)["material_root_causes"]
        )
        expectation = self._load_expectation(case_id)
        leak = expectation["material_root_causes"][0]["consequence"]
        packet_path = self.root / "reviewer" / case_id / "packet.json"
        packet = json.loads(packet_path.read_text())
        packet["change_contract"]["non_goals"].append(leak)
        packet_path.write_text(json.dumps(packet, indent=2))
        self.assertAuditFails("private expectation text")

    def test_undeclared_case_directory_fails(self):
        (self.root / "reviewer" / "surprise-topic").mkdir()
        self.assertAuditFails("not declared in corpus.json")

    def test_undeclared_expectation_file_fails(self):
        (self.root / "private" / "expectations" / "surprise-topic.json").write_text(
            "{}"
        )
        self.assertAuditFails("is not declared")

    def test_packet_validity_disagreement_fails(self):
        case_id = next(
            item
            for item in self._index()["cases"]
            if self._load_expectation(item)["expected_verdict"] == "blocked"
        )
        expectation = self._load_expectation(case_id)
        expectation["packet_valid"] = True
        expectation["expected_verdict"] = "clean"
        self._write_expectation(case_id, expectation)
        self.assertAuditFails("packet:")

    def test_a_missing_declared_dependency_fails(self):
        index = self._index()
        index["target_skill_dependencies"].append("review-nothing-at-all")
        self._write_index(index)
        self.assertAuditFails("missing declared skill")

    def test_a_missing_target_skill_fails(self):
        index = self._index()
        index["target_skill"] = "review-nothing-at-all"
        self._write_index(index)
        self.assertAuditFails("missing declared skill")

    def test_a_target_listing_itself_as_a_dependency_fails(self):
        index = self._index()
        index["target_skill_dependencies"].append(index["target_skill"])
        self._write_index(index)
        self.assertAuditFails("lists itself as a dependency")

    def test_duplicate_declared_dependencies_fail(self):
        index = self._index()
        index["target_skill_dependencies"].append(index["target_skill_dependencies"][0])
        self._write_index(index)
        self.assertAuditFails("duplicate target_skill_dependencies")

    def test_an_absent_dependency_declaration_fails(self):
        index = self._index()
        del index["target_skill_dependencies"]
        self._write_index(index)
        self.assertAuditFails("target_skill_dependencies")

    def test_grader_version_drift_fails(self):
        index = self._index()
        index["grader_version"] = "0.0"
        self._write_index(index)
        self.assertAuditFails("does not match the shipped grader")

    def test_reviewer_prompt_naming_a_verdict_fails(self):
        prompt = self.root / "reviewer" / "PROMPT.md"
        prompt.write_text(
            prompt.read_text() + "\nReturn clean when nothing is wrong.\n"
        )
        self.assertAuditFails("names verdict or severity word")


class AuditCommandTests(unittest.TestCase):
    def test_audit_passes_on_the_shipped_corpus(self):
        self.assertEqual([], audit_corpus.audit(None))

    def test_audit_script_exits_zero_without_launching_a_runtime(self):
        completed = subprocess.run(
            [sys.executable, str(AUDIT_SCRIPT)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn("corpus audit passed", completed.stdout)

    def test_audit_script_reports_a_missing_corpus(self):
        completed = subprocess.run(
            [sys.executable, str(AUDIT_SCRIPT), "--corpus", "/nonexistent/corpus"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(1, completed.returncode)
        self.assertIn("missing corpus directory", completed.stderr)


if __name__ == "__main__":
    unittest.main()
