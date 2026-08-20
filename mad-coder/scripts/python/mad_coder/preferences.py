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
    """Configurable editor appearance and behavior."""

    font_family: str
    font_size: int
    autocomplete_enabled: bool = True
    type_checking_enabled: bool = True


def default_font_family(available_families: list[str], system_fixed_family: str) -> str:
    """Prefer Roboto Mono when installed, otherwise use Qt's fixed-width default."""

    by_normalized_name = {family.casefold(): family for family in available_families}
    return by_normalized_name.get(PREFERRED_FONT_FAMILY.casefold(), system_fixed_family)


class PreferencesStore:
    """Load and save validated Mad Coder preferences."""

    FONT_FAMILY_KEY = "editor/font_family"
    FONT_SIZE_KEY = "editor/font_size"
    AUTOCOMPLETE_ENABLED_KEY = "autocomplete/enabled"
    TYPE_CHECKING_ENABLED_KEY = "type_checking/enabled"

    def __init__(
        self,
        backend: SettingsBackend,
        default_family: str,
        available_families: list[str],
    ) -> None:
        self._backend = backend
        self._available_families = {family.casefold(): family for family in available_families}
        self.default = EditorPreferences(
            self._validated_font_family(default_family), DEFAULT_FONT_SIZE, True, True
        )

    def _validated_font_family(self, family: str) -> str:
        normalized_family = family.casefold()
        if normalized_family in self._available_families:
            return self._available_families[normalized_family]
        return next(iter(self._available_families.values()), family)

    def load(self) -> EditorPreferences:
        family = str(self._backend.value(self.FONT_FAMILY_KEY, self.default.font_family))
        family = self._validated_font_family(family)

        raw_size = self._backend.value(self.FONT_SIZE_KEY, self.default.font_size)
        try:
            size = int(raw_size)
        except (TypeError, ValueError):
            size = self.default.font_size
        size = max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, size))

        raw_autocomplete = self._backend.value(
            self.AUTOCOMPLETE_ENABLED_KEY, self.default.autocomplete_enabled
        )
        autocomplete_enabled = self._validated_boolean(
            raw_autocomplete, self.default.autocomplete_enabled
        )
        raw_type_checking = self._backend.value(
            self.TYPE_CHECKING_ENABLED_KEY, self.default.type_checking_enabled
        )
        type_checking_enabled = self._validated_boolean(
            raw_type_checking, self.default.type_checking_enabled
        )
        return EditorPreferences(family, size, autocomplete_enabled, type_checking_enabled)

    @staticmethod
    def _validated_boolean(value: Any, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value != 0
        if isinstance(value, str):
            normalized = value.strip().casefold()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
        return default

    def save(self, preferences: EditorPreferences) -> None:
        family = self._validated_font_family(preferences.font_family)
        size = max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, preferences.font_size))
        self._backend.setValue(self.FONT_FAMILY_KEY, family)
        self._backend.setValue(self.FONT_SIZE_KEY, size)
        self._backend.setValue(self.AUTOCOMPLETE_ENABLED_KEY, preferences.autocomplete_enabled)
        self._backend.setValue(self.TYPE_CHECKING_ENABLED_KEY, preferences.type_checking_enabled)
