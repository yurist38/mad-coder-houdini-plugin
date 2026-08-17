"""Output console widget for Mad Coder executions."""

from __future__ import annotations

from datetime import datetime

from PySide6 import QtCore, QtGui, QtWidgets

from .execution import ExecutionResult


class ExecutionConsole(QtWidgets.QWidget):
    """Display captured output from code executed inside Houdini."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.output = QtWidgets.QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        self.output.document().setMaximumBlockCount(10_000)

        clear_button = QtWidgets.QPushButton("Clear")
        copy_button = QtWidgets.QPushButton("Copy All")
        clear_button.clicked.connect(self.output.clear)
        copy_button.clicked.connect(self._copy_all)

        toolbar = QtWidgets.QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.addStretch(1)
        toolbar.addWidget(copy_button)
        toolbar.addWidget(clear_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        layout.addLayout(toolbar)
        layout.addWidget(self.output, 1)

    def begin(self, source_name: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._append(f"▶ [{timestamp}] Running {source_name}\n", "#4fc1ff")

    def finish(self, result: ExecutionResult) -> None:
        if result.output:
            self._append(result.output)
            if not result.output.endswith("\n"):
                self._append("\n")
        duration = f"{result.duration_seconds:.2f} seconds"
        if result.succeeded:
            self._append(f"✓ Completed in {duration}\n\n", "#6a9955")
        else:
            self._append(f"✗ Failed after {duration}\n\n", "#f44747")

    def _append(self, text: str, color: str | None = None) -> None:
        cursor = self.output.textCursor()
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
        text_format = QtGui.QTextCharFormat()
        if color:
            text_format.setForeground(QtGui.QColor(color))
        cursor.insertText(text, text_format)
        self.output.setTextCursor(cursor)
        self.output.ensureCursorVisible()

    def _copy_all(self) -> None:
        clipboard = QtWidgets.QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self.output.toPlainText())

    def focus_output(self) -> None:
        self.output.setFocus(QtCore.Qt.FocusReason.ShortcutFocusReason)
