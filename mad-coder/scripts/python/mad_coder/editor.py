"""Qt code editing widget with line numbers and inline diagnostics."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from .diagnostics import Diagnostic
from .highlighter import PythonHighlighter


class LineNumberArea(QtWidgets.QWidget):
    def __init__(self, editor: "MadCoderEditor") -> None:
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802 - Qt API
        return QtCore.QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802 - Qt API
        self.editor.paint_line_numbers(event)


class MadCoderEditor(QtWidgets.QPlainTextEdit):
    """Python-oriented text editor that remains native to Houdini's Qt UI."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._line_area = LineNumberArea(self)
        self._diagnostics: list[Diagnostic] = []
        self._highlighter = PythonHighlighter(self.document())

        font = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.SystemFont.FixedFont)
        font.setPointSize(11)
        self.setFont(font)
        self.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)
        self.setMouseTracking(True)

        self.blockCountChanged.connect(self._update_line_number_width)
        self.updateRequest.connect(self._update_line_number_area)
        self.cursorPositionChanged.connect(self._refresh_extra_selections)
        self._update_line_number_width()

    def line_number_area_width(self) -> int:
        digits = max(2, len(str(max(1, self.blockCount()))))
        return 10 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_line_number_width(self, _count: int = 0) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_line_number_area(self, rect: QtCore.QRect, dy: int) -> None:
        if dy:
            self._line_area.scroll(0, dy)
        else:
            self._line_area.update(0, rect.y(), self._line_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_line_number_width()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        contents = self.contentsRect()
        self._line_area.setGeometry(
            QtCore.QRect(
                contents.left(),
                contents.top(),
                self.line_number_area_width(),
                contents.height(),
            )
        )

    def paint_line_numbers(self, event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self._line_area)
        painter.fillRect(event.rect(), self.palette().alternateBase())
        painter.setPen(self.palette().color(QtGui.QPalette.ColorRole.PlaceholderText))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.drawText(
                    0,
                    top,
                    self._line_area.width() - 5,
                    self.fontMetrics().height(),
                    QtCore.Qt.AlignmentFlag.AlignRight,
                    str(block_number + 1),
                )
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1

    def set_diagnostics(self, diagnostics: list[Diagnostic]) -> None:
        self._diagnostics = diagnostics
        self._refresh_extra_selections()

    def _refresh_extra_selections(self) -> None:
        selections: list[QtWidgets.QTextEdit.ExtraSelection] = []

        if not self.isReadOnly():
            current_line = QtWidgets.QTextEdit.ExtraSelection()
            current_line.format.setBackground(self.palette().alternateBase())
            current_line.format.setProperty(QtGui.QTextFormat.Property.FullWidthSelection, True)
            current_line.cursor = self.textCursor()
            current_line.cursor.clearSelection()
            selections.append(current_line)

        document_length = max(0, self.document().characterCount() - 1)
        for diagnostic in self._diagnostics:
            start_block = self.document().findBlockByNumber(diagnostic.line - 1)
            end_block = self.document().findBlockByNumber(diagnostic.end_line - 1)
            if not start_block.isValid():
                continue
            if not end_block.isValid():
                end_block = start_block
            start = min(document_length, start_block.position() + diagnostic.column - 1)
            end = min(document_length, end_block.position() + diagnostic.end_column - 1)
            if end <= start:
                end = min(document_length, start + 1)

            selection = QtWidgets.QTextEdit.ExtraSelection()
            selection.cursor = QtGui.QTextCursor(self.document())
            selection.cursor.setPosition(start)
            selection.cursor.setPosition(end, QtGui.QTextCursor.MoveMode.KeepAnchor)
            color = "#f44747" if diagnostic.severity == "error" else "#cca700"
            selection.format.setUnderlineColor(QtGui.QColor(color))
            selection.format.setUnderlineStyle(QtGui.QTextCharFormat.UnderlineStyle.WaveUnderline)
            selections.append(selection)

        self.setExtraSelections(selections)

    def go_to(self, line: int, column: int = 1) -> None:
        block = self.document().findBlockByNumber(max(0, line - 1))
        if not block.isValid():
            return
        cursor = QtGui.QTextCursor(block)
        cursor.movePosition(
            QtGui.QTextCursor.MoveOperation.Right,
            QtGui.QTextCursor.MoveMode.MoveAnchor,
            max(0, column - 1),
        )
        self.setTextCursor(cursor)
        self.centerCursor()
        self.setFocus()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802 - Qt API
        cursor = self.cursorForPosition(event.position().toPoint())
        line = cursor.blockNumber() + 1
        column = cursor.positionInBlock() + 1
        messages = [
            f"{item.code}: {item.message}" if item.code else item.message
            for item in self._diagnostics
            if item.line <= line <= item.end_line
            and (line != item.line or column >= item.column)
            and (line != item.end_line or column <= item.end_column)
        ]
        if messages:
            QtWidgets.QToolTip.showText(event.globalPosition().toPoint(), "\n".join(messages), self)
        else:
            QtWidgets.QToolTip.hideText()
        super().mouseMoveEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802 - Qt API
        if event.key() == QtCore.Qt.Key.Key_Tab and not event.modifiers():
            self.insertPlainText(" " * 4)
            return
        if event.key() in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
            cursor = self.textCursor()
            current = cursor.block().text()
            indentation = current[: len(current) - len(current.lstrip())]
            if current.rstrip().endswith(":"):
                indentation += " " * 4
            super().keyPressEvent(event)
            self.insertPlainText(indentation)
            return
        super().keyPressEvent(event)

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:  # noqa: N802 - Qt API
        if event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier:
            font = self.font()
            change = 1 if event.angleDelta().y() > 0 else -1
            font.setPointSize(max(7, min(32, font.pointSize() + change)))
            self.setFont(font)
            self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)
            self._update_line_number_width()
            event.accept()
            return
        super().wheelEvent(event)
