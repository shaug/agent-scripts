from __future__ import annotations

import shlex
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import helpers  # noqa: F401  # ensures sys.path is set
from command_argv import display_argv, execute_argv, parse_argv_json, validate_argv
from common import CommandError


class CommandArgvTests(unittest.TestCase):
    def test_parse_accepts_json_string_array(self) -> None:
        self.assertEqual(
            ["python3", "-c", "print('ok')"],
            parse_argv_json('["python3", "-c", "print(\'ok\')"]', label="--test-argv"),
        )

    def test_parse_rejects_malformed_json(self) -> None:
        with self.assertRaisesRegex(CommandError, "valid JSON"):
            parse_argv_json("[not-json", label="--test-argv")

    def test_validation_rejects_unsafe_or_unknown_representations(self) -> None:
        invalid_values = [
            [],
            "",
            ("just", "test"),
            {"command": ["just", "test"]},
            ["just", 1],
            ["", "test"],
            ["printf", "bad\x00argument"],
        ]
        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(CommandError):
                    validate_argv(value, label="command argv")

    def test_execution_rejects_raw_unknown_representations(self) -> None:
        invalid_values = ["x", ("python3",), {"python3": "-V"}]
        with patch("command_argv.subprocess.run") as run_mock:
            for value in invalid_values:
                with self.subTest(value=value):
                    with self.assertRaises(CommandError):
                        execute_argv(value)
            run_mock.assert_not_called()

    def test_execution_does_not_interpret_shell_metacharacters(self) -> None:
        result = execute_argv(
            [
                "python3",
                "-c",
                "import sys; print(sys.argv[1])",
                "literal; echo not-executed",
            ],
            text=True,
            capture_output=True,
        )
        self.assertEqual(0, result.returncode)
        self.assertEqual("literal; echo not-executed\n", result.stdout)

    def test_explicit_shell_semantics_remain_available(self) -> None:
        result = execute_argv(
            ["sh", "-lc", "printf '%s' explicit-shell"],
            text=True,
            capture_output=True,
        )
        self.assertEqual(0, result.returncode)
        self.assertEqual("explicit-shell", result.stdout)

    def test_explicit_shell_supports_required_shell_behaviors(self) -> None:
        with tempfile.TemporaryDirectory(prefix="carve-shell-test-") as temp_dir:
            output = Path(temp_dir) / "output.txt"
            output_arg = shlex.quote(str(output))
            script = (
                "VALUE='hello world'; export VALUE; "
                "printf '%s\\n' \"$VALUE\" | tr '[:lower:]' '[:upper:]' "
                f"> {output_arg} && printf '%s' ':done' >> {output_arg}"
            )
            result = execute_argv(["sh", "-lc", script])
            self.assertEqual(0, result.returncode)
            self.assertEqual("HELLO WORLD\n:done", output.read_text())

    def test_display_is_shell_escaped_but_execution_shape_is_unchanged(self) -> None:
        argv = ["python3", "-c", "print('hello world')"]
        self.assertEqual(
            "python3 -c 'print('\"'\"'hello world'\"'\"')'", display_argv(argv)
        )
        self.assertEqual(argv, validate_argv(argv, label="command argv"))


if __name__ == "__main__":
    unittest.main()
