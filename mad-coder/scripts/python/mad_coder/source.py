"""Source adapters for Python code stored by Houdini."""

from __future__ import annotations

import os
import re
from typing import Any, Protocol


class SourceConflictError(RuntimeError):
    """Raised when the backing source changed after it was loaded."""


class SourceUnavailableError(RuntimeError):
    """Raised when a node, parameter, definition, or section no longer exists."""


class SourceAdapter(Protocol):
    """Interface shared by editable Houdini Python source adapters."""

    display_name: str
    lint_builtins: tuple[str, ...]
    lint_filename: str
    placeholder: str
    save_warning: str
    source_key: str

    def load(self) -> str: ...

    def save(self, text: str, expected: str | None) -> None: ...

    def read_only_reason(self) -> str | None: ...


def _hou_module(hou_module: Any | None) -> Any:
    if hou_module is None:
        import hou  # type: ignore[import-not-found]

        return hou
    return hou_module


def _filename(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")
    return f"{normalized or 'houdini_source'}.py"


class SessionSource:
    """Read and write the scene-local ``hou.session`` module."""

    display_name = "Scene · hou.session"
    lint_builtins = ("hou",)
    lint_filename = "hou_session.py"
    placeholder = "# Python stored in hou.session"
    save_warning = ""
    source_key = "session"

    def __init__(self, hou_module: Any | None = None) -> None:
        self._hou = _hou_module(hou_module)

    def load(self) -> str:
        return str(self._hou.sessionModuleSource())

    def save(self, text: str, expected: str | None) -> None:
        current = self.load()
        if expected is not None and current != expected:
            raise SourceConflictError("hou.session changed outside this editor after it was loaded")
        self._hou.setSessionModuleSource(text)

    def read_only_reason(self) -> str | None:
        return None


class NodeParameterSource:
    """Read and write Python stored in a string parameter on a node instance."""

    save_warning = ""

    def __init__(self, node_path: str, parm_name: str, hou_module: Any | None = None) -> None:
        self.node_path = node_path
        self.parm_name = parm_name
        self._hou = _hou_module(hou_module)
        self.display_name = f"Node · {node_path} · {parm_name}"
        self.lint_filename = _filename(f"{node_path}_{parm_name}")
        self.placeholder = f"# Python stored in {node_path}/{parm_name}"
        self.source_key = f"parm:{node_path}:{parm_name}"
        self.lint_builtins = ("hou",)

    def _resolve_node(self) -> Any:
        node = self._hou.node(self.node_path)
        if node is None:
            raise SourceUnavailableError(f"Node no longer exists: {self.node_path}")
        return node

    def _resolve_parm(self) -> Any:
        parm = self._resolve_node().parm(self.parm_name)
        if parm is None:
            raise SourceUnavailableError(
                f"Parameter no longer exists: {self.node_path}/{self.parm_name}"
            )
        return parm

    def load(self) -> str:
        return str(self._resolve_parm().unexpandedString())

    def save(self, text: str, expected: str | None) -> None:
        parm = self._resolve_parm()
        current = str(parm.unexpandedString())
        if expected is not None and current != expected:
            raise SourceConflictError(
                f"{self.node_path}/{self.parm_name} changed outside this editor"
            )
        with self._hou.undos.group(f"Mad Coder: {self.node_path}/{self.parm_name}"):
            parm.set(text)

    def read_only_reason(self) -> str | None:
        try:
            node = self._resolve_node()
            parm = self._resolve_parm()
            if hasattr(parm, "isLocked") and parm.isLocked():
                return "The source parameter is locked."
            if (
                hasattr(node, "isInsideLockedHDA")
                and node.isInsideLockedHDA()
                and hasattr(node, "isEditableInsideLockedHDA")
                and not node.isEditableInsideLockedHDA()
            ):
                return "The source node is inside a locked digital asset."
        except SourceUnavailableError as exc:
            return str(exc)
        return None


class HDASectionSource:
    """Read and write a textual Python section on an HDA definition."""

    def __init__(
        self,
        node_path: str,
        section_name: str = "PythonModule",
        hou_module: Any | None = None,
    ) -> None:
        self.node_path = node_path
        self.section_name = section_name
        self._hou = _hou_module(hou_module)
        node = self._resolve_node()
        type_name = node.type().name()
        self.display_name = f"Asset · {type_name} · {section_name}"
        self.lint_builtins = ("hou", "kwargs")
        self.lint_filename = _filename(f"{type_name}_{section_name}")
        self.placeholder = f"# {section_name} for {type_name}"
        self.save_warning = (
            "Saving changes the digital asset definition and affects every instance of this asset."
        )
        self.source_key = f"hda:{node_path}:{section_name}"

    def _resolve_node(self) -> Any:
        node = self._hou.node(self.node_path)
        if node is None:
            raise SourceUnavailableError(f"Node no longer exists: {self.node_path}")
        return node

    def _resolve_definition(self) -> Any:
        definition = self._resolve_node().type().definition()
        if definition is None:
            raise SourceUnavailableError(f"Node is not a digital asset: {self.node_path}")
        return definition

    def _resolve_section(self) -> Any:
        section = self._resolve_definition().sections().get(self.section_name)
        if section is None:
            raise SourceUnavailableError(f"Asset section no longer exists: {self.section_name}")
        return section

    def load(self) -> str:
        return str(self._resolve_section().contents())

    def save(self, text: str, expected: str | None) -> None:
        section = self._resolve_section()
        current = str(section.contents())
        if expected is not None and current != expected:
            raise SourceConflictError(f"{self.display_name} changed outside this editor")
        section.setContents(text)

    def read_only_reason(self) -> str | None:
        try:
            library_path = str(self._resolve_definition().libraryFilePath())
        except SourceUnavailableError as exc:
            return str(exc)
        if library_path != "Embedded" and not os.access(library_path, os.W_OK):
            return f"The asset library is not writable: {library_path}"
        return None


def python_sources_for_node(node: Any, hou_module: Any | None = None) -> list[SourceAdapter]:
    """Discover supported Python sources for a selected Houdini node."""

    hou_module = _hou_module(hou_module)
    sources: list[SourceAdapter] = []
    node_path = str(node.path())
    type_name = str(node.type().name()).lower()
    normalized_type_name = re.sub(r"[^a-z0-9]+", "", type_name)

    candidates = ["python", "pythoncode", "pythonscript"]
    if "python" in type_name:
        candidates.extend(["script", "code"])

    seen: set[str] = set()
    for parm_name in candidates:
        if parm_name in seen:
            continue
        seen.add(parm_name)
        parm = node.parm(parm_name)
        if parm is None:
            continue
        try:
            parm.unexpandedString()
        except Exception:
            continue
        source = NodeParameterSource(node_path, parm_name, hou_module)
        if "pythonsnippet" in normalized_type_name:
            source.lint_builtins = ("hou", "kwargs")
        sources.append(source)

    try:
        definition = node.type().definition()
        if definition is not None and "PythonModule" in definition.sections():
            sources.append(HDASectionSource(node_path, "PythonModule", hou_module))
    except Exception:
        pass

    return sources
