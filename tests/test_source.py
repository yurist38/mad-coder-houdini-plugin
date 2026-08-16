import sys
import unittest
from pathlib import Path

MODULE_ROOT = Path(__file__).parents[1] / "mad-coder" / "scripts" / "python"
sys.path.insert(0, str(MODULE_ROOT))

from mad_coder.source import SessionSource, SourceConflictError  # noqa: E402


class FakeHou:
    def __init__(self, source: str = "") -> None:
        self.source = source

    def sessionModuleSource(self) -> str:
        return self.source

    def setSessionModuleSource(self, source: str) -> None:
        self.source = source


class SessionSourceTests(unittest.TestCase):
    def test_loads_and_saves(self) -> None:
        hou = FakeHou("answer = 41\n")
        source = SessionSource(hou)

        source.save("answer = 42\n", expected="answer = 41\n")

        self.assertEqual(source.load(), "answer = 42\n")

    def test_detects_external_change(self) -> None:
        hou = FakeHou("answer = 41\n")
        source = SessionSource(hou)
        hou.source = "answer = 99\n"

        with self.assertRaises(SourceConflictError):
            source.save("answer = 42\n", expected="answer = 41\n")

    def test_can_explicitly_overwrite(self) -> None:
        hou = FakeHou("external = True\n")
        source = SessionSource(hou)

        source.save("mine = True\n", expected=None)

        self.assertEqual(hou.source, "mine = True\n")


if __name__ == "__main__":
    unittest.main()
