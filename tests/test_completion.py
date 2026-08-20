import sys
import unittest
from pathlib import Path

MODULE_ROOT = Path(__file__).parents[1] / "mad-coder" / "scripts" / "python"
sys.path.insert(0, str(MODULE_ROOT))

from mad_coder.completion import (  # noqa: E402
    CompletionItem,
    analysis_source,
    complete_python,
    completion_prefix,
)


class AnalysisSourceTests(unittest.TestCase):
    def test_adds_context_prelude_and_reports_line_offset(self) -> None:
        source, offset = analysis_source("hou.no", ("hou", "kwargs"))

        self.assertEqual(
            source,
            "import hou as hou\nkwargs: dict[str, object] = {}\nhou.no",
        )
        self.assertEqual(offset, 2)

    def test_deduplicates_context_names(self) -> None:
        source, offset = analysis_source("hou.no", ("hou", "hou"))

        self.assertEqual(source, "import hou as hou\nhou.no")
        self.assertEqual(offset, 1)

    def test_rejects_invalid_context_name(self) -> None:
        with self.assertRaisesRegex(ValueError, "Invalid completion builtin"):
            analysis_source("", ("not-a-name",))


class CompletionPrefixTests(unittest.TestCase):
    def test_returns_identifier_before_cursor(self) -> None:
        self.assertEqual(completion_prefix("value.upper", 8), "up")

    def test_stops_at_dot(self) -> None:
        self.assertEqual(completion_prefix("value.", 6), "")

    def test_clamps_column_to_block(self) -> None:
        self.assertEqual(completion_prefix("value", 100), "value")


class JediCompletionTests(unittest.TestCase):
    def test_completes_inferred_string_member(self) -> None:
        text = "value = 'hello'\nvalue.up"

        items = complete_python(text, 2, len("value.up"), "test.py")

        self.assertIn(CompletionItem("upper", "function", "def upper"), items)

    def test_completes_context_kwargs_without_altering_cursor_coordinates(self) -> None:
        text = "kwargs.it"

        items = complete_python(text, 1, len(text), "test.py", ("kwargs",))

        self.assertTrue(any(item.name == "items" for item in items))

    def test_rejects_cursor_outside_buffer(self) -> None:
        with self.assertRaisesRegex(ValueError, "outside the buffer"):
            complete_python("value", 2, 0, "test.py")


if __name__ == "__main__":
    unittest.main()
