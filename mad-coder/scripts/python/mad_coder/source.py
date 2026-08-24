"""Source adapters for Python and VEX code stored by Houdini."""

from __future__ import annotations

import os
import re
from typing import Any, Protocol

SUPPORTED_HDA_PYTHON_SECTIONS = ("PythonModule", "ViewerStateModule")


class SourceConflictError(RuntimeError):
    """Raised when the backing source changed after it was loaded."""


class SourceUnavailableError(RuntimeError):
    """Raised when a node, parameter, definition, or section no longer exists."""


class SourceAdapter(Protocol):
    """Interface shared by editable Houdini code source adapters."""

    display_name: str
    language: str
    lint_builtins: tuple[str, ...]
    lint_filename: str
    lint_ignores: tuple[str, ...]
    placeholder: str
    save_warning: str
    source_key: str

    def load(self) -> str: ...

    def save(self, text: str, expected: str | None) -> None: ...

    def execute(self) -> None: ...

    def read_only_reason(self) -> str | None: ...


def _hou_module(hou_module: Any | None) -> Any:
    if hou_module is None:
        import hou  # type: ignore[import-not-found]

        return hou
    return hou_module


def _filename(value: str, extension: str = "py") -> str:
    normalized = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")
    return f"{normalized or 'houdini_source'}.{extension}"


class SessionSource:
    """Read and write the scene-local ``hou.session`` module."""

    display_name = "Scene · hou.session"
    language = "python"
    lint_builtins: tuple[str, ...] = ("hou",)
    lint_filename = "hou_session.py"
    lint_ignores: tuple[str, ...] = ()
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

    def execute(self) -> None:
        """The session module is evaluated by ``save``."""


class NodeParameterSource:
    """Read and write code stored in a string parameter on a node instance."""

    save_warning = ""

    def __init__(
        self,
        node_path: str,
        parm_name: str,
        hou_module: Any | None = None,
        *,
        language: str = "python",
    ) -> None:
        self.node_path = node_path
        self.parm_name = parm_name
        self._hou = _hou_module(hou_module)
        self.language = language
        label = "VEX" if language == "vex" else "Node"
        self.display_name = f"{label} · {node_path} · {parm_name}"
        extension = "vfl" if language == "vex" else "py"
        self.lint_filename = _filename(f"{node_path}_{parm_name}", extension)
        self.lint_ignores: tuple[str, ...] = ()
        comment = "//" if language == "vex" else "#"
        self.placeholder = f"{comment} {language.upper()} stored in {node_path}/{parm_name}"
        self.source_key = f"parm:{node_path}:{parm_name}"
        self.lint_builtins: tuple[str, ...] = () if language == "vex" else ("hou",)

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

    def execute(self) -> None:
        """Force the node to cook in its native Houdini context."""

        node = self._resolve_node()
        node.cook(force=True)
        if hasattr(node, "errors"):
            errors = tuple(node.errors())
            if errors:
                raise RuntimeError("Node cook failed:\n" + "\n".join(map(str, errors)))


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
        self.language = "python"
        self.lint_builtins: tuple[str, ...] = ("hou", "kwargs")
        self.lint_filename = _filename(f"{type_name}_{section_name}")
        self.lint_ignores: tuple[str, ...] = ()
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

    def execute(self) -> None:
        """Reload the edited HDA module using its section-specific Houdini API."""

        node = self._resolve_node()
        if self.section_name == "ViewerStateModule":
            module = node.hdaViewerStateModule()
            self._hou.hda.reloadHDAViewerStateModule(module)
            return
        node.type().hdaModule()


def _parameter_language(parm: Any) -> str | None:
    """Read Houdini's documented editor language tag from a parameter."""

    try:
        tags = parm.parmTemplate().tags()
    except Exception:
        return None
    language = str(tags.get("editorlang", "")).strip().casefold()
    return language if language in {"python", "vex"} else None


def code_sources_for_node(node: Any, hou_module: Any | None = None) -> list[SourceAdapter]:
    """Discover supported Python and VEX sources for a selected Houdini node."""

    hou_module = _hou_module(hou_module)
    sources: list[SourceAdapter] = []
    node_path = str(node.path())
    type_name = str(node.type().name()).lower()
    normalized_type_name = re.sub(r"[^a-z0-9]+", "", type_name)

    candidates: list[tuple[str, str]] = []
    try:
        for parm in node.parms():
            language = _parameter_language(parm)
            if language is not None:
                candidates.append((str(parm.name()), language))
    except Exception:
        pass

    legacy_python_candidates = ["python", "pythoncode", "pythonscript"]
    if "python" in type_name:
        legacy_python_candidates.extend(["script", "code"])
    candidates.extend((name, "python") for name in legacy_python_candidates)

    seen: set[str] = set()
    for parm_name, language in candidates:
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
        source = NodeParameterSource(node_path, parm_name, hou_module, language=language)
        if language == "python" and "pythonsnippet" in normalized_type_name:
            source.lint_builtins = ("hou", "kwargs")
            # Houdini executes Python Snippet parameters as a function body, where a
            # top-level return is valid even though Ruff sees the buffer as a module.
            source.lint_ignores = ("F706",)
        sources.append(source)

    try:
        definition = node.type().definition()
        if definition is not None:
            sections = definition.sections()
            for section_name in SUPPORTED_HDA_PYTHON_SECTIONS:
                if section_name in sections:
                    sources.append(HDASectionSource(node_path, section_name, hou_module))
    except Exception:
        pass

    return sources


def python_sources_for_node(node: Any, hou_module: Any | None = None) -> list[SourceAdapter]:
    """Backward-compatible alias for callers predating VEX source support."""

    return code_sources_for_node(node, hou_module)
