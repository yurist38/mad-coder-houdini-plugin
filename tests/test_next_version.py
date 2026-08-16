import sys
import unittest
from pathlib import Path

SCRIPT_ROOT = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_ROOT))

from next_version import next_version  # noqa: E402


class NextVersionTests(unittest.TestCase):
    def test_fix_increments_patch(self) -> None:
        self.assertEqual(next_version(["v1.2.3"], "fix"), "v1.2.4")

    def test_minor_increments_minor_and_resets_patch(self) -> None:
        self.assertEqual(next_version(["v1.2.3"], "minor"), "v1.3.0")

    def test_major_increments_major_and_resets_lower_parts(self) -> None:
        self.assertEqual(next_version(["v1.2.3"], "major"), "v2.0.0")

    def test_uses_highest_version_not_tag_order(self) -> None:
        tags = ["v1.9.9", "v2.0.0", "v1.10.0"]
        self.assertEqual(next_version(tags, "fix"), "v2.0.1")

    def test_ignores_non_release_and_prerelease_tags(self) -> None:
        tags = ["latest", "v3.0.0-beta.1", "build-20", "v2.4.1"]
        self.assertEqual(next_version(tags, "minor"), "v2.5.0")

    def test_initial_versions(self) -> None:
        self.assertEqual(next_version([], "fix"), "v0.0.1")
        self.assertEqual(next_version([], "minor"), "v0.1.0")
        self.assertEqual(next_version([], "major"), "v1.0.0")

    def test_rejects_unknown_release_type(self) -> None:
        with self.assertRaises(ValueError):
            next_version(["v1.0.0"], "preview")


if __name__ == "__main__":
    unittest.main()
