import sys
import unittest
from pathlib import Path

MODULE_ROOT = Path(__file__).parents[1] / "mad-coder" / "scripts" / "python"
sys.path.insert(0, str(MODULE_ROOT))

from mad_coder.ruff_config import check_arguments  # noqa: E402


class CheckArgumentsTests(unittest.TestCase):
    def test_adds_houdini_builtins_as_isolated_override(self) -> None:
        arguments = check_arguments("python_sop.py", ("hou", "kwargs"))

        config_index = arguments.index("--config")
        self.assertEqual(arguments[config_index + 1], 'builtins = ["hou", "kwargs"]')
        self.assertEqual(arguments[-3:], ["--stdin-filename", "python_sop.py", "-"])

    def test_omits_empty_builtins_override(self) -> None:
        self.assertNotIn("--config", check_arguments("script.py"))

    def test_deduplicates_names_in_stable_order(self) -> None:
        arguments = check_arguments("script.py", ("hou", "hou", "kwargs"))

        config_index = arguments.index("--config")
        self.assertEqual(arguments[config_index + 1], 'builtins = ["hou", "kwargs"]')

    def test_adds_context_specific_ignored_codes(self) -> None:
        arguments = check_arguments("python_snippet.py", ("hou", "kwargs"), ("F706",))

        ignore_index = arguments.index("--ignore")
        self.assertEqual(arguments[ignore_index + 1], "F706")

    def test_rejects_invalid_python_names(self) -> None:
        with self.assertRaises(ValueError):
            check_arguments("script.py", ("not-a-name",))


if __name__ == "__main__":
    unittest.main()
