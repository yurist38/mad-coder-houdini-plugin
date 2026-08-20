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


class LocateTyTests(unittest.TestCase):
    def test_locates_binary_from_active_python_distribution(self) -> None:
        executable_name = "ty.exe" if sys.platform == "win32" else "ty"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            native_ty = root / "bin" / executable_name
            native_ty.parent.mkdir(parents=True)
            native_ty.write_bytes(b"native-ty")
            distribution = FakeDistribution(root, [Path("bin") / executable_name])

            with mock.patch.object(
                build_release.metadata,
                "distribution",
                return_value=distribution,
            ):
                result = build_release.locate_ty()

        self.assertEqual(result, native_ty.resolve())


class CopyPythonDistributionTests(unittest.TestCase):
    def test_copies_importable_files_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            module = root / "example" / "__init__.py"
            metadata_file = root / "example-1.0.dist-info" / "METADATA"
            bytecode = root / "example" / "__pycache__" / "module.pyc"
            for path in (module, metadata_file, bytecode):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(path.name)
            distribution = FakeDistribution(
                root,
                [
                    Path("example/__init__.py"),
                    Path("example-1.0.dist-info/METADATA"),
                    Path("example/__pycache__/module.pyc"),
                    Path("../../../bin/example"),
                ],
            )
            destination = root / "release"

            with mock.patch.object(
                build_release.metadata,
                "distribution",
                return_value=distribution,
            ):
                build_release.copy_python_distribution("example", destination)

            self.assertTrue((destination / "example" / "__init__.py").is_file())
            self.assertTrue((destination / "example-1.0.dist-info" / "METADATA").is_file())
            self.assertFalse((destination / "example" / "__pycache__").exists())

    def test_copies_distribution_license(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            license_file = root / "example-1.0.dist-info" / "LICENSE.txt"
            license_file.parent.mkdir(parents=True)
            license_file.write_text("Example license")
            distribution = FakeDistribution(
                root,
                [Path("example-1.0.dist-info/LICENSE.txt")],
            )
            destination = root / "release"
            destination.mkdir()

            with mock.patch.object(
                build_release.metadata,
                "distribution",
                return_value=distribution,
            ):
                build_release.copy_distribution_license("example-package", destination)

            self.assertEqual(
                (destination / "EXAMPLE_PACKAGE_LICENSE").read_text(),
                "Example license",
            )

    def test_uses_repository_license_when_wheel_omits_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = root / "release"
            destination.mkdir()
            distribution = FakeDistribution(root, [])

            with mock.patch.object(
                build_release.metadata,
                "distribution",
                return_value=distribution,
            ):
                build_release.copy_distribution_license("types-houdini", destination)

            copied_license = destination / "TYPES_HOUDINI_LICENSE"
            self.assertIn("Apache License", copied_license.read_text())


if __name__ == "__main__":
    unittest.main()
