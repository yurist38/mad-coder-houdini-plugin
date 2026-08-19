"""Persistent user preferences independent of Houdini and Qt widgets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

DEFAULT_FONT_SIZE = 11
MIN_FONT_SIZE = 7
MAX_FONT_SIZE = 32
PREFERRED_FONT_FAMILY = "Roboto Mono"


class SettingsBackend(Protocol):
    """Small subset of the QSettings API used by Mad Coder."""

    def value(self, key: str, default: Any = None) -> Any: ...

    def setValue(self, key: str, value: Any) -> None: ...  # noqa: N802 - Qt API


@dataclass(frozen=True)
class EditorPreferences:
    """Configurable editor appearance."""

    font_family: str
    font_size: int


def default_font_family(available_families: list[str], system_fixed_family: str) -> str:
    """Prefer Roboto Mono when installed, otherwise use Qt's fixed-width default."""

    by_normalized_name = {family.casefold(): family for family in available_families}
    return by_normalized_name.get(PREFERRED_FONT_FAMILY.casefold(), system_fixed_family)


class PreferencesStore:
    """Load and save validated Mad Coder preferences."""

    FONT_FAMILY_KEY = "editor/font_family"
    FONT_SIZE_KEY = "editor/font_size"

    def __init__(
        self,
        backend: SettingsBackend,
        default_family: str,
        available_families: list[str],
    ) -> None:
        self._backend = backend
        self.default = EditorPreferences(default_family, DEFAULT_FONT_SIZE)
        self._available_families = set(available_families)

    def load(self) -> EditorPreferences:
        family = str(self._backend.value(self.FONT_FAMILY_KEY, self.default.font_family))
        if family not in self._available_families:
            family = self.default.font_family

        raw_size = self._backend.value(self.FONT_SIZE_KEY, self.default.font_size)
        try:
            size = int(raw_size)
        except (TypeError, ValueError):
            size = self.default.font_size
        size = max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, size))
        return EditorPreferences(family, size)

    def save(self, preferences: EditorPreferences) -> None:
        family = preferences.font_family
        if family not in self._available_families:
            family = self.default.font_family
        size = max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, preferences.font_size))
        self._backend.setValue(self.FONT_FAMILY_KEY, family)
        self._backend.setValue(self.FONT_SIZE_KEY, size)
