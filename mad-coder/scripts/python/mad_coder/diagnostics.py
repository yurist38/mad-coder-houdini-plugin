"""Linter diagnostics and Ruff output parsing."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """A source diagnostic using one-based line and column positions."""

    line: int
    column: int
    end_line: int
    end_column: int
    message: str
    code: str = ""
    severity: str = "warning"
    fixable: bool = False


def _positive_int(value: Any, default: int) -> int:
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default


def _severity(code: str) -> str:
    error_prefixes = ("E9", "F63", "F7", "F82")
    return "error" if code == "invalid-syntax" or code.startswith(error_prefixes) else "warning"


def parse_ruff_output(payload: str) -> list[Diagnostic]:
    """Convert Ruff's JSON output into stable application diagnostics."""

    try:
        items = json.loads(payload or "[]")
    except json.JSONDecodeError as exc:
        raise ValueError(f"Ruff returned invalid JSON: {exc}") from exc

    if not isinstance(items, list):
        raise ValueError("Ruff JSON output must be a list")

    result: list[Diagnostic] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        location = item.get("location") or {}
        end_location = item.get("end_location") or location
        line = _positive_int(location.get("row"), 1)
        column = _positive_int(location.get("column"), 1)
        end_line = _positive_int(end_location.get("row"), line)
        end_column = _positive_int(end_location.get("column"), column + 1)
        code = str(item.get("code") or "")
        result.append(
            Diagnostic(
                line=line,
                column=column,
                end_line=end_line,
                end_column=end_column,
                message=str(item.get("message") or "Unknown Ruff diagnostic"),
                code=code,
                severity=_severity(code),
                fixable=item.get("fix") is not None,
            )
        )
    return result
