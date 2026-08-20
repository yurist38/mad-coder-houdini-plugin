"""Build a user-installable Houdini package archive."""

from __future__ import annotations

import argparse
import shutil
import stat
import sys
import tempfile
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLED_PYTHON_DISTRIBUTIONS = ("jedi", "parso", "types-houdini")
BUNDLED_LICENSE_FALLBACKS = {
    "types-houdini": ROOT / "licenses" / "TYPES_HOUDINI_LICENSE",
}


def locate_distribution_executable(distribution_name: str, executable_name: str) -> Path:
    """Locate a native executable from its active Python distribution."""

    display_name = "Ruff" if distribution_name == "ruff" else distribution_name
    try:
        distribution = metadata.distribution(distribution_name)
    except metadata.PackageNotFoundError as exc:
        raise RuntimeError(
            f"{display_name} must be installed in the active Python environment"
        ) from exc

    for relative_path in distribution.files or ():
        if relative_path.name != executable_name:
            continue
        executable = Path(str(distribution.locate_file(relative_path))).resolve()
        if executable.is_file():
            return executable
    raise RuntimeError(
        f"Could not locate {display_name}'s executable in its installed distribution"
    )


def locate_ruff() -> Path:
    """Locate Ruff from the distribution installed for the active Python."""

    executable_name = "ruff.exe" if sys.platform == "win32" else "ruff"
    return locate_distribution_executable("ruff", executable_name)


def locate_ty() -> Path:
    """Locate ty from the distribution installed for the active Python."""

    executable_name = "ty.exe" if sys.platform == "win32" else "ty"
    return locate_distribution_executable("ty", executable_name)


def copy_ruff_license(destination: Path) -> None:
    try:
        distribution = metadata.distribution("ruff")
    except metadata.PackageNotFoundError as exc:
        raise RuntimeError("The Ruff Python distribution is required to build a release") from exc

    candidates = [
        path
        for path in (distribution.files or [])
        if path.name.upper() in {"LICENSE", "LICENSE.TXT", "LICENSE-MIT"}
    ]
    if not candidates:
        raise RuntimeError("Could not locate Ruff's license in the installed distribution")
    source = Path(str(distribution.locate_file(candidates[0])))
    shutil.copy2(source, destination / "RUFF_LICENSE")


def copy_python_distribution(distribution_name: str, destination: Path) -> None:
    """Copy an installed pure-Python distribution into the release's import path."""

    try:
        distribution = metadata.distribution(distribution_name)
    except metadata.PackageNotFoundError as exc:
        raise RuntimeError(
            f"{distribution_name} must be installed in the active Python environment"
        ) from exc

    for relative_path in distribution.files or ():
        relative = Path(str(relative_path))
        if relative.is_absolute() or ".." in relative.parts:
            continue
        source = Path(str(distribution.locate_file(relative_path)))
        if not source.is_file() or source.suffix in {".pyc", ".pyo"}:
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def copy_distribution_license(distribution_name: str, destination: Path) -> None:
    """Copy a bundled distribution's license beside the packaged README."""

    try:
        distribution = metadata.distribution(distribution_name)
    except metadata.PackageNotFoundError as exc:
        raise RuntimeError(
            f"{distribution_name} must be installed in the active Python environment"
        ) from exc

    candidates = [
        path
        for path in (distribution.files or ())
        if path.name.upper().startswith(("LICENSE", "COPYING"))
    ]
    distribution_licenses = [
        path for path in candidates if any(part.endswith(".dist-info") for part in path.parts)
    ]
    if distribution_licenses:
        candidates = distribution_licenses
    if not candidates:
        source = BUNDLED_LICENSE_FALLBACKS.get(distribution_name)
        if source is None or not source.is_file():
            raise RuntimeError(f"Could not locate {distribution_name}'s license")
    else:
        source = Path(str(distribution.locate_file(candidates[0])))
    license_name = distribution_name.upper().replace("-", "_") + "_LICENSE"
    shutil.copy2(source, destination / license_name)


def build(version: str, platform: str, output: Path) -> Path:
    version = version.removeprefix("v")
    output.mkdir(parents=True, exist_ok=True)
    archive_base = output / f"mad-coder-{version}-{platform}"

    with tempfile.TemporaryDirectory(prefix="mad-coder-") as temporary:
        staging = Path(temporary)
        shutil.copytree(ROOT / "packages", staging / "packages")
        content = staging / "mad-coder"
        shutil.copytree(
            ROOT / "mad-coder",
            content,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
        )
        shutil.copy2(ROOT / "LICENSE", content / "LICENSE")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        packaged_readme = readme.replace(
            'src="mad-coder/config/Icons/MAD_mad_coder.svg"',
            'src="config/Icons/MAD_mad_coder.svg"',
        )
        (content / "README.md").write_text(packaged_readme, encoding="utf-8")
        shutil.copy2(ROOT / "THIRD_PARTY_NOTICES.md", content / "THIRD_PARTY_NOTICES.md")

        python_directory = content / "scripts" / "python"
        for distribution_name in BUNDLED_PYTHON_DISTRIBUTIONS:
            copy_python_distribution(distribution_name, python_directory)
            copy_distribution_license(distribution_name, content)

        binary_directory = content / "bin"
        binary_directory.mkdir()
        binary_name = "ruff.exe" if platform.startswith("windows") else "ruff"
        bundled_ruff = binary_directory / binary_name
        shutil.copy2(locate_ruff(), bundled_ruff)
        bundled_ruff.chmod(bundled_ruff.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        copy_ruff_license(content)

        ty_name = "ty.exe" if platform.startswith("windows") else "ty"
        bundled_ty = binary_directory / ty_name
        shutil.copy2(locate_ty(), bundled_ty)
        bundled_ty.chmod(bundled_ty.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        copy_distribution_license("ty", content)

        archive = Path(shutil.make_archive(str(archive_base), "zip", staging))
    print(archive)
    return archive


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="0.0.0-dev")
    parser.add_argument("--platform", required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    arguments = parser.parse_args()
    build(arguments.version, arguments.platform, arguments.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
