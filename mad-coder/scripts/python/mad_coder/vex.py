"""VEX snippet preparation and vcc diagnostic parsing."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from difflib import SequenceMatcher

from .diagnostics import Diagnostic

VEX_SNIPPET_LINE_OFFSET = 3

_PROTECTED = re.compile(
    r'(/\*.*?\*/|//[^\n]*(?:\n|$)|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')',
    re.DOTALL,
)
_PROTOTYPE = re.compile(
    r"^(\s*)([A-Za-z_][A-Za-z0-9_]*)\s+@([A-Za-z_][A-Za-z0-9_]*)"
    r"(\s*\[\s*\])?(?=\s*;\s*(?://.*)?$)"
)
_ATTRIBUTE = re.compile(
    r"(?<![A-Za-z0-9_])(?:(?P<prefix>[fuvp234isd])(?P<array>\[\])?)?"
    r"@(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
)
_VCC_DIAGNOSTIC = re.compile(
    r"^(?P<path>.+?):(?:(?P<line>\d+):(?P<column>\d+)"
    r"(?:-(?P<end_column>\d+))?:)?\s*"
    r"(?P<severity>Error|Warning|Info)\s*(?P<number>\d+)?:\s*(?P<message>.*)$"
)

_PREFIX_TYPES = {
    "f": "float",
    "u": "vector2",
    "v": "vector",
    "p": "vector4",
    "2": "matrix2",
    "3": "matrix3",
    "4": "matrix",
    "i": "int",
    "s": "string",
    "d": "dict",
}
_KNOWN_VECTOR = {
    "P",
    "accel",
    "Cd",
    "N",
    "scale",
    "force",
    "rest",
    "torque",
    "up",
    "uv",
    "v",
    "center",
    "dPdx",
    "dPdy",
    "dPdz",
}
_KNOWN_VECTOR4 = {"backtrack", "orient", "rot"}
_KNOWN_INT = {
    "id",
    "nextid",
    "pstate",
    "elemnum",
    "ptnum",
    "primnum",
    "vtxnum",
    "numelem",
    "numpt",
    "numprim",
    "numvtx",
    "ix",
    "iy",
    "iz",
    "resx",
    "resy",
    "resz",
}
_KNOWN_STRING = {"name", "instance"}


@dataclass(frozen=True, slots=True)
class VexAnalysisSource:
    """Generated source plus information needed to restore snippet positions."""

    source: str
    original: str
    line_offset: int = VEX_SNIPPET_LINE_OFFSET


def _implicit_prefix(name: str) -> str:
    name_without_input = re.sub(r"^opinput\d+_", "", name, flags=re.IGNORECASE)
    if name_without_input in _KNOWN_VECTOR:
        return "v"
    if name_without_input in _KNOWN_VECTOR4:
        return "p"
    if name_without_input in _KNOWN_INT or name.startswith("group_"):
        return "i"
    if name_without_input in _KNOWN_STRING or name.startswith("OpInput"):
        return "s"
    return "f"


def vex_snippet_source(source: str) -> VexAnalysisSource:
    """Wrap a Wrangle-style snippet in a vcc-compatible analysis function."""

    arguments: list[str] = []
    bound: set[str] = set()
    pieces = _PROTECTED.split(source)

    for piece_index, piece in enumerate(pieces):
        if not piece or _PROTECTED.fullmatch(piece):
            continue

        lines = piece.split("\n")
        for line_index, line in enumerate(lines):
            prototype = _PROTOTYPE.match(line)
            if prototype is None:
                continue
            vex_type = prototype.group(2)
            name = prototype.group(3)
            array_suffix = "[]" if prototype.group(4) else ""
            if name not in bound:
                arguments.append(f"{vex_type} _bound_{name}{array_suffix}")
                bound.add(name)
            lines[line_index] = f"{prototype.group(1)}// Attribute prototype for {name}"
        piece = "\n".join(lines)

        def replace_attribute(match: re.Match[str]) -> str:
            prefix = match.group("prefix") or _implicit_prefix(match.group("name"))
            name = match.group("name")
            if name not in bound:
                array_suffix = "[]" if match.group("array") else ""
                arguments.append(f"{_PREFIX_TYPES[prefix]} _bound_{name}{array_suffix}")
                bound.add(name)
            return f"_bound_{name}"

        pieces[piece_index] = _ATTRIBUTE.sub(replace_attribute, piece)

    arguments_text = "; ".join(arguments)
    body = "".join(pieces)
    generated = f"#include <math.h>\nvoid mad_coder_vex_check({arguments_text})\n{{\n{body}\n}}\n"
    return VexAnalysisSource(generated, source)


def _mapped_column(column: int, generated_line: str, source_line: str) -> int:
    """Map a column past generated binding names back to the original line."""

    position = max(0, column - 1)
    if position >= len(generated_line):
        return len(source_line) + 1
    matcher = SequenceMatcher(None, source_line, generated_line, autojunk=False)
    for tag, source_start, source_end, generated_start, generated_end in matcher.get_opcodes():
        if not generated_start <= position < generated_end:
            continue
        if tag == "equal":
            return source_start + (position - generated_start) + 1
        source_length = source_end - source_start
        generated_length = max(1, generated_end - generated_start)
        relative = (position - generated_start) / generated_length
        return source_start + min(source_length, round(relative * source_length)) + 1
    return max(1, min(len(source_line) + 1, column))


def parse_vcc_output(
    payload: str,
    *,
    analysis: VexAnalysisSource | None = None,
) -> list[Diagnostic]:
    """Parse vcc stderr and map generated snippet positions to editor positions."""

    parsed: list[Diagnostic] = []
    generated_lines = analysis.source.splitlines() if analysis is not None else []
    original_lines = analysis.original.splitlines() if analysis is not None else []

    for raw_line in payload.splitlines():
        match = _VCC_DIAGNOSTIC.match(raw_line.strip())
        if match is None:
            if parsed and raw_line.strip():
                previous = parsed[-1]
                parsed[-1] = replace(previous, message=f"{previous.message}\n{raw_line.strip()}")
            continue

        generated_line = int(match.group("line") or 1)
        line = generated_line
        column = int(match.group("column") or 1)
        end_column = int(match.group("end_column") or column + 1)
        if analysis is not None and match.group("line"):
            line = generated_line - analysis.line_offset
            if 1 <= line <= len(original_lines) and generated_line <= len(generated_lines):
                generated_text = generated_lines[generated_line - 1]
                original_text = original_lines[line - 1]
                column = _mapped_column(column, generated_text, original_text)
                end_column = _mapped_column(end_column, generated_text, original_text)
            elif line < 1:
                line = 1
        severity = match.group("severity").casefold()
        number = match.group("number") or ""
        parsed.append(
            Diagnostic(
                line=max(1, line),
                column=max(1, column),
                end_line=max(1, line),
                end_column=max(column + 1, end_column),
                message=match.group("message") or "Unknown vcc diagnostic",
                code=f"VEX{number}" if number else "VEX",
                severity="error" if severity == "error" else "warning",
            )
        )
    return parsed
