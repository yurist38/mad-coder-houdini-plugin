import sys
import unittest
from pathlib import Path
from typing import Any

MODULE_ROOT = Path(__file__).parents[1] / "mad-coder" / "scripts" / "python"
sys.path.insert(0, str(MODULE_ROOT))

from mad_coder.preferences import (  # noqa: E402
    DEFAULT_FONT_SIZE,
    EditorPreferences,
    PreferencesStore,
    default_font_family,
)


class FakeSettings:
    def __init__(self, values: dict[str, Any] | None = None) -> None:
        self.values = values or {}

    def value(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)

    def setValue(self, key: str, value: Any) -> None:  # noqa: N802 - Qt API
        self.values[key] = value


class DefaultFontFamilyTests(unittest.TestCase):
    def test_prefers_roboto_mono_when_installed(self) -> None:
        family = default_font_family(["Menlo", "Roboto Mono"], "Menlo")

        self.assertEqual(family, "Roboto Mono")

    def test_matches_preferred_font_case_insensitively(self) -> None:
        family = default_font_family(["ROBOTO MONO", "Menlo"], "Menlo")

        self.assertEqual(family, "ROBOTO MONO")

    def test_falls_back_to_system_fixed_font(self) -> None:
        self.assertEqual(default_font_family(["Menlo"], "Menlo"), "Menlo")


class PreferencesStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.backend = FakeSettings()
        self.store = PreferencesStore(self.backend, "Menlo", ["Menlo", "Roboto Mono"])

    def test_loads_defaults(self) -> None:
        self.assertEqual(self.store.load(), EditorPreferences("Menlo", DEFAULT_FONT_SIZE))

    def test_round_trips_font_preferences(self) -> None:
        expected = EditorPreferences("Roboto Mono", 14)

        self.store.save(expected)

        self.assertEqual(self.store.load(), expected)

    def test_missing_saved_font_falls_back_to_default(self) -> None:
        self.backend.values[PreferencesStore.FONT_FAMILY_KEY] = "Missing Mono"

        self.assertEqual(self.store.load().font_family, "Menlo")

    def test_saved_font_matches_available_family_case_insensitively(self) -> None:
        self.backend.values[PreferencesStore.FONT_FAMILY_KEY] = "roboto mono"

        self.assertEqual(self.store.load().font_family, "Roboto Mono")

    def test_unavailable_default_falls_back_to_available_family(self) -> None:
        store = PreferencesStore(self.backend, "Missing Mono", ["Menlo", "Roboto Mono"])
        self.backend.values[PreferencesStore.FONT_FAMILY_KEY] = "Missing Mono"

        self.assertEqual(store.load().font_family, "Menlo")

    def test_save_with_unavailable_default_stores_available_family(self) -> None:
        store = PreferencesStore(self.backend, "Missing Mono", ["Menlo", "Roboto Mono"])

        store.save(EditorPreferences("Missing Mono", 14))

        self.assertEqual(self.backend.values[PreferencesStore.FONT_FAMILY_KEY], "Menlo")

    def test_invalid_size_falls_back_to_default(self) -> None:
        self.backend.values[PreferencesStore.FONT_SIZE_KEY] = "large"

        self.assertEqual(self.store.load().font_size, DEFAULT_FONT_SIZE)

    def test_size_is_clamped(self) -> None:
        self.backend.values[PreferencesStore.FONT_SIZE_KEY] = 100

        self.assertEqual(self.store.load().font_size, 32)


if __name__ == "__main__":
    unittest.main()
