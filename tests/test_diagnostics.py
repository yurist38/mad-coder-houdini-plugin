import json
import sys
import unittest
from pathlib import Path

MODULE_ROOT = Path(__file__).parents[1] / "mad-coder" / "scripts" / "python"
sys.path.insert(0, str(MODULE_ROOT))

from mad_coder.diagnostics import parse_ruff_output  # noqa: E402


class ParseRuffOutputTests(unittest.TestCase):
    def test_parses_locations_and_fixability(self) -> None:
        payload = json.dumps(
            [
                {
                    "code": "F401",
                    "message": "`os` imported but unused",
                    "location": {"row": 3, "column": 1},
                    "end_location": {"row": 3, "column": 10},
                    "fix": {"applicability": "safe", "edits": []},
                }
            ]
        )

        diagnostics = parse_ruff_output(payload)

        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].code, "F401")
        self.assertEqual(diagnostics[0].line, 3)
        self.assertEqual(diagnostics[0].end_column, 10)
        self.assertTrue(diagnostics[0].fixable)
        self.assertEqual(diagnostics[0].severity, "warning")

    def test_marks_syntax_diagnostics_as_errors(self) -> None:
        payload = json.dumps(
            [
                {
                    "code": "invalid-syntax",
                    "message": "Expected an expression",
                    "location": {"row": 1, "column": 4},
                    "end_location": {"row": 1, "column": 5},
                }
            ]
        )

        diagnostic = parse_ruff_output(payload)[0]

        self.assertEqual(diagnostic.severity, "error")

    def test_rejects_invalid_json_shape(self) -> None:
        with self.assertRaises(ValueError):
            parse_ruff_output("{}")


if __name__ == "__main__":
    unittest.main()
