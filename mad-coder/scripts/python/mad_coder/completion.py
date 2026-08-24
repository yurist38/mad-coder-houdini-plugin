"""Pure-Python completion analysis backed by Jedi."""

from __future__ import annotations

import keyword
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


class CompletionUnavailableError(RuntimeError):
    """Raised when the optional completion engine is not installed."""


@dataclass(frozen=True, slots=True)
class CompletionItem:
    """A completion candidate suitable for presentation by the editor UI."""

    name: str
    kind: str
    description: str


def _configure_jedi(jedi_module: object) -> None:
    """Keep Jedi's parser cache in an explicitly writable location."""

    configured = os.environ.get("MAD_CODER_JEDI_CACHE")
    cache_directory = (
        Path(configured) if configured else Path(tempfile.gettempdir()) / "mad-coder-jedi"
    )
    cache_directory.mkdir(parents=True, exist_ok=True)
    jedi_module.settings.cache_directory = str(cache_directory)  # type: ignore[attr-defined]


def analysis_source(text: str, builtins: tuple[str, ...]) -> tuple[str, int]:
    """Add source-context globals without changing the stored editor text."""

    prelude: list[str] = []
    for name in dict.fromkeys(builtins):
        if not name.isidentifier() or keyword.iskeyword(name):
            raise ValueError(f"Invalid completion builtin: {name!r}")
        if name == "hou":
            prelude.append("import hou as hou")
        elif name == "kwargs":
            prelude.extend(
                [
                    "from typing import Any as _MadCoderAny",
                    "kwargs: dict[str, _MadCoderAny] = {}",
                ]
            )
        else:
            prelude.append(f"{name}: object")

    if not prelude:
        return text, 0
    return "\n".join([*prelude, text]), len(prelude)


def completion_prefix(block_text: str, column: int) -> str:
    """Return the Python identifier fragment immediately before ``column``."""

    column = max(0, min(column, len(block_text)))
    start = column
    while start and (block_text[start - 1].isalnum() or block_text[start - 1] == "_"):
        start -= 1
    return block_text[start:column]


def complete_python(
    text: str,
    line: int,
    column: int,
    filename: str,
    builtins: tuple[str, ...] = (),
) -> list[CompletionItem]:
    """Return Jedi completion candidates for a zero-based cursor column."""

    try:
        import jedi
    except ImportError as exc:
        raise CompletionUnavailableError(
            "Jedi is unavailable. Install a Mad Coder release that includes autocomplete."
        ) from exc

    _configure_jedi(jedi)

    lines = text.split("\n")
    if line < 1 or line > len(lines):
        raise ValueError(f"Completion line is outside the buffer: {line}")
    if column < 0 or column > len(lines[line - 1]):
        raise ValueError(f"Completion column is outside line {line}: {column}")

    source, line_offset = analysis_source(text, builtins)
    path = Path(filename)
    if not path.is_absolute():
        path = Path.cwd() / path

    completions = jedi.Script(code=source, path=path).complete(line + line_offset, column)
    results: list[CompletionItem] = []
    seen: set[tuple[str, str]] = set()
    for candidate in completions:
        key = (candidate.name, candidate.type)
        if key in seen:
            continue
        seen.add(key)
        results.append(
            CompletionItem(
                name=candidate.name,
                kind=candidate.type,
                description=candidate.description,
            )
        )
    return results
