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


def locate_ruff() -> Path:
    executable = shutil.which("ruff")
    if not executable:
        raise RuntimeError("Ruff is required to build a release archive")
    return Path(executable)


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
    source = Path(distribution.locate_file(candidates[0]))
    shutil.copy2(source, destination / "RUFF_LICENSE")


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
        shutil.copy2(ROOT / "README.md", content / "README.md")
        shutil.copy2(ROOT / "THIRD_PARTY_NOTICES.md", content / "THIRD_PARTY_NOTICES.md")

        binary_directory = content / "bin"
        binary_directory.mkdir()
        binary_name = "ruff.exe" if platform.startswith("windows") else "ruff"
        bundled_ruff = binary_directory / binary_name
        shutil.copy2(locate_ruff(), bundled_ruff)
        bundled_ruff.chmod(bundled_ruff.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        copy_ruff_license(content)

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
