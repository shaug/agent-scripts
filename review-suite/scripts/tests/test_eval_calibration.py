"""Calibration tests: pilot cases are calibrated, scored cases never are.

These tests are the executable half of grader calibration. The calibration sets
hold the probe reviews; this module replays each probe through the real grader
against the real shipped expectation and asserts the classification the
calibration set claims. A formulation that stops recognising a real reviewer's
prose, or loosens far enough to credit an overlapping symptom, fails here rather
than quietly changing what a baseline means.

Calibration and scoring are mutually exclusive by the owner-settled method on
#58: a scored case is never calibrated on its own prose, and a grader miss on a
scored case is reported as `referred_root_cause_ids` (see `grader.py`) rather
than silently becoming recall damage. Calibration sets exist only for the
disjoint pilot corpus, whose cases are never scored.

Nothing in this module launches a runtime or spends money.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from evals import calibration, corpus, grader, protocol  # noqa: E402


class CalibrationSetTests(unittest.TestCase):
    """The calibration sets themselves must be well formed and grounded."""

    @classmethod
    def setUpClass(cls):
        cls.sets = calibration.load_sets()
        cls.cases = calibration.cases_by_id()

    def test_at_least_one_calibration_set_ships(self):
        self.assertTrue(self.sets, "no calibration set is shipped")

    def test_every_calibration_set_names_a_real_case(self):
        for case_id in self.sets:
            with self.subTest(case_id=case_id):
                self.assertIn(case_id, self.cases)

    def test_every_calibration_set_matches_the_shipped_grader(self):
        for case_id, calibration_set in self.sets.items():
            with self.subTest(case_id=case_id):
                self.assertEqual(grader.GRADER_VERSION, calibration_set.grader_version)

    def test_every_calibration_set_probes_every_grading_boundary(self):
        for case_id, calibration_set in self.sets.items():
            with self.subTest(case_id=case_id):
                self.assertEqual(
                    frozenset(),
                    calibration.REQUIRED_PROBE_KINDS - calibration_set.kinds,
                    "a calibration set that does not probe every boundary can "
                    "certify a formulation that credits the wrong answer",
                )

    def test_every_probe_finding_conforms_to_the_v1_result_contract(self):
        for case_id, calibration_set in self.sets.items():
            candidate = self.cases[case_id][0][1].packet["candidate"]
            identity = {
                "head_sha": candidate["head_sha"],
                "comparison_base_sha": candidate["comparison_base_sha"],
            }
            for probe in calibration_set.probes:
                with self.subTest(case_id=case_id, probe=probe["id"]):
                    result = calibration.probe_result(probe, identity)
                    self.assertEqual([], protocol.VALIDATOR.validate_result(result))

    def test_a_case_carried_by_several_corpora_carries_one_expectation(self):
        """The pilot strata share one case so the closure is the only variable.

        If their expectations could drift apart, one calibration set would be
        certifying grading behaviour that only holds for one of them.
        """
        for case_id, occurrences in self.cases.items():
            with self.subTest(case_id=case_id):
                expectations = [case.expectation for _, case in occurrences]
                for other in expectations[1:]:
                    self.assertEqual(expectations[0], other)

    def test_a_scored_case_is_never_calibrated(self):
        """Settled by the owner on #58: never calibrate a scored case's prose.

        Batch 1 measured what an uncalibrated expectation reports - recall 0.0
        against a reviewer that found the defect on every attempt - and batch 2
        proposed calibrating scored cases against their own observed prose as
        one fix. The owner rejected that: calibrating a case requires observing
        its real reviewer prose, and a scored case must never have been
        observed before scoring, or the baseline measures a case the corpus
        author already looked at - the exact contamination the payload-blindness
        tests exist to prevent, entering through the grader instead.

        The settled replacement is three-way scoring (matched / missed /
        referred), which needs no calibration at all: a formulation miss
        surfaces as `referred_root_cause_ids` rather than a silently wrong
        recall figure. So `calibrated: true` on a scored case is not a missing
        nice-to-have, it is itself the contamination this method exists to rule
        out.
        """
        for root in corpus.corpus_roots():
            loaded = corpus.load_corpus(root)
            if not loaded.scored:
                continue
            for case in loaded.cases:
                with self.subTest(stratum=root.name, case_id=case.case_id):
                    self.assertIs(
                        False,
                        case.expectation.get("calibrated"),
                        "a scored case must never be calibrated on its own "
                        "prose - see the three-way scoring method",
                    )

    def test_a_scored_case_records_a_complete_second_adjudication(self):
        """A scored stratum may not carry a case still marked as needing one."""
        for root in corpus.corpus_roots():
            loaded = corpus.load_corpus(root)
            if not loaded.scored:
                continue
            for case in loaded.cases:
                with self.subTest(stratum=root.name, case_id=case.case_id):
                    adjudication = case.provenance.get("adjudication")
                    self.assertIsNotNone(adjudication)
                    self.assertIn(
                        adjudication["second"],
                        {"oracle", "owner_confirmed"},
                        "a scored case's second adjudication must be settled, "
                        "not still owner_required or none",
                    )

    def test_a_calibrated_expectation_ships_a_calibration_set(self):
        """`calibrated: true` is a claim the calibration set has to back."""
        for root in corpus.corpus_roots():
            for case in corpus.load_corpus(root).cases:
                if not case.expectation.get("calibrated"):
                    continue
                with self.subTest(stratum=root.name, case_id=case.case_id):
                    self.assertIn(case.case_id, self.sets)


class CalibratedGradingTests(unittest.TestCase):
    """Each probe must be graded exactly as its calibration set claims."""

    @classmethod
    def setUpClass(cls):
        cls.sets = calibration.load_sets()
        cls.cases = calibration.cases_by_id()

    def _grade(self, case_id, probe):
        _, case = self.cases[case_id][0]
        candidate = case.packet["candidate"]
        identity = {
            "head_sha": candidate["head_sha"],
            "comparison_base_sha": candidate["comparison_base_sha"],
        }
        return grader.grade(case.expectation, calibration.probe_result(probe, identity))

    def test_every_probe_demonstrates_what_its_kind_claims(self):
        """A kind is a claim about grading behaviour, not a label.

        Asserted against the real grader rather than against the calibration
        set's own `expect` block, so a set cannot certify a boundary by
        declaring the outcome it happens to get.
        """
        for case_id, calibration_set in self.sets.items():
            for probe in calibration_set.probes:
                required, must_charge = calibration.PROBE_KIND_CONTRACT[probe["kind"]]
                with self.subTest(case_id=case_id, probe=probe["id"]):
                    graded = self._grade(case_id, probe)
                    observed = {
                        record["classification"] for record in graded["findings"]
                    }
                    self.assertEqual(required, observed)
                    self.assertEqual(
                        must_charge, bool(graded["false_positive_finding_ids"])
                    )
                    if probe["kind"] in {"observed", "paraphrase"}:
                        self.assertEqual(1.0, graded["recall"])
                    if probe["kind"] == "duplicate_report":
                        self.assertEqual(1, len(graded["matched_root_cause_ids"]))
                        self.assertEqual(1, len(graded["duplicate_finding_ids"]))

    def test_every_probe_receives_its_calibrated_classification(self):
        for case_id, calibration_set in self.sets.items():
            for probe in calibration_set.probes:
                expect = probe["expect"]
                with self.subTest(case_id=case_id, probe=probe["id"]):
                    graded = self._grade(case_id, probe)
                    observed = {
                        record["finding_id"]: record["classification"]
                        for record in graded["findings"]
                    }
                    self.assertEqual(expect["classifications"], observed)
                    self.assertEqual(
                        expect["matched_root_cause_ids"],
                        graded["matched_root_cause_ids"],
                    )
                    self.assertEqual(expect["recall"], graded["recall"])
                    self.assertEqual(
                        expect["false_positive_finding_ids"],
                        graded["false_positive_finding_ids"],
                    )
                    self.assertEqual(
                        expect["adjudication_finding_ids"],
                        [
                            item["finding_id"]
                            for item in graded["adjudication_required"]
                        ],
                    )


class StratumLabellingTests(unittest.TestCase):
    """A stratum must say what it is, and must not claim what it is not."""

    def test_every_stratum_corpus_declares_a_labelled_stratum(self):
        for root in corpus.corpus_roots():
            if root.parent != corpus.STRATA_ROOT:
                continue
            with self.subTest(stratum=root.name):
                loaded = corpus.load_corpus(root)
                self.assertIsNotNone(loaded.stratum)
                self.assertEqual(root.name, loaded.stratum["id"])

    def test_no_shipped_stratum_claims_connector_ground_truth(self):
        """The connector stratum is deferred, and must not be implied.

        No connector review history is available to this repository under
        acceptable disclosure terms, so connector-escape recall has never been
        measured. A corpus labelled `connector-review` would let a report present
        a human-review figure as a connector figure, which is the one comparison
        the baseline limitations record forbids. Delete this test when real
        adjudicated connector material is actually curated.
        """
        for root in corpus.corpus_roots():
            with self.subTest(stratum=root.name):
                loaded = corpus.load_corpus(root)
                self.assertNotEqual(
                    "connector-review", (loaded.stratum or {}).get("ground_truth")
                )

    def test_a_scored_stratum_must_grade_its_own_target(self):
        """A stratum whose expectations target another lens cannot be scored.

        Grading a contract-faithful lens against another lens's root cause is a
        corpus defect, not a reviewer miss, and would invalidate the stratum.
        """
        for root in corpus.corpus_roots():
            loaded = corpus.load_corpus(root)
            if loaded.stratum is None:
                continue
            with self.subTest(stratum=root.name):
                if loaded.scored:
                    self.assertTrue(loaded.stratum["grading_is_signal"])

    def test_no_pilot_case_is_also_a_scored_case(self):
        """Calibrating on a case that is also scored would fit the answer."""
        pilot: set[str] = set()
        scored: set[str] = set()
        for root in corpus.corpus_roots():
            loaded = corpus.load_corpus(root)
            if loaded.stratum is None:
                continue
            target = scored if loaded.scored else pilot
            target.update(case.case_id for case in loaded.cases)
        self.assertEqual(set(), pilot & scored)


if __name__ == "__main__":
    unittest.main()
