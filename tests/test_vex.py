import sys
import unittest
from pathlib import Path

MODULE_ROOT = Path(__file__).parents[1] / "mad-coder" / "scripts" / "python"
sys.path.insert(0, str(MODULE_ROOT))

from mad_coder.vex import parse_vcc_output, vex_snippet_source  # noqa: E402


class VexSnippetSourceTests(unittest.TestCase):
    def test_wraps_common_and_explicit_attribute_bindings(self) -> None:
        analysis = vex_snippet_source("@P += v@N;\ni[]@ids = array(1, 2);\n")

        self.assertIn("vector _bound_P", analysis.source)
        self.assertIn("vector _bound_N", analysis.source)
        self.assertIn("int _bound_ids[]", analysis.source)
        self.assertIn("_bound_P += _bound_N", analysis.source)
        self.assertNotIn("v@N", analysis.source)

    def test_does_not_treat_comments_or_strings_as_bindings(self) -> None:
        analysis = vex_snippet_source(
            'string address = "artist@example.com"; // v@ignored\n/* @also_ignored */\n'
        )

        self.assertNotIn("_bound_ignored", analysis.source)
        self.assertNotIn("_bound_example", analysis.source)
        self.assertIn('"artist@example.com"', analysis.source)

    def test_converts_attribute_prototype_to_function_argument(self) -> None:
        analysis = vex_snippet_source("vector @direction;\n@direction = {0, 1, 0};\n")

        self.assertEqual(analysis.source.count("vector _bound_direction"), 1)
        self.assertIn("// Attribute prototype for direction", analysis.source)

    def test_deduplicates_mixed_binding_references(self) -> None:
        analysis = vex_snippet_source("v@P += @P;\n")

        self.assertEqual(analysis.source.count("vector _bound_P"), 1)


class ParseVccOutputTests(unittest.TestCase):
    def test_maps_generated_line_and_column_to_original_snippet(self) -> None:
        source = "float value = 1;\n@P += {1, 0, ;\n"
        analysis = vex_snippet_source(source)
        payload = "/tmp/check.vfl:5:20: Error 1088: Syntax error, expecting '}'."

        diagnostic = parse_vcc_output(payload, analysis=analysis)[0]

        self.assertEqual(diagnostic.line, 2)
        self.assertEqual(diagnostic.column, 14)
        self.assertEqual(diagnostic.code, "VEX1088")
        self.assertEqual(diagnostic.severity, "error")

    def test_parses_warning_and_column_range(self) -> None:
        payload = "/tmp/check.vfl:2:4-9: Warning 2001: Suspicious expression."

        diagnostic = parse_vcc_output(payload)[0]

        self.assertEqual(diagnostic.line, 2)
        self.assertEqual(diagnostic.column, 4)
        self.assertEqual(diagnostic.end_column, 9)
        self.assertEqual(diagnostic.severity, "warning")

    def test_parses_windows_drive_letter_path(self) -> None:
        payload = r"C:\Users\artist\check.vfl:2:4: Error 1088: Syntax error."

        diagnostic = parse_vcc_output(payload)[0]

        self.assertEqual(diagnostic.line, 2)
        self.assertEqual(diagnostic.column, 4)
        self.assertEqual(diagnostic.code, "VEX1088")

    def test_appends_continuation_lines_to_previous_message(self) -> None:
        payload = "/tmp/check.vfl:2:4: Error 1000: Candidates are:\nfloat foo(float)"

        diagnostic = parse_vcc_output(payload)[0]

        self.assertIn("float foo(float)", diagnostic.message)

    def test_ignores_unrecognized_output_without_a_diagnostic(self) -> None:
        self.assertEqual(parse_vcc_output("License server message"), [])


if __name__ == "__main__":
    unittest.main()
