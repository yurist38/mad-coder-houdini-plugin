"""Editor diagnostics and external-tool output parsing."""

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


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


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
        location = _as_dict(item.get("location"))
        end_location = _as_dict(item.get("end_location")) or location
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


def parse_ty_output(payload: str, line_offset: int = 0) -> list[Diagnostic]:
    """Convert ty's GitLab JSON output and restore editor line numbers."""

    try:
        items = json.loads(payload or "[]")
    except json.JSONDecodeError as exc:
        raise ValueError(f"ty returned invalid JSON: {exc}") from exc

    if not isinstance(items, list):
        raise ValueError("ty JSON output must be a list")

    offset = max(0, line_offset)
    result: list[Diagnostic] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        positions = _as_dict(_as_dict(item.get("location")).get("positions"))
        begin = _as_dict(positions.get("begin"))
        end = _as_dict(positions.get("end")) or begin
        generated_line = _positive_int(begin.get("line"), 1)
        line = generated_line - offset
        if line < 1:
            # Diagnostics in Mad Coder's synthetic Houdini-context prelude are not
            # actionable in the user's buffer.
            continue
        end_line = max(line, _positive_int(end.get("line"), generated_line) - offset)
        column = _positive_int(begin.get("column"), 1)
        end_column = _positive_int(end.get("column"), column + 1)
        code = str(item.get("check_name") or "unknown")
        message = str(item.get("description") or "Unknown ty diagnostic")
        prefix = f"{code}: "
        if message.startswith(prefix):
            message = message[len(prefix) :]
        severity = str(item.get("severity") or "").casefold()
        result.append(
            Diagnostic(
                line=line,
                column=column,
                end_line=end_line,
                end_column=end_column,
                message=message,
                code=f"ty:{code}",
                severity="error" if severity in {"blocker", "critical", "major"} else "warning",
            )
        )
    return result
