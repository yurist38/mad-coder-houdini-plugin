"""Pure-Python source preparation for static type checking."""

from __future__ import annotations

import ast

from .completion import analysis_source


def type_analysis_source(text: str, builtins: tuple[str, ...]) -> tuple[str, int]:
    """Add Houdini globals while keeping valid ``__future__`` imports first."""

    tree = ast.parse(text)
    source, prelude_lines = analysis_source("", builtins)
    prelude = source.rstrip("\n")
    if not prelude:
        return text, 0

    lines = text.splitlines(keepends=True)
    future_blocks: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or node.module != "__future__":
            continue
        start = node.lineno - 1
        end = node.end_lineno or node.lineno
        future_blocks.append("".join(lines[start:end]).rstrip("\r\n"))
        for index in range(start, end):
            line = lines[index]
            if line.endswith("\r\n"):
                lines[index] = "\r\n"
            elif line.endswith("\n") or line.endswith("\r"):
                lines[index] = line[-1]
            else:
                lines[index] = ""

    prefix_parts = [*future_blocks, prelude]
    prefix = "\n".join(prefix_parts) + "\n"
    line_offset = len(future_blocks) + prelude_lines
    # A multiline future import contributes more than one generated line.
    line_offset += sum(block.count("\n") for block in future_blocks)
    return prefix + "".join(lines), line_offset
