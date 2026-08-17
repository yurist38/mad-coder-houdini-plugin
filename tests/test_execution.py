import logging
import sys
import unittest
from pathlib import Path

MODULE_ROOT = Path(__file__).parents[1] / "mad-coder" / "scripts" / "python"
sys.path.insert(0, str(MODULE_ROOT))

from mad_coder.execution import capture_execution  # noqa: E402


class CaptureExecutionTests(unittest.TestCase):
    def test_captures_stdout_stderr_and_logging(self) -> None:
        def action() -> None:
            print("standard output")
            print("standard error", file=sys.stderr)
            logging.getLogger("mad_coder_test").warning("logged warning")

        result = capture_execution(action)

        self.assertTrue(result.succeeded)
        self.assertIn("standard output", result.output)
        self.assertIn("standard error", result.output)
        self.assertIn("WARNING: logged warning", result.output)

    def test_captures_exception_traceback(self) -> None:
        def action() -> None:
            raise ValueError("bad script")

        result = capture_execution(action)

        self.assertFalse(result.succeeded)
        self.assertIsInstance(result.exception, ValueError)
        self.assertIn("Traceback (most recent call last)", result.output)
        self.assertIn("ValueError: bad script", result.output)

    def test_restores_streams_and_logging_handler(self) -> None:
        stdout = sys.stdout
        stderr = sys.stderr
        root_logger = logging.getLogger()
        handlers = tuple(root_logger.handlers)

        capture_execution(lambda: print("captured"))

        self.assertIs(sys.stdout, stdout)
        self.assertIs(sys.stderr, stderr)
        self.assertEqual(tuple(root_logger.handlers), handlers)

    def test_captures_system_exit_instead_of_terminating_houdini(self) -> None:
        result = capture_execution(lambda: sys.exit(7))

        self.assertFalse(result.succeeded)
        self.assertIsInstance(result.exception, SystemExit)
        self.assertIn("SystemExit: 7", result.output)


if __name__ == "__main__":
    unittest.main()
