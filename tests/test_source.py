import sys
import unittest
from pathlib import Path

MODULE_ROOT = Path(__file__).parents[1] / "mad-coder" / "scripts" / "python"
sys.path.insert(0, str(MODULE_ROOT))

from mad_coder.source import (  # noqa: E402
    HDASectionSource,
    NodeParameterSource,
    SessionSource,
    SourceConflictError,
    SourceUnavailableError,
    python_sources_for_node,
)


class FakeUndoGroup:
    def __init__(self, undos: "FakeUndos", label: str) -> None:
        self.undos = undos
        self.label = label

    def __enter__(self) -> None:
        self.undos.labels.append(self.label)

    def __exit__(self, *_args: object) -> None:
        return None


class FakeUndos:
    def __init__(self) -> None:
        self.labels: list[str] = []

    def group(self, label: str) -> FakeUndoGroup:
        return FakeUndoGroup(self, label)


class FakeParm:
    def __init__(self, source: str, *, locked: bool = False) -> None:
        self.source = source
        self.locked = locked

    def unexpandedString(self) -> str:
        return self.source

    def set(self, source: str) -> None:
        self.source = source

    def isLocked(self) -> bool:
        return self.locked


class FakeSection:
    def __init__(self, source: str) -> None:
        self.source = source

    def contents(self) -> str:
        return self.source

    def setContents(self, source: str) -> None:
        self.source = source


class FakeDefinition:
    def __init__(self, section: FakeSection | None = None, library: str = "Embedded") -> None:
        self.section = section
        self.library = library

    def sections(self) -> dict[str, FakeSection]:
        return {"PythonModule": self.section} if self.section is not None else {}

    def libraryFilePath(self) -> str:
        return self.library


class FakeNodeType:
    def __init__(self, name: str, definition: FakeDefinition | None = None) -> None:
        self._name = name
        self._definition = definition
        self.hda_module_loads = 0

    def name(self) -> str:
        return self._name

    def definition(self) -> FakeDefinition | None:
        return self._definition

    def hdaModule(self) -> object:
        self.hda_module_loads += 1
        return object()


class FakeNode:
    def __init__(
        self,
        path: str,
        node_type: FakeNodeType,
        parms: dict[str, FakeParm] | None = None,
        *,
        inside_locked_hda: bool = False,
        editable_inside_locked_hda: bool = True,
    ) -> None:
        self._path = path
        self._type = node_type
        self._parms = parms or {}
        self._inside_locked_hda = inside_locked_hda
        self._editable_inside_locked_hda = editable_inside_locked_hda
        self.cooks: list[bool] = []
        self.cook_errors: tuple[str, ...] = ()

    def path(self) -> str:
        return self._path

    def type(self) -> FakeNodeType:
        return self._type

    def parm(self, name: str) -> FakeParm | None:
        return self._parms.get(name)

    def isInsideLockedHDA(self) -> bool:
        return self._inside_locked_hda

    def isEditableInsideLockedHDA(self) -> bool:
        return self._editable_inside_locked_hda

    def cook(self, *, force: bool = False) -> None:
        self.cooks.append(force)

    def errors(self) -> tuple[str, ...]:
        return self.cook_errors


class FakeHou:
    def __init__(self, source: str = "", nodes: list[FakeNode] | None = None) -> None:
        self.source = source
        self.nodes = {node.path(): node for node in nodes or []}
        self.undos = FakeUndos()

    def sessionModuleSource(self) -> str:
        return self.source

    def setSessionModuleSource(self, source: str) -> None:
        self.source = source

    def node(self, path: str) -> FakeNode | None:
        return self.nodes.get(path)


class SessionSourceTests(unittest.TestCase):
    def test_exposes_houdini_lint_context(self) -> None:
        self.assertEqual(SessionSource(FakeHou()).lint_builtins, ("hou",))

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


class NodeParameterSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parm = FakeParm("answer = 41\n")
        self.node = FakeNode("/obj/python1", FakeNodeType("python"), {"python": self.parm})
        self.hou = FakeHou(nodes=[self.node])
        self.source = NodeParameterSource("/obj/python1", "python", self.hou)

    def test_loads_and_saves_with_undo_group(self) -> None:
        self.source.save("answer = 42\n", expected="answer = 41\n")

        self.assertEqual(self.source.load(), "answer = 42\n")
        self.assertEqual(self.hou.undos.labels, ["Mad Coder: /obj/python1/python"])

    def test_exposes_python_sop_lint_context(self) -> None:
        self.assertEqual(self.source.lint_builtins, ("hou",))

    def test_executes_by_forcing_node_cook(self) -> None:
        self.source.execute()

        self.assertEqual(self.node.cooks, [True])

    def test_reports_node_cook_errors(self) -> None:
        self.node.cook_errors = ("Python error: broken script",)

        with self.assertRaisesRegex(RuntimeError, "broken script"):
            self.source.execute()

    def test_detects_external_change(self) -> None:
        self.parm.source = "external = True\n"

        with self.assertRaises(SourceConflictError):
            self.source.save("mine = True\n", expected="answer = 41\n")

    def test_reports_locked_parameter_as_read_only(self) -> None:
        self.parm.locked = True

        self.assertEqual(self.source.read_only_reason(), "The source parameter is locked.")

    def test_reports_missing_node(self) -> None:
        del self.hou.nodes["/obj/python1"]

        with self.assertRaises(SourceUnavailableError):
            self.source.load()


class HDASectionSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.section = FakeSection("def create():\n    pass\n")
        self.definition = FakeDefinition(self.section)
        self.node = FakeNode("/obj/tool1", FakeNodeType("mad::tool", self.definition))
        self.hou = FakeHou(nodes=[self.node])
        self.source = HDASectionSource("/obj/tool1", "PythonModule", self.hou)

    def test_loads_and_saves(self) -> None:
        updated = "def create():\n    return 42\n"

        self.source.save(updated, expected=self.section.source)

        self.assertEqual(self.source.load(), updated)

    def test_exposes_hda_lint_context(self) -> None:
        self.assertEqual(self.source.lint_builtins, ("hou", "kwargs"))

    def test_executes_by_loading_hda_module(self) -> None:
        self.source.execute()

        self.assertEqual(self.node.type().hda_module_loads, 1)

    def test_detects_external_change(self) -> None:
        expected = self.section.source
        self.section.source = "external = True\n"

        with self.assertRaises(SourceConflictError):
            self.source.save("mine = True\n", expected=expected)

    def test_embedded_definition_is_writable(self) -> None:
        self.assertIsNone(self.source.read_only_reason())

    def test_missing_library_is_read_only(self) -> None:
        self.definition.library = "/path/that/does/not/exist/tool.hda"

        self.assertIn("not writable", self.source.read_only_reason() or "")


class SourceDiscoveryTests(unittest.TestCase):
    def test_discovers_python_parameter_and_hda_module(self) -> None:
        section = FakeSection("VALUE = 1\n")
        node = FakeNode(
            "/obj/python1",
            FakeNodeType("python", FakeDefinition(section)),
            {"python": FakeParm("print('node')\n")},
        )
        hou = FakeHou(nodes=[node])

        sources = python_sources_for_node(node, hou)

        self.assertEqual(
            [type(source) for source in sources],
            [NodeParameterSource, HDASectionSource],
        )
        self.assertEqual(sources[0].source_key, "parm:/obj/python1:python")
        self.assertEqual(sources[1].source_key, "hda:/obj/python1:PythonModule")

    def test_python_snippet_exposes_kwargs(self) -> None:
        node = FakeNode(
            "/obj/python_snippet1",
            FakeNodeType("python_snippet"),
            {"python": FakeParm("return kwargs['geo']\n")},
        )
        hou = FakeHou(nodes=[node])

        sources = python_sources_for_node(node, hou)

        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0].lint_builtins, ("hou", "kwargs"))


if __name__ == "__main__":
    unittest.main()
