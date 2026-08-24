"""Build deterministic Ruff command-line arguments."""

from __future__ import annotations

import json


def check_arguments(
    filename: str,
    builtins: tuple[str, ...] = (),
    ignored_codes: tuple[str, ...] = (),
) -> list[str]:
    """Return isolated Ruff check arguments for a Houdini source context."""

    unique_builtins = tuple(dict.fromkeys(builtins))
    invalid = [name for name in unique_builtins if not name.isidentifier()]
    if invalid:
        raise ValueError(f"Invalid Python built-in name: {invalid[0]}")

    arguments = [
        "check",
        "--isolated",
        "--output-format",
        "json",
        "--select",
        "E4,E7,E9,F",
        "--target-version",
        "py311",
    ]
    if unique_builtins:
        value = json.dumps(list(unique_builtins), ensure_ascii=True)
        arguments.extend(["--config", f"builtins = {value}"])
    unique_ignored_codes = tuple(dict.fromkeys(ignored_codes))
    if unique_ignored_codes:
        arguments.extend(["--ignore", ",".join(unique_ignored_codes)])
    arguments.extend(["--stdin-filename", filename, "-"])
    return arguments
