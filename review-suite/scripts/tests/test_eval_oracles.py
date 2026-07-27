"""Oracle tests: the machine half of a case's independent adjudication.

An oracle is only an adjudication if it is actually executed and actually
discriminates. These tests run each case's requirement against the reproduction
the candidate leaves behind, and against the corrected reproduction where one
exists, and assert the polarity the case's expected verdict demands.

The `corrected` leg is what makes this an adjudication of the *root cause* rather
than of a symptom: correcting the stated cause is what must make the requirement
hold. A case whose requirement fails for some unrelated reason fails here.

Nothing in this module launches a runtime or spends money.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from evals import calibration, corpus, oracles  # noqa: E402


def _expectation_for(case_id: str) -> dict:
    for _, case in calibration.cases_by_id()[case_id]:
        return case.expectation
    raise AssertionError(f"no corpus case {case_id!r}")


class OracleContractTests(unittest.TestCase):
    """The oracle set must be well formed and must name real cases."""

    @classmethod
    def setUpClass(cls):
        cls.case_ids = oracles.case_ids()
        cls.corpus_cases = calibration.cases_by_id()

    def test_at_least_one_oracle_ships(self):
        self.assertTrue(self.case_ids)

    def test_every_oracle_names_a_real_case(self):
        for case_id in self.case_ids:
            with self.subTest(case_id=case_id):
                self.assertIn(case_id, self.corpus_cases)

    def test_every_oracle_declares_its_own_case_id(self):
        for case_id in self.case_ids:
            with self.subTest(case_id=case_id):
                self.assertEqual(case_id, oracles.load(case_id).case_id)

    def test_a_clean_expected_case_has_no_corrected_leg(self):
        """There is nothing to correct, and inventing one would assert a defect."""
        for case_id in self.case_ids:
            expectation = _expectation_for(case_id)
            if expectation["expected_verdict"] != "clean":
                continue
            with self.subTest(case_id=case_id):
                self.assertIsNone(oracles.load(case_id).corrected)

    def test_a_gating_case_ships_a_corrected_leg(self):
        """Without it the oracle cannot tell the root cause from a symptom."""
        for case_id in self.case_ids:
            expectation = _expectation_for(case_id)
            if expectation["expected_verdict"] != "changes_required":
                continue
            with self.subTest(case_id=case_id):
                self.assertIsNotNone(oracles.load(case_id).corrected)


class OracleAdjudicationTests(unittest.TestCase):
    """Each requirement must fail or hold exactly as the verdict demands."""

    def test_the_requirement_fails_on_every_gating_candidate(self):
        for case_id in oracles.case_ids():
            expectation = _expectation_for(case_id)
            if expectation["expected_verdict"] != "changes_required":
                continue
            oracle = oracles.load(case_id)
            with self.subTest(case_id=case_id):
                self.assertFalse(
                    oracle.check(oracle.candidate()),
                    f"{case_id}: the stated requirement holds against the "
                    "candidate, so this case does not demonstrate a defect",
                )

    def test_correcting_the_root_cause_makes_the_requirement_hold(self):
        for case_id in oracles.case_ids():
            expectation = _expectation_for(case_id)
            if expectation["expected_verdict"] != "changes_required":
                continue
            oracle = oracles.load(case_id)
            with self.subTest(case_id=case_id):
                self.assertTrue(
                    oracle.check(oracle.corrected()),
                    f"{case_id}: correcting the stated root cause does not make "
                    "the requirement hold, so the stated cause is not the cause",
                )

    def test_the_requirement_holds_on_every_clean_candidate(self):
        for case_id in oracles.case_ids():
            expectation = _expectation_for(case_id)
            if expectation["expected_verdict"] != "clean":
                continue
            oracle = oracles.load(case_id)
            with self.subTest(case_id=case_id):
                self.assertTrue(
                    oracle.check(oracle.candidate()),
                    f"{case_id}: the stated requirement does not hold, so this "
                    "case cannot serve as a clean control",
                )


class OracleCoverageTests(unittest.TestCase):
    """Where an oracle is available it must be shipped, and it must be recorded."""

    def test_every_case_in_the_correctness_stratum_has_an_oracle(self):
        """The correctness stratum is the one where an oracle is always possible.

        A correctness requirement is a statement about behaviour, so it can be
        run. Leaving one un-oracled would silently route a case to the owner that
        a machine could have settled.
        """
        root = corpus.STRATA_ROOT / "s1-correctness-orchestrator"
        if not root.is_dir():
            self.skipTest("the correctness stratum is not populated")
        shipped = set(oracles.case_ids())
        for case in corpus.load_corpus(root).cases:
            with self.subTest(case_id=case.case_id):
                self.assertIn(case.case_id, shipped)

    def test_an_oracle_settled_case_records_that_in_its_provenance(self):
        """A reader must never have to infer how a case was adjudicated."""
        shipped = set(oracles.case_ids())
        for case_id in shipped:
            for _, case in calibration.cases_by_id()[case_id]:
                with self.subTest(case_id=case_id):
                    adjudication = case.provenance.get("adjudication")
                    self.assertIsNotNone(adjudication)
                    self.assertEqual("oracle", adjudication["second"])
                    self.assertTrue(adjudication["first"].strip())

    def test_a_case_without_an_oracle_routes_to_the_owner(self):
        """`owner_required` is the only honest alternative to an oracle.

        A fresh agent context is not a second adjudicator for materiality when it
        shares a model family with the reviewer being measured, so a case with no
        oracle has to say it needs the owner rather than quietly claiming two.
        """
        shipped = set(oracles.case_ids())
        for root in corpus.corpus_roots():
            for case in corpus.load_corpus(root).cases:
                adjudication = case.provenance.get("adjudication")
                if adjudication is None or case.case_id in shipped:
                    continue
                with self.subTest(stratum=root.name, case_id=case.case_id):
                    self.assertEqual("owner_required", adjudication["second"])


if __name__ == "__main__":
    unittest.main()
