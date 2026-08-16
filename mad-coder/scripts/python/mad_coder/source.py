"""Source adapters for code stored by Houdini."""

from __future__ import annotations

from typing import Any


class SourceConflictError(RuntimeError):
    """Raised when the backing source changed after it was loaded."""


class SessionSource:
    """Read and write the scene-local ``hou.session`` module."""

    display_name = "Scene · hou.session"
    lint_filename = "hou_session.py"

    def __init__(self, hou_module: Any | None = None) -> None:
        if hou_module is None:
            import hou  # type: ignore[import-not-found]

            hou_module = hou
        self._hou = hou_module

    def load(self) -> str:
        return str(self._hou.sessionModuleSource())

    def save(self, text: str, expected: str | None) -> None:
        current = self.load()
        if expected is not None and current != expected:
            raise SourceConflictError("hou.session changed outside this editor after it was loaded")
        self._hou.setSessionModuleSource(text)
