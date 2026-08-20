"""A lightweight Python syntax highlighter for the editor."""

from __future__ import annotations

import keyword

from PySide6 import QtCore, QtGui  # type: ignore[import-not-found]


class PythonHighlighter(QtGui.QSyntaxHighlighter):
    """Highlight common Python tokens without third-party dependencies."""

    def __init__(self, document: QtGui.QTextDocument) -> None:
        super().__init__(document)
        self._rules: list[tuple[QtCore.QRegularExpression, QtGui.QTextCharFormat]] = []

        keyword_format = self._format("#c586c0", bold=True)
        builtin_format = self._format("#4ec9b0")
        number_format = self._format("#b5cea8")
        string_format = self._format("#ce9178")
        comment_format = self._format("#6a9955", italic=True)
        decorator_format = self._format("#dcdcaa")

        words = "|".join(keyword.kwlist)
        self._rules.append((QtCore.QRegularExpression(rf"\b(?:{words})\b"), keyword_format))
        self._rules.append(
            (
                QtCore.QRegularExpression(
                    r"\b(?:abs|all|any|bool|bytes|dict|enumerate|filter|float|"
                    r"getattr|hasattr|int|isinstance|len|list|map|max|min|next|"
                    r"object|open|print|property|range|repr|reversed|round|set|"
                    r"setattr|sorted|str|sum|super|tuple|type|zip)\b"
                ),
                builtin_format,
            )
        )
        self._rules.append(
            (
                QtCore.QRegularExpression(
                    r"\b(?:0[xX][0-9A-Fa-f]+|0[bB][01]+|\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\b"
                ),
                number_format,
            )
        )
        self._rules.append((QtCore.QRegularExpression(r"\"(?:\\.|[^\"\\])*\""), string_format))
        self._rules.append((QtCore.QRegularExpression(r"'(?:\\.|[^'\\])*'"), string_format))
        self._rules.append((QtCore.QRegularExpression(r"#[^\n]*"), comment_format))
        self._rules.append(
            (QtCore.QRegularExpression(r"@[A-Za-z_][A-Za-z0-9_.]*"), decorator_format)
        )

        self._triple_single = QtCore.QRegularExpression("'''")
        self._triple_double = QtCore.QRegularExpression('"""')
        self._multiline_format = string_format

    @staticmethod
    def _format(color: str, *, bold: bool = False, italic: bool = False) -> QtGui.QTextCharFormat:
        value = QtGui.QTextCharFormat()
        value.setForeground(QtGui.QColor(color))
        if bold:
            value.setFontWeight(QtGui.QFont.Weight.Bold)
        value.setFontItalic(italic)
        return value

    def highlightBlock(self, text: str) -> None:  # noqa: N802 - Qt API
        for expression, text_format in self._rules:
            iterator = expression.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), text_format)

        self.setCurrentBlockState(0)
        if self.previousBlockState() == 1:
            self._highlight_multiline(text, self._triple_single, 1, 0)
        elif self.previousBlockState() == 2:
            self._highlight_multiline(text, self._triple_double, 2, 0)
        else:
            single = self._triple_single.match(text)
            double = self._triple_double.match(text)
            starts = [
                (single.capturedStart(), self._triple_single, 1),
                (double.capturedStart(), self._triple_double, 2),
            ]
            starts = [item for item in starts if item[0] >= 0]
            if starts:
                start, expression, state = min(starts, key=lambda item: item[0])
                self._highlight_multiline(text, expression, state, start)

    def _highlight_multiline(
        self,
        text: str,
        delimiter: QtCore.QRegularExpression,
        state: int,
        start: int,
    ) -> None:
        search_from = start + (0 if self.previousBlockState() == state else 3)
        end_match = delimiter.match(text, search_from)
        if end_match.hasMatch():
            length = end_match.capturedEnd() - start
        else:
            self.setCurrentBlockState(state)
            length = len(text) - start
        self.setFormat(start, max(0, length), self._multiline_format)
