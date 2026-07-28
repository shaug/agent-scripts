from __future__ import annotations

import io
import shutil
import stat
import subprocess
import tempfile
import unittest
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import db_compare as db_compare_mod
from chain import create_chain
from legacy_helpers import chdir, init_repo, run


class DbCompareTests(unittest.TestCase):
    def _prepare_repo(self) -> tuple[Path, dict]:
        repo_dir, plan = init_repo()
        with chdir(repo_dir):
            create_chain(plan)
        return repo_dir, plan

    @contextmanager
    def _record_ephemeral_directory(self):
        real_temporary_directory = tempfile.TemporaryDirectory
        paths: list[Path] = []

        def create(*args, **kwargs):
            temporary = real_temporary_directory(*args, **kwargs)
            paths.append(Path(temporary.name))
            return temporary

        with patch.object(
            db_compare_mod.tempfile, "TemporaryDirectory", side_effect=create
        ):
            yield paths

    def _assert_restored_and_clean(self, repo_dir: Path) -> None:
        branch = run(["git", "branch", "--show-current"], cwd=repo_dir).stdout.strip()
        temporary_branches = run(
            ["git", "branch", "--list", "carve-temp-db_compare-*"], cwd=repo_dir
        ).stdout.strip()
        status = run(
            ["git", "status", "--porcelain", "--untracked-files=all"], cwd=repo_dir
        ).stdout.strip()
        self.assertEqual("feature/test", branch)
        self.assertEqual("", temporary_branches)
        self.assertEqual("", status)

    def test_db_compare_rejects_unknown_command_representations_before_git(
        self,
    ) -> None:
        invalid_values = ["x", ("python3",), {"python3": "-V"}]
        with patch.object(db_compare_mod, "ensure_git_repo") as ensure_git_repo:
            for value in invalid_values:
                with self.subTest(value=value, boundary="source"):
                    with self.assertRaises(db_compare_mod.CommandError):
                        db_compare_mod.db_compare(
                            {},
                            source_argv=value,
                            chain_argv=["true"],
                        )
                with self.subTest(value=value, boundary="chain"):
                    with self.assertRaises(db_compare_mod.CommandError):
                        db_compare_mod.db_compare(
                            {},
                            source_argv=["true"],
                            chain_argv=value,
                        )
            ensure_git_repo.assert_not_called()

    def test_run_capture_preserves_exact_argv_and_restricts_output(self) -> None:
        exact_argv = ["python3", "-c", "print('two words')", "literal $VALUE"]
        with tempfile.TemporaryDirectory() as directory:
            outfile = Path(directory) / "source.txt"
            completed = subprocess.CompletedProcess(exact_argv, 0, "payload\n", "")
            with patch.object(
                db_compare_mod, "execute_argv", return_value=completed
            ) as execute:
                db_compare_mod.run_capture(exact_argv, outfile)

            execute.assert_called_once_with(exact_argv, text=True, capture_output=True)
            self.assertEqual("payload\n", outfile.read_text())
            self.assertEqual(0o600, stat.S_IMODE(outfile.stat().st_mode))

    def test_default_success_is_ephemeral_and_restores_repository(self) -> None:
        repo_dir, plan = self._prepare_repo()
        try:
            output = io.StringIO()
            with (
                chdir(repo_dir),
                self._record_ephemeral_directory() as ephemeral_paths,
                redirect_stdout(output),
            ):
                db_compare_mod.db_compare(
                    plan,
                    source_argv=["cat", "a.txt"],
                    chain_argv=["cat", "a.txt"],
                )

            self.assertEqual(1, len(ephemeral_paths))
            self.assertFalse(ephemeral_paths[0].exists())
            self.assertIn("Raw comparison outputs are ephemeral.", output.getvalue())
            self.assertIn("[OK] No differences detected.", output.getvalue())
            self.assertFalse((repo_dir / ".carve-changesets" / "db-compare").exists())
            self._assert_restored_and_clean(repo_dir)
        finally:
            shutil.rmtree(repo_dir)

    def test_difference_diagnostic_is_bounded_and_outputs_are_removed(self) -> None:
        repo_dir, plan = self._prepare_repo()
        try:
            output = io.StringIO()
            long_value = "x" * (db_compare_mod.DIAGNOSTIC_LIMIT + 1000)
            with (
                chdir(repo_dir),
                self._record_ephemeral_directory() as ephemeral_paths,
                redirect_stdout(output),
            ):
                db_compare_mod.db_compare(
                    plan,
                    source_argv=["cat", "a.txt"],
                    chain_argv=["python3", "-c", f"print({long_value!r})"],
                )

            self.assertFalse(ephemeral_paths[0].exists())
            self.assertIn("[TRUNCATED] Diagnostic limited to", output.getvalue())
            self.assertLess(
                len(output.getvalue()), db_compare_mod.DIAGNOSTIC_LIMIT + 1500
            )
            self._assert_restored_and_clean(repo_dir)
        finally:
            shutil.rmtree(repo_dir)

    def test_command_failure_is_bounded_and_removes_ephemeral_outputs(self) -> None:
        repo_dir, plan = self._prepare_repo()
        try:
            command = [
                "python3",
                "-c",
                (
                    "import sys; "
                    f"print('s' * {db_compare_mod.DIAGNOSTIC_LIMIT + 1000}); "
                    "sys.exit(3)"
                ),
            ]
            with (
                chdir(repo_dir),
                self._record_ephemeral_directory() as ephemeral_paths,
            ):
                with self.assertRaises(db_compare_mod.CommandError) as raised:
                    db_compare_mod.db_compare(
                        plan,
                        source_argv=command,
                        chain_argv=["true"],
                    )

            self.assertFalse(ephemeral_paths[0].exists())
            self.assertIn("Command failed (3)", str(raised.exception))
            self.assertIn("[TRUNCATED] Diagnostic limited to", str(raised.exception))
            self.assertLess(
                len(str(raised.exception)), db_compare_mod.DIAGNOSTIC_LIMIT + 500
            )
            self._assert_restored_and_clean(repo_dir)
        finally:
            shutil.rmtree(repo_dir)

    def test_diff_failure_removes_ephemeral_outputs(self) -> None:
        repo_dir, plan = self._prepare_repo()
        original_git = db_compare_mod.git

        def fail_diff(*args, **kwargs):
            if args[:2] == ("diff", "--no-index"):
                return subprocess.CompletedProcess(args, 2, "", "diff failed")
            return original_git(*args, **kwargs)

        try:
            with (
                chdir(repo_dir),
                self._record_ephemeral_directory() as ephemeral_paths,
                patch.object(db_compare_mod, "git", side_effect=fail_diff),
            ):
                with self.assertRaisesRegex(
                    db_compare_mod.CommandError,
                    r"(?s)Database output comparison failed \(2\).*diff failed",
                ):
                    db_compare_mod.db_compare(
                        plan,
                        source_argv=["cat", "a.txt"],
                        chain_argv=["cat", "a.txt"],
                    )

            self.assertFalse(ephemeral_paths[0].exists())
            self._assert_restored_and_clean(repo_dir)
        finally:
            shutil.rmtree(repo_dir)

    def test_interruption_removes_outputs_and_restores_repository(self) -> None:
        repo_dir, plan = self._prepare_repo()
        original_capture = db_compare_mod.run_capture
        call_count = 0

        def interrupt_second_capture(argv, outfile):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise KeyboardInterrupt
            return original_capture(argv, outfile)

        try:
            with (
                chdir(repo_dir),
                self._record_ephemeral_directory() as ephemeral_paths,
                patch.object(
                    db_compare_mod,
                    "run_capture",
                    side_effect=interrupt_second_capture,
                ),
            ):
                with self.assertRaises(KeyboardInterrupt):
                    db_compare_mod.db_compare(
                        plan,
                        source_argv=["cat", "a.txt"],
                        chain_argv=["cat", "a.txt"],
                    )

            self.assertFalse(ephemeral_paths[0].exists())
            self._assert_restored_and_clean(repo_dir)
        finally:
            shutil.rmtree(repo_dir)

    def test_restoration_failure_still_removes_outputs_and_retries_restoration(
        self,
    ) -> None:
        repo_dir, plan = self._prepare_repo()

        @contextmanager
        def fail_restoration():
            yield
            raise db_compare_mod.CommandError("simulated restoration failure")

        try:
            with (
                chdir(repo_dir),
                self._record_ephemeral_directory() as ephemeral_paths,
                patch.object(
                    db_compare_mod,
                    "checkout_restore",
                    side_effect=fail_restoration,
                ),
            ):
                with self.assertRaisesRegex(
                    db_compare_mod.CommandError, "simulated restoration failure"
                ):
                    db_compare_mod.db_compare(
                        plan,
                        source_argv=["cat", "a.txt"],
                        chain_argv=["cat", "a.txt"],
                    )

            self.assertFalse(ephemeral_paths[0].exists())
            self._assert_restored_and_clean(repo_dir)
        finally:
            shutil.rmtree(repo_dir)

    def test_explicit_retention_reports_exact_paths_and_restricts_files(self) -> None:
        repo_dir, plan = self._prepare_repo()
        try:
            destination = repo_dir / ".carve-changesets" / "retained-db-output"
            output = io.StringIO()
            with chdir(repo_dir), redirect_stdout(output):
                db_compare_mod.db_compare(
                    plan,
                    source_argv=["cat", "a.txt"],
                    chain_argv=["cat", "a.txt"],
                    keep_output_dir=destination,
                )

            source_out = destination.resolve() / "source.txt"
            chain_out = destination.resolve() / "chain.txt"
            self.assertEqual(source_out.read_text(), chain_out.read_text())
            self.assertEqual(0o600, stat.S_IMODE(source_out.stat().st_mode))
            self.assertEqual(0o600, stat.S_IMODE(chain_out.stat().st_mode))
            self.assertIn(str(source_out), output.getvalue())
            self.assertIn(str(chain_out), output.getvalue())
            self._assert_restored_and_clean(repo_dir)
        finally:
            shutil.rmtree(repo_dir)

    def test_unignored_repository_retention_path_fails_before_branch_mutation(
        self,
    ) -> None:
        repo_dir, plan = self._prepare_repo()
        try:
            destination = repo_dir / "raw-output"
            branches_before = run(
                ["git", "for-each-ref", "--format=%(refname)", "refs/heads/"],
                cwd=repo_dir,
            ).stdout
            with chdir(repo_dir):
                with self.assertRaisesRegex(
                    db_compare_mod.CommandError,
                    "must use .carve-changesets/ or another ignored path",
                ):
                    db_compare_mod.db_compare(
                        plan,
                        source_argv=["cat", "a.txt"],
                        chain_argv=["cat", "a.txt"],
                        keep_output_dir=destination,
                    )
            branches_after = run(
                ["git", "for-each-ref", "--format=%(refname)", "refs/heads/"],
                cwd=repo_dir,
            ).stdout
            self.assertEqual(branches_before, branches_after)
            self.assertFalse(destination.exists())
            self._assert_restored_and_clean(repo_dir)
        finally:
            shutil.rmtree(repo_dir)


if __name__ == "__main__":
    unittest.main()
