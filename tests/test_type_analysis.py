import ast
import sys
import unittest
from pathlib import Path

MODULE_ROOT = Path(__file__).parents[1] / "mad-coder" / "scripts" / "python"
sys.path.insert(0, str(MODULE_ROOT))

from mad_coder.type_analysis import type_analysis_source  # noqa: E402


class TypeAnalysisSourceTests(unittest.TestCase):
    def test_adds_houdini_context_before_editor_source(self) -> None:
        source, offset = type_analysis_source(
            'hou.node("/")\n"some string".upper()\n', ("hou", "kwargs")
        )

        self.assertEqual(offset, 2)
        self.assertTrue(source.startswith("import hou as hou\nkwargs: dict[str, object] = {}\n"))
        self.assertEqual(source.splitlines()[offset], 'hou.node("/")')

    def test_keeps_future_imports_valid_and_preserves_line_mapping(self) -> None:
        text = "from __future__ import annotations\nvalue: Missing | None = None\n"

        source, offset = type_analysis_source(text, ("hou",))

        ast.parse(source)
        self.assertTrue(
            source.startswith("from __future__ import annotations\nimport hou as hou\n")
        )
        self.assertEqual(source.splitlines()[offset + 1], "value: Missing | None = None")

    def test_does_not_change_source_without_context_globals(self) -> None:
        text = "answer = 42\n"

        self.assertEqual(type_analysis_source(text, ()), (text, 0))


if __name__ == "__main__":
    unittest.main()
