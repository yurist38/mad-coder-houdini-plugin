"""Calculate the next Mad Coder semantic-version tag."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Iterable

VERSION_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


def next_version(tags: Iterable[str], release_type: str) -> str:
    """Return the next strict ``vMAJOR.MINOR.PATCH`` tag.

    ``fix`` is the user-facing name for a semantic-version patch release.
    Non-semantic and prerelease tags are intentionally ignored.
    """

    versions = []
    for tag in tags:
        match = VERSION_TAG.fullmatch(tag.strip())
        if match:
            versions.append(tuple(int(part) for part in match.groups()))

    major, minor, patch = max(versions, default=(0, 0, 0))
    if release_type == "fix":
        patch += 1
    elif release_type == "minor":
        minor += 1
        patch = 0
    elif release_type == "major":
        major += 1
        minor = 0
        patch = 0
    else:
        raise ValueError(f"Unknown release type: {release_type}")

    return f"v{major}.{minor}.{patch}"


def git_tags() -> list[str]:
    result = subprocess.run(
        ["git", "tag", "--list"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.splitlines()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-type", choices=("fix", "minor", "major"), required=True)
    arguments = parser.parse_args()
    print(next_version(git_tags(), arguments.release_type))
    return 0


if __name__ == "__main__":
    sys.exit(main())
