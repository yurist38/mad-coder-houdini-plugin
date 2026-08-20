import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT_ROOT = Path(__file__).parents[1] / "scripts"
SCRIPT_ROOT_PATH = str(SCRIPT_ROOT)
sys.path.insert(0, SCRIPT_ROOT_PATH)

try:
    import build_release  # noqa: E402
finally:
    sys.path.remove(SCRIPT_ROOT_PATH)


class FakeDistribution:
    def __init__(self, root: Path, files: list[Path]) -> None:
        self.root = root
        self.files = files

    def locate_file(self, path: Path) -> Path:
        return self.root / path


class LocateRuffTests(unittest.TestCase):
    def test_locates_binary_from_active_python_distribution(self) -> None:
        executable_name = "ruff.exe" if sys.platform == "win32" else "ruff"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            native_ruff = root / "bin" / executable_name
            native_ruff.parent.mkdir(parents=True)
            native_ruff.write_bytes(b"native-ruff")
            distribution = FakeDistribution(root, [Path("bin") / executable_name])

            with mock.patch.object(
                build_release.metadata,
                "distribution",
                return_value=distribution,
            ):
                result = build_release.locate_ruff()

        self.assertEqual(result, native_ruff.resolve())

    def test_reports_distribution_without_executable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            distribution = FakeDistribution(root, [Path("ruff.dist-info/METADATA")])

            with (
                mock.patch.object(
                    build_release.metadata,
                    "distribution",
                    return_value=distribution,
                ),
                self.assertRaisesRegex(RuntimeError, "Could not locate Ruff's executable"),
            ):
                build_release.locate_ruff()

    def test_reports_missing_distribution(self) -> None:
        with (
            mock.patch.object(
                build_release.metadata,
                "distribution",
                side_effect=build_release.metadata.PackageNotFoundError("ruff"),
            ),
            self.assertRaisesRegex(RuntimeError, "active Python environment"),
        ):
            build_release.locate_ruff()


if __name__ == "__main__":
    unittest.main()
