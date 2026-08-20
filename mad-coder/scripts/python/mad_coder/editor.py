"""Qt code editing widget with line numbers and inline diagnostics."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets  # type: ignore[import-not-found]

from .completion import CompletionItem, completion_prefix
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

    completion_requested = QtCore.Signal(bool)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._line_area = LineNumberArea(self)
        self._diagnostics: list[Diagnostic] = []
        self._highlighter = PythonHighlighter(self.document())
        self._completion_request_block = -1
        self._completion_request_position = -1
        self._completion_was_explicit = False
        self._autocomplete_enabled = True
        self._completion_items: list[CompletionItem] = []

        self._completion_model = QtGui.QStandardItemModel(self)
        completion_popup = QtWidgets.QTreeView(self.viewport())
        self._completion_popup = completion_popup
        completion_popup.setModel(self._completion_model)
        completion_popup.setRootIsDecorated(False)
        completion_popup.setAlternatingRowColors(True)
        completion_popup.setUniformRowHeights(True)
        completion_popup.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        completion_popup.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        completion_popup.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        completion_popup.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        completion_popup.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        completion_popup.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating)
        completion_popup.header().hide()
        completion_popup.clicked.connect(self._insert_completion)
        completion_popup.hide()

        font = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.SystemFont.FixedFont)
        self.set_code_font(font.family(), 11)
        self.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)

        self.blockCountChanged.connect(self._update_line_number_width)
        self.updateRequest.connect(self._update_line_number_area)
        self.cursorPositionChanged.connect(self._refresh_extra_selections)
        self._update_line_number_width()

    def set_code_font(self, family: str, point_size: int) -> None:
        """Apply the configured monospaced editor font."""

        font = QtGui.QFont(family, point_size)
        font.setStyleHint(QtGui.QFont.StyleHint.Monospace)
        self.setFont(font)
        self._update_line_number_width()
        self._line_area.update()

    @property
    def autocomplete_enabled(self) -> bool:
        return self._autocomplete_enabled

    def set_autocomplete_enabled(self, enabled: bool) -> None:
        """Enable or disable all automatic and explicit completion requests."""

        self._autocomplete_enabled = enabled
        if not enabled:
            self.hide_completions()

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
        self.hide_completions()
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
            if not block.isValid():
                break
            block_number += 1
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())

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

        diagnostic_lines: dict[int, str] = {}
        block_count = self.blockCount()
        for diagnostic in self._diagnostics:
            first_line = max(1, diagnostic.line)
            last_line = min(block_count, max(first_line, diagnostic.end_line))
            for line in range(first_line, last_line + 1):
                current_severity = diagnostic_lines.get(line)
                if current_severity != "error":
                    diagnostic_lines[line] = diagnostic.severity

        for line, severity in sorted(diagnostic_lines.items()):
            block = self.document().findBlockByNumber(line - 1)
            if not block.isValid():
                continue
            line_selection = QtWidgets.QTextEdit.ExtraSelection()
            line_selection.cursor = QtGui.QTextCursor(block)
            line_selection.cursor.clearSelection()
            color = QtGui.QColor("#f44747" if severity == "error" else "#cca700")
            color.setAlpha(36 if severity == "error" else 28)
            line_selection.format.setBackground(color)
            line_selection.format.setProperty(QtGui.QTextFormat.Property.FullWidthSelection, True)
            selections.append(line_selection)

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
        self.hide_completions()
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

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802 - Qt API
        self.hide_completions()
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.setFocus(QtCore.Qt.FocusReason.MouseFocusReason)
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802 - Qt API
        popup_visible = self._completion_popup.isVisible()
        if popup_visible:
            if event.key() == QtCore.Qt.Key.Key_Escape:
                self.hide_completions()
                event.accept()
                return
            if event.key() in (
                QtCore.Qt.Key.Key_Enter,
                QtCore.Qt.Key.Key_Return,
                QtCore.Qt.Key.Key_Tab,
            ):
                self._insert_current_completion()
                event.accept()
                return
            if event.key() in (QtCore.Qt.Key.Key_Up, QtCore.Qt.Key.Key_Backtab):
                self._move_completion_selection(-1)
                event.accept()
                return
            if event.key() == QtCore.Qt.Key.Key_Down:
                self._move_completion_selection(1)
                event.accept()
                return
            if event.key() == QtCore.Qt.Key.Key_PageUp:
                self._move_completion_selection(-10)
                event.accept()
                return
            if event.key() == QtCore.Qt.Key.Key_PageDown:
                self._move_completion_selection(10)
                event.accept()
                return

        completion_modifiers = (
            QtCore.Qt.KeyboardModifier.ControlModifier,
            QtCore.Qt.KeyboardModifier.MetaModifier,
        )
        explicit_completion = (
            event.key() == QtCore.Qt.Key.Key_Space and event.modifiers() in completion_modifiers
        )
        if explicit_completion:
            self._request_completions(explicit=True)
            event.accept()
            return

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

        typed_dot = event.text() == "." and not event.modifiers()
        super().keyPressEvent(event)

        if typed_dot and not self.isReadOnly():
            self.hide_completions()
            self._request_completions(explicit=False)
            return
        if popup_visible:
            self._refresh_completion_prefix()

    def _request_completions(self, *, explicit: bool) -> None:
        if self.isReadOnly() or not self._autocomplete_enabled:
            return
        cursor = self.textCursor()
        self._completion_request_block = cursor.blockNumber()
        self._completion_request_position = cursor.position()
        self._completion_was_explicit = explicit
        self.completion_requested.emit(explicit)

    def show_completions(self, items: list[CompletionItem]) -> None:
        """Display completion candidates at the current text cursor."""

        cursor = self.textCursor()
        if (
            not self._autocomplete_enabled
            or self.isReadOnly()
            or not items
            or cursor.blockNumber() != self._completion_request_block
            or cursor.position() < self._completion_request_position
        ):
            self.hide_completions()
            return

        prefix = completion_prefix(cursor.block().text(), cursor.positionInBlock())
        self._completion_items = items
        if not self._populate_completion_model(prefix):
            self.hide_completions()
            return

        self._show_completion_popup()

    def _populate_completion_model(self, prefix: str) -> bool:
        matching_items = [
            item
            for item in self._completion_items
            if item.name.casefold().startswith(prefix.casefold())
        ]

        self._completion_model.clear()
        for item in matching_items:
            name = QtGui.QStandardItem(item.name)
            name.setToolTip(item.description)
            kind = QtGui.QStandardItem(item.kind)
            kind.setForeground(self.palette().color(QtGui.QPalette.ColorRole.PlaceholderText))
            description = QtGui.QStandardItem(item.description)
            description.setForeground(
                self.palette().color(QtGui.QPalette.ColorRole.PlaceholderText)
            )
            self._completion_model.appendRow([name, kind, description])
        return bool(matching_items)

    def _show_completion_popup(self) -> None:
        popup = self._completion_popup
        popup.resizeColumnToContents(0)
        popup.resizeColumnToContents(1)
        popup.resizeColumnToContents(2)
        popup.setCurrentIndex(self._completion_model.index(0, 0))

        natural_width = sum(popup.sizeHintForColumn(column) for column in range(3)) + 32
        available_width = max(1, self.viewport().width())
        width = min(max(320, natural_width), available_width)
        row_height = max(popup.sizeHintForRow(0), self.fontMetrics().height() + 6)
        height = min(10, self._completion_model.rowCount()) * row_height + popup.frameWidth() * 2
        cursor_rectangle = self.cursorRect()
        x = max(0, min(cursor_rectangle.left(), available_width - width))
        below = cursor_rectangle.bottom() + 1
        y = (
            below
            if below + height <= self.viewport().height()
            else max(0, cursor_rectangle.top() - height)
        )
        popup.setGeometry(x, y, width, height)
        popup.show()
        popup.raise_()

    def hide_completions(self) -> None:
        self._completion_popup.hide()
        self._completion_items = []
        self._completion_model.clear()
        self._completion_request_block = -1
        self._completion_request_position = -1

    def _refresh_completion_prefix(self) -> None:
        cursor = self.textCursor()
        block_text = cursor.block().text()
        column = cursor.positionInBlock()
        prefix = completion_prefix(block_text, column)
        follows_dot = column > len(prefix) and block_text[column - len(prefix) - 1] == "."
        if not prefix and not follows_dot and not self._completion_was_explicit:
            self.hide_completions()
            return
        if not self._populate_completion_model(prefix):
            self.hide_completions()
            return
        self._show_completion_popup()

    def _move_completion_selection(self, offset: int) -> None:
        row_count = self._completion_model.rowCount()
        if not row_count:
            return
        current_row = self._completion_popup.currentIndex().row()
        next_row = max(0, min(row_count - 1, current_row + offset))
        index = self._completion_model.index(next_row, 0)
        self._completion_popup.setCurrentIndex(index)
        self._completion_popup.scrollTo(index)

    def _insert_current_completion(self) -> None:
        index = self._completion_popup.currentIndex()
        if index.isValid():
            self._insert_completion(index)

    def _insert_completion(self, index: QtCore.QModelIndex) -> None:
        completion = str(index.sibling(index.row(), 0).data())
        cursor = self.textCursor()
        prefix = completion_prefix(cursor.block().text(), cursor.positionInBlock())
        cursor.movePosition(
            QtGui.QTextCursor.MoveOperation.Left,
            QtGui.QTextCursor.MoveMode.KeepAnchor,
            len(prefix),
        )
        cursor.insertText(completion)
        self.setTextCursor(cursor)
        self.hide_completions()
        self.setFocus(QtCore.Qt.FocusReason.OtherFocusReason)

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:  # noqa: N802 - Qt API
        if event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier:
            font = self.font()
            change = 1 if event.angleDelta().y() > 0 else -1
            font.setPointSize(max(7, min(32, font.pointSize() + change)))
            self.setFont(font)
            self._update_line_number_width()
            event.accept()
            return
        self.hide_completions()
        super().wheelEvent(event)
