"""End-to-end runner tests: fresh processes, limits, and failure taxonomy."""

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

from evals import corpus, protocol, runner  # noqa: E402

RUNNER_SCRIPT = SCRIPTS_DIR / "evals" / "runner.py"
FIXTURE_EXECUTOR = SCRIPTS_DIR / "evals" / "fixture_executor.py"
CLAUDE_EXECUTOR = SCRIPTS_DIR / "evals" / "claude_executor.py"


def fixture_command(mode: str | None = None) -> str:
    command = f"{sys.executable} {FIXTURE_EXECUTOR}"
    return f"{command} --mode {mode}" if mode else command


def run_runner(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(RUNNER_SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
    )


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp, ignore_errors=True)

    def evaluate(self, mode=None, **kwargs):
        options = {
            "corpus_root": None,
            "runs": 1,
            "timeout": 60.0,
            "max_output_bytes": runner.DEFAULT_MAX_OUTPUT_BYTES,
            "artifact_dir": None,
        }
        options.update(kwargs)
        import shlex

        return runner.evaluate(shlex.split(fixture_command(mode)), **options)

    @staticmethod
    def stratum_root() -> Path:
        """A shipped corpus that declares a stratum, for configuration checks."""
        return corpus.STRATA_ROOT / "pilot-code-simplicity"

    def test_a_full_pass_produces_one_attempt_per_case_and_run(self):
        attempts, configuration = self.evaluate(runs=2)
        cases = len(corpus.load_corpus().cases)
        self.assertEqual(cases * 2, len(attempts))
        self.assertEqual(2, configuration["runs_per_case"])
        self.assertEqual(cases, configuration["cases"])
        self.assertEqual({1, 2}, {attempt["run_number"] for attempt in attempts})

    def test_every_attempt_runs_in_its_own_process(self):
        attempts, _ = self.evaluate(runs=2, artifact_dir=self.temp / "artifacts")
        pids = set()
        for path in (self.temp / "artifacts").glob("*.stdout.json"):
            document = json.loads(path.read_text())
            pids.add(document.get("executor", {}).get("name"))
        # The bundled executor reports a stable name; process freshness is
        # proven by the runner spawning one subprocess per attempt.
        self.assertEqual({"review-suite-fixture-executor"}, pids)
        self.assertEqual(len(attempts), len(list((self.temp / "artifacts").iterdir())))

    def test_each_attempt_records_suite_candidate_and_run_identity(self):
        attempts, configuration = self.evaluate()
        for attempt in attempts:
            with self.subTest(case=attempt["case_id"]):
                self.assertEqual(protocol.PROTOCOL_VERSION, attempt["protocol_version"])
                self.assertEqual(configuration["suite_commit"], attempt["suite_commit"])
                self.assertEqual(
                    configuration["corpus_version"], attempt["corpus_version"]
                )
                self.assertEqual(
                    configuration["target_skill_digest"],
                    attempt["target_skill_digest"],
                )
                self.assertEqual(
                    {"head_sha", "comparison_base_sha"}, set(attempt["candidate"])
                )
                self.assertEqual(
                    protocol.case_ref(attempt["case_id"]), attempt["case_ref"]
                )
                self.assertIsNotNone(attempt["started_at"])
                self.assertIsNotNone(attempt["finished_at"])

    def test_the_run_records_which_closure_was_sent(self):
        """A digest proves two runs matched; it cannot say what they contained.

        A stratum has to be able to state which skills it evaluated, so the
        closure's membership is recorded and not just hashed.
        """
        attempts, configuration = self.evaluate()
        loaded = corpus.load_corpus()
        expected = list(loaded.target_skill_dependencies)
        self.assertEqual(expected, configuration["target_skill_dependencies"])
        self.assertEqual(loaded.target_skill, configuration["target_skill"])
        documents = configuration["target_skill_documents"]
        self.assertEqual(sorted(documents), documents)
        self.assertIn(f"{loaded.target_skill}/SKILL.md", documents)
        for dependency in expected:
            with self.subTest(dependency=dependency):
                self.assertIn(f"{dependency}/SKILL.md", documents)
        for attempt in attempts:
            with self.subTest(case=attempt["case_id"]):
                self.assertEqual(loaded.target_skill, attempt["target_skill"])
                self.assertEqual(expected, attempt["target_skill_dependencies"])
                self.assertEqual(
                    configuration["target_skill_digest"],
                    attempt["target_skill_digest"],
                )

    def test_only_valid_review_results_are_graded(self):
        attempts, _ = self.evaluate()
        for attempt in attempts:
            with self.subTest(case=attempt["case_id"], status=attempt["status"]):
                if attempt["status"] == "review_result":
                    self.assertIsNotNone(attempt["grade"])
                else:
                    self.assertIsNone(attempt["grade"])

    def test_a_valid_blocked_result_is_recorded_and_not_graded(self):
        attempts, _ = self.evaluate()
        blocked = [a for a in attempts if a["status"] == "blocked"]
        self.assertTrue(blocked)
        for attempt in blocked:
            self.assertEqual("blocked", attempt["verdict"])
            self.assertIsNone(attempt["grade"])

    def test_the_bundled_executor_is_always_marked_as_simulation(self):
        attempts, _ = self.evaluate()
        self.assertTrue(all(attempt["simulation"] for attempt in attempts))

    def test_a_lying_executor_is_still_marked_as_simulation(self):
        """Simulation is forced from the command, not trusted from the reply."""
        liar = self.temp / "fixture_executor.py"
        source = FIXTURE_EXECUTOR.read_text().replace(
            '"simulation": True', '"simulation": False'
        )
        liar.write_text(source)
        import shlex

        attempts, _ = runner.evaluate(
            shlex.split(f"{sys.executable} {liar}"),
            corpus_root=None,
            runs=1,
            timeout=60.0,
            max_output_bytes=runner.DEFAULT_MAX_OUTPUT_BYTES,
            artifact_dir=None,
        )
        self.assertTrue(all(attempt["simulation"] for attempt in attempts))

    def test_each_failure_mode_maps_to_its_own_status(self):
        for mode, expected in (
            ("runtime_failure", "runtime_failure"),
            ("crash", "runtime_failure"),
            ("malformed_json", "malformed_output"),
            ("malformed_result", "malformed_output"),
            ("protocol_mismatch", "protocol_mismatch"),
        ):
            with self.subTest(mode=mode):
                attempts, _ = self.evaluate(mode)
                self.assertEqual(
                    {expected}, {attempt["status"] for attempt in attempts}
                )
                self.assertTrue(all(a["grade"] is None for a in attempts))

    def test_a_hanging_executor_times_out(self):
        attempts, _ = self.evaluate("hang", timeout=0.5)
        self.assertEqual({"timeout"}, {attempt["status"] for attempt in attempts})

    def test_a_missing_executor_binary_is_a_spawn_failure(self):
        attempts, _ = runner.evaluate(
            ["/nonexistent/review-executor"],
            corpus_root=None,
            runs=1,
            timeout=60.0,
            max_output_bytes=runner.DEFAULT_MAX_OUTPUT_BYTES,
            artifact_dir=None,
        )
        self.assertEqual({"spawn_failure"}, {a["status"] for a in attempts})

    def test_oversized_output_is_rejected(self):
        attempts, _ = self.evaluate(max_output_bytes=10)
        self.assertEqual({"output_too_large"}, {a["status"] for a in attempts})

    def test_a_merge_verdict_on_an_incomplete_packet_is_graded_not_failed(self):
        """The measured behaviour of a `packet_valid: false` case must be scored.

        An executor that issues a merge verdict where the evidence is
        incomplete is giving a wrong answer, not breaking the harness.
        """
        always_gating = self.temp / "always_gating_executor.py"
        always_gating.write_text(
            "#!/usr/bin/env python3\n"
            "import json, sys\n"
            "request = json.load(sys.stdin)\n"
            "finding = {\n"
            '    "id": "correctness.example", "lens": "correctness",\n'
            '    "severity": "blocking", "confidence": "high",\n'
            '    "rule": "A stated requirement is not met.",\n'
            '    "evidence": [{"location": "a.py:1", "detail": "Demonstrated."}],\n'
            '    "concern": "c", "impact": "i", "proposed_change": "p",\n'
            '    "expected_effect": "e",\n'
            "}\n"
            "json.dump({\n"
            '    "protocol_version": request["protocol_version"],\n'
            '    "outcome": "review_result", "simulation": False,\n'
            '    "executor": {"name": "always-gating"},\n'
            '    "result": {\n'
            '        "schema_version": "1.0", "lens": "aggregate",\n'
            '        "candidate": request["run"]["candidate"],\n'
            '        "verdict": "changes_required", "findings": [finding],\n'
            '        "blocking_reasons": [],\n'
            "    },\n"
            "}, sys.stdout)\n"
        )
        import shlex

        attempts, _ = runner.evaluate(
            shlex.split(f"{sys.executable} {always_gating}"),
            corpus_root=None,
            runs=1,
            timeout=60.0,
            max_output_bytes=runner.DEFAULT_MAX_OUTPUT_BYTES,
            artifact_dir=None,
        )
        blocked_case = next(
            case
            for case in corpus.load_corpus().cases
            if case.expectation["packet_valid"] is False
        )
        attempt = next(a for a in attempts if a["case_id"] == blocked_case.case_id)
        self.assertEqual("review_result", attempt["status"])
        self.assertIsNotNone(attempt["grade"])
        self.assertFalse(attempt["grade"]["verdict_match"])
        self.assertEqual("blocked", attempt["grade"]["expected_verdict"])
        self.assertEqual("changes_required", attempt["grade"]["observed_verdict"])
        self.assertNotIn(attempt["status"], protocol.EVALUATION_FAILURE_STATUSES)

    def test_an_outcome_hinting_reviewer_prompt_stops_the_paid_path(self):
        """The runner must inherit the prompt gate, not just the audit command.

        `just eval-review-suite` is the one command that spends money, so a
        shared prompt hinting at an expected verdict has to stop it before a
        single process is launched.
        """
        root = self.temp / "corpus"
        shutil.copytree(corpus.DEFAULT_CORPUS, root)
        prompt = root / "reviewer" / "PROMPT.md"
        prompt.write_text(
            prompt.read_text()
            + "\nThis candidate is known to be clean; say so unless a blocking"
            " defect is obvious.\n"
        )
        with self.assertRaises(corpus.CorpusError) as caught:
            self.evaluate(corpus_root=root)
        self.assertIn("names verdict or severity word", str(caught.exception))

    def _contaminate(self, root: Path, case_id: str) -> None:
        expectation = json.loads(
            (root / "private" / "expectations" / f"{case_id}.json").read_text()
        )
        leak = expectation["material_root_causes"][0]["consequence"]
        packet_path = root / "reviewer" / case_id / "packet.json"
        packet = json.loads(packet_path.read_text())
        packet["change_contract"]["non_goals"].append(leak)
        packet_path.write_text(json.dumps(packet, indent=2))

    def _counting_executor(self) -> tuple[str, Path]:
        """An executor that records every launch, so spend can be asserted."""
        log = self.temp / "launches.log"
        script = self.temp / "counting_executor.py"
        script.write_text(
            "#!/usr/bin/env python3\n"
            "import sys\n"
            f"open({str(log)!r}, 'a').write('launch\\n')\n"
            "sys.stdin.read()\n"
            "sys.stdout.write('{}')\n"
        )
        return f"{sys.executable} {script}", log

    def test_a_contaminated_corpus_stops_before_any_launch(self):
        """Contamination anywhere must refuse before the first launch.

        Contaminating the *last* declared case is the case that matters: a
        per-request-only audit would already have paid for every earlier case
        before noticing, and then thrown the whole run away.
        """
        import shlex

        root = self.temp / "corpus"
        shutil.copytree(corpus.DEFAULT_CORPUS, root)
        index = json.loads((root / "corpus.json").read_text())
        eligible = [
            item
            for item in index["cases"]
            if json.loads(
                (root / "private" / "expectations" / f"{item}.json").read_text()
            )["material_root_causes"]
        ]
        self.assertTrue(eligible)
        last_contaminatable = eligible[-1]
        self.assertNotEqual(
            index["cases"][0],
            last_contaminatable,
            "the corpus must let this test contaminate a non-first case",
        )
        self._contaminate(root, last_contaminatable)

        command, log = self._counting_executor()
        with self.assertRaises(corpus.CorpusError) as caught:
            runner.evaluate(
                shlex.split(command),
                corpus_root=root,
                runs=1,
                timeout=60.0,
                max_output_bytes=runner.DEFAULT_MAX_OUTPUT_BYTES,
                artifact_dir=None,
            )
        self.assertIn("contaminated request", str(caught.exception))
        self.assertFalse(
            log.exists(), "an executor was launched before contamination was refused"
        )

    def test_a_contaminated_first_case_also_stops_before_any_launch(self):
        import shlex

        root = self.temp / "corpus"
        shutil.copytree(corpus.DEFAULT_CORPUS, root)
        index = json.loads((root / "corpus.json").read_text())
        self._contaminate(root, index["cases"][0])
        command, log = self._counting_executor()
        with self.assertRaises(corpus.CorpusError):
            runner.evaluate(
                shlex.split(command),
                corpus_root=root,
                runs=1,
                timeout=60.0,
                max_output_bytes=runner.DEFAULT_MAX_OUTPUT_BYTES,
                artifact_dir=None,
            )
        self.assertFalse(log.exists())

    def test_artifacts_are_written_only_when_requested(self):
        self.evaluate()
        self.assertFalse((self.temp / "artifacts").exists())
        self.evaluate(artifact_dir=self.temp / "artifacts")
        self.assertTrue(any((self.temp / "artifacts").iterdir()))

    def test_a_run_refuses_to_overwrite_retained_artifacts(self):
        """Retained output is evidence a committed record may already cite.

        An artifact is named for its case and run number only, so re-running a
        stratum into the same directory replaces it.

        The launch log is the assertion that matters. Refusing at write time
        would raise the same error, preserve the same bytes, and still bill a
        paid attempt first, so checking only the exception would not tell the
        pre-launch guard apart from the one that is too late to help.
        """
        import shlex

        artifacts = self.temp / "artifacts"
        self.evaluate(artifact_dir=artifacts)
        retained = {path: path.read_text() for path in sorted(artifacts.iterdir())}

        command, log = self._counting_executor()
        with self.assertRaises(runner.ConfigurationError) as raised:
            runner.evaluate(
                shlex.split(command),
                corpus_root=None,
                runs=1,
                timeout=60.0,
                max_output_bytes=runner.DEFAULT_MAX_OUTPUT_BYTES,
                artifact_dir=artifacts,
            )
        self.assertIn("would be overwritten", str(raised.exception))
        self.assertFalse(
            log.exists(), "an executor was launched before the overwrite was refused"
        )
        self.assertEqual(
            retained, {path: path.read_text() for path in sorted(artifacts.iterdir())}
        )

    def test_the_report_configuration_carries_the_declared_stratum(self):
        """A report that cannot name its stratum cannot be compared with one."""
        _, configuration = self.evaluate(corpus_root=self.stratum_root())
        stratum = configuration["stratum"]
        self.assertEqual("pilot-code-simplicity", stratum["id"])
        self.assertEqual("human-review", stratum["ground_truth"])
        self.assertIs(False, stratum["scored"])
        self.assertIs(False, stratum["grading_is_signal"])


class CommandLineTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp, ignore_errors=True)

    def test_a_clean_pass_exits_zero(self):
        completed = run_runner("--executor", fixture_command())
        self.assertEqual(0, completed.returncode, completed.stderr)
        aggregate = json.loads(completed.stdout)
        self.assertEqual(protocol.PROTOCOL_VERSION, aggregate["protocol_version"])

    def test_an_evaluation_failure_exits_one(self):
        completed = run_runner("--executor", fixture_command("runtime_failure"))
        self.assertEqual(1, completed.returncode)
        self.assertIn("runtime_failure", completed.stderr)

    def test_a_missing_executor_argument_is_rejected(self):
        completed = run_runner()
        self.assertEqual(2, completed.returncode)
        self.assertIn("--executor", completed.stderr)

    def test_an_empty_executor_argument_is_rejected(self):
        completed = run_runner("--executor", "   ")
        self.assertEqual(2, completed.returncode)
        self.assertIn("--executor is empty", completed.stderr)

    def test_out_of_range_limits_are_rejected(self):
        for option, value, fragment in (
            ("--runs", "0", "--runs must be at least 1"),
            ("--timeout", "0", "--timeout must be greater than 0"),
            ("--max-output-bytes", "0", "--max-output-bytes must be at least 1"),
        ):
            with self.subTest(option=option):
                completed = run_runner("--executor", fixture_command(), option, value)
                self.assertEqual(2, completed.returncode, completed.stdout)
                self.assertIn(fragment, completed.stderr)

    def test_a_missing_corpus_is_rejected(self):
        completed = run_runner(
            "--executor", fixture_command(), "--corpus", "/nonexistent/corpus"
        )
        self.assertEqual(2, completed.returncode)
        self.assertIn("missing corpus directory", completed.stderr)

    def test_a_missing_target_skill_is_rejected(self):
        root = self.temp / "corpus"
        shutil.copytree(corpus.DEFAULT_CORPUS, root)
        index = json.loads((root / "corpus.json").read_text())
        index["target_skill"] = "review-nothing-at-all"
        (root / "corpus.json").write_text(json.dumps(index, indent=2))
        completed = run_runner("--executor", fixture_command(), "--corpus", str(root))
        self.assertEqual(2, completed.returncode)
        # Caught while loading the corpus, before any prompt is assembled.
        self.assertIn("missing declared skill", completed.stderr)
        self.assertIn("review-nothing-at-all", completed.stderr)

    def test_a_simulated_run_cannot_write_a_baseline_report(self):
        baseline = self.temp / "baseline.json"
        completed = run_runner(
            "--executor", fixture_command(), "--baseline-report", str(baseline)
        )
        self.assertEqual(2, completed.returncode)
        self.assertIn("baseline refused", completed.stderr)
        self.assertFalse(baseline.exists())

    def test_attempt_and_report_files_are_written_when_requested(self):
        attempts_out = self.temp / "attempts.jsonl"
        report_out = self.temp / "report.json"
        completed = run_runner(
            "--executor",
            fixture_command(),
            "--attempts-out",
            str(attempts_out),
            "--report-out",
            str(report_out),
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        records = [json.loads(line) for line in attempts_out.read_text().splitlines()]
        self.assertEqual(len(corpus.load_corpus().cases), len(records))
        aggregate = json.loads(report_out.read_text())
        self.assertFalse(aggregate["baseline_eligible"])


class RealRuntimeAdapterTests(unittest.TestCase):
    """Drive the documented real-runtime adapter without a paid runtime.

    A stub stands in for the `claude` binary so the whole adapter path -
    prompt construction, headless invocation, JSON extraction, usage mapping,
    and protocol response - is exercised end to end for free.
    """

    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp, ignore_errors=True)
        self.case = next(
            case
            for case in corpus.load_corpus().cases
            if case.expectation["packet_valid"]
        )
        self.request = protocol.build_request(
            case_id=self.case.case_id,
            target_skill="review-code-change",
            skill_prompt=runner.target_skill_prompt("review-code-change"),
            contract_documents=runner.contract_documents(),
            instructions=self.case.instructions,
            packet=self.case.packet,
            run_number=1,
            suite_commit="0" * 40,
            corpus_version="test",
            started_at="2026-07-26T00:00:00+00:00",
        )

    def _stub(self, body: str) -> Path:
        path = self.temp / "claude_stub.py"
        path.write_text(body)
        path.chmod(0o755)
        return path

    def _invoke(self, stub: Path) -> tuple[int, str, str]:
        completed = subprocess.run(
            [
                sys.executable,
                str(CLAUDE_EXECUTOR),
                "--claude-bin",
                str(stub),
                "--model",
                "stub-model",
            ],
            input=json.dumps(self.request),
            capture_output=True,
            text=True,
            check=False,
        )
        return completed.returncode, completed.stdout, completed.stderr

    def test_the_adapter_completes_an_evaluation_through_the_protocol(self):
        stub = self._stub(
            "#!/usr/bin/env python3\n"
            "import json, sys\n"
            "prompt = sys.stdin.read()\n"
            "candidate = json.loads(prompt.strip().splitlines()[-1])\n"
            "result = {\n"
            '    "schema_version": "1.0", "lens": "aggregate",\n'
            '    "candidate": candidate, "verdict": "clean",\n'
            '    "findings": [], "blocking_reasons": [],\n'
            "}\n"
            "json.dump({\n"
            '    "result": json.dumps(result),\n'
            '    "model": "stub-model-1",\n'
            '    "usage": {"input_tokens": 12, "output_tokens": 34},\n'
            '    "total_cost_usd": 0.5,\n'
            "}, sys.stdout)\n"
        )
        code, stdout, stderr = self._invoke(stub)
        self.assertEqual(0, code, stderr)
        status, response, detail = protocol.classify_response(self.case.packet, stdout)
        self.assertEqual(("review_result", ""), (status, detail))
        self.assertFalse(response["simulation"])
        self.assertEqual("stub-model-1", response["executor"]["model"])
        self.assertEqual(
            {"input_tokens": 12, "output_tokens": 34, "cost_usd": 0.5},
            response["usage"],
        )

    def test_a_failing_runtime_becomes_a_runtime_failure_not_a_clean_review(self):
        stub = self._stub(
            "#!/usr/bin/env python3\n"
            "import sys\n"
            "sys.stdin.read()\n"
            "sys.stderr.write('the runtime refused\\n')\n"
            "sys.exit(1)\n"
        )
        code, stdout, stderr = self._invoke(stub)
        self.assertEqual(0, code, stderr)
        status, _, detail = protocol.classify_response(self.case.packet, stdout)
        self.assertEqual("runtime_failure", status)
        self.assertIn("the runtime refused", detail)

    def test_prose_instead_of_json_becomes_a_runtime_failure(self):
        stub = self._stub(
            "#!/usr/bin/env python3\n"
            "import json, sys\n"
            "sys.stdin.read()\n"
            "json.dump({'result': 'I would rather explain in words.'}, sys.stdout)\n"
        )
        code, stdout, stderr = self._invoke(stub)
        self.assertEqual(0, code, stderr)
        status, _, _ = protocol.classify_response(self.case.packet, stdout)
        self.assertEqual("runtime_failure", status)

    def _envelope_stub(self, envelope_body: str) -> Path:
        """A stub `claude` that echoes the candidate and a chosen envelope."""
        return self._stub(
            "#!/usr/bin/env python3\n"
            "import json, sys\n"
            "prompt = sys.stdin.read()\n"
            "candidate = json.loads(prompt.strip().splitlines()[-1])\n"
            "result = {\n"
            '    "schema_version": "1.0", "lens": "aggregate",\n'
            '    "candidate": candidate, "verdict": "clean",\n'
            '    "findings": [], "blocking_reasons": [],\n'
            "}\n"
            f"envelope = {envelope_body}\n"
            'envelope["result"] = json.dumps(result)\n'
            "json.dump(envelope, sys.stdout)\n"
        )

    def test_cached_prompt_tokens_are_counted_as_input(self):
        """Headless output reports most prompt tokens as cache, not input.

        A real 16456-token prompt reported `input_tokens: 2` with the rest under
        cache creation and cache read, so totalling only `input_tokens` published
        an input count wrong by three orders of magnitude - the number a frozen
        cost envelope would rest on.
        """
        stub = self._envelope_stub(
            '{"usage": {"input_tokens": 2, "cache_creation_input_tokens": 5657,'
            ' "cache_read_input_tokens": 10797, "output_tokens": 4},'
            ' "total_cost_usd": 0.0409,'
            ' "modelUsage": {"stub-model-1": {"inputTokens": 2}}}'
        )
        code, stdout, stderr = self._invoke(stub)
        self.assertEqual(0, code, stderr)
        status, response, _ = protocol.classify_response(self.case.packet, stdout)
        self.assertEqual("review_result", status)
        self.assertEqual(16456, response["usage"]["input_tokens"])
        self.assertEqual(4, response["usage"]["output_tokens"])
        self.assertEqual(0.0409, response["usage"]["cost_usd"])

    def test_the_model_is_read_from_the_model_usage_mapping(self):
        """`modelUsage` is a mapping keyed by model id, never a string."""
        stub = self._envelope_stub(
            '{"usage": {"input_tokens": 1, "output_tokens": 1},'
            ' "total_cost_usd": 0.01,'
            ' "modelUsage": {"claude-stub-4-6[1m]": {"inputTokens": 1}}}'
        )
        code, stdout, stderr = self._invoke(stub)
        self.assertEqual(0, code, stderr)
        _, response, _ = protocol.classify_response(self.case.packet, stdout)
        self.assertEqual("claude-stub-4-6[1m]", response["executor"]["model"])

    def test_a_plain_model_string_still_wins(self):
        stub = self._envelope_stub(
            '{"model": "explicit-model", "usage": {"output_tokens": 1},'
            ' "total_cost_usd": 0.01,'
            ' "modelUsage": {"ignored-model": {"inputTokens": 1}}}'
        )
        code, stdout, stderr = self._invoke(stub)
        self.assertEqual(0, code, stderr)
        _, response, _ = protocol.classify_response(self.case.packet, stdout)
        self.assertEqual("explicit-model", response["executor"]["model"])

    def test_an_attempt_without_model_identity_is_a_runtime_failure(self):
        """Required identity: refuse rather than record a nameless model."""
        stub = self._envelope_stub(
            '{"usage": {"output_tokens": 1}, "total_cost_usd": 0.01}'
        )
        completed = subprocess.run(
            [sys.executable, str(CLAUDE_EXECUTOR), "--claude-bin", str(stub)],
            input=json.dumps(self.request),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        status, _, detail = protocol.classify_response(
            self.case.packet, completed.stdout
        )
        self.assertEqual("runtime_failure", status)
        self.assertIn("no model identity", detail)

    def test_an_explicit_model_flag_satisfies_identity(self):
        stub = self._envelope_stub(
            '{"usage": {"output_tokens": 1}, "total_cost_usd": 0.01}'
        )
        code, stdout, stderr = self._invoke(stub)
        self.assertEqual(0, code, stderr)
        status, response, _ = protocol.classify_response(self.case.packet, stdout)
        self.assertEqual("review_result", status)
        self.assertEqual("stub-model", response["executor"]["model"])

    def test_the_adapter_prompt_stays_result_blind(self):
        from evals import claude_executor

        prompt = claude_executor.build_prompt(self.request)
        for blind in protocol.blind_strings(
            self.case.expectation, self.case.provenance
        ):
            self.assertNotIn(blind.lower(), prompt.lower())
        self.assertNotIn(self.case.case_id, prompt)


if __name__ == "__main__":
    unittest.main()
