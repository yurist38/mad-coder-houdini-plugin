"""The dockable Mad Coder panel."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from .diagnostics import Diagnostic
from .editor import MadCoderEditor
from .linting import RuffService
from .source import SessionSource, SourceConflictError


class MadCoderPanel(QtWidgets.QWidget):
    """Edit the current scene's ``hou.session`` source with live diagnostics."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._source = SessionSource()
        self._baseline = ""
        self._loading = False
        self._diagnostics: list[Diagnostic] = []

        self._source_label = QtWidgets.QLabel(self._source.display_name)
        self._source_label.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._save_button = QtWidgets.QPushButton("Save")
        self._reload_button = QtWidgets.QPushButton("Reload")
        self._format_button = QtWidgets.QPushButton("Format")
        self._lint_badge = QtWidgets.QLabel()

        toolbar = QtWidgets.QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.addWidget(self._source_label)
        toolbar.addStretch(1)
        toolbar.addWidget(self._lint_badge)
        toolbar.addWidget(self._reload_button)
        toolbar.addWidget(self._format_button)
        toolbar.addWidget(self._save_button)

        self.editor = MadCoderEditor()
        self.editor.setPlaceholderText("# Python stored in hou.session")

        self._problems = QtWidgets.QTreeWidget()
        self._problems.setHeaderLabels(["Problem", "Code", "Line"])
        self._problems.setRootIsDecorated(False)
        self._problems.setAlternatingRowColors(True)
        self._problems.header().setStretchLastSection(False)
        self._problems.header().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self._problems.header().setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        self._problems.header().setSectionResizeMode(
            2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        splitter.addWidget(self.editor)
        splitter.addWidget(self._problems)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([700, 180])

        self._status = QtWidgets.QLabel()
        self._status.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        layout.addLayout(toolbar)
        layout.addWidget(splitter, 1)
        layout.addWidget(self._status)

        self._lint_timer = QtCore.QTimer(self)
        self._lint_timer.setSingleShot(True)
        self._lint_timer.setInterval(400)
        self._ruff = RuffService(self)

        self.editor.textChanged.connect(self._text_changed)
        self._save_button.clicked.connect(self.save)
        self._reload_button.clicked.connect(self.reload)
        self._format_button.clicked.connect(self.format_code)
        self._problems.itemActivated.connect(self._problem_activated)
        self._problems.itemClicked.connect(self._problem_activated)
        self._lint_timer.timeout.connect(self._run_lint)
        self._ruff.lint_ready.connect(self._lint_ready)
        self._ruff.lint_failed.connect(self._lint_failed)
        self._ruff.format_ready.connect(self._format_ready)
        self._ruff.format_failed.connect(self._format_failed)

        self._shortcuts = [
            QtGui.QShortcut(QtGui.QKeySequence.StandardKey.Save, self),
            QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Shift+F"), self),
            QtGui.QShortcut(QtGui.QKeySequence("F5"), self),
        ]
        self._shortcuts[0].activated.connect(self.save)
        self._shortcuts[1].activated.connect(self.format_code)
        self._shortcuts[2].activated.connect(self.reload)

        self.reload(force=True)

    def _text_changed(self) -> None:
        if self._loading:
            return
        dirty = self.editor.toPlainText() != self._baseline
        self._save_button.setEnabled(dirty)
        self._source_label.setText(self._source.display_name + (" *" if dirty else ""))
        self._lint_badge.setText("Checking…")
        self._lint_timer.start()

    def reload(self, force: bool = False) -> None:
        if not force and self.editor.toPlainText() != self._baseline:
            answer = QtWidgets.QMessageBox.question(
                self,
                "Discard unsaved changes?",
                "Reloading hou.session will discard the changes in this editor.",
                QtWidgets.QMessageBox.StandardButton.Discard
                | QtWidgets.QMessageBox.StandardButton.Cancel,
                QtWidgets.QMessageBox.StandardButton.Cancel,
            )
            if answer != QtWidgets.QMessageBox.StandardButton.Discard:
                return

        try:
            source = self._source.load()
        except Exception as exc:  # Houdini reports API failures through several exception types.
            self._show_error("Could not read hou.session", str(exc))
            return

        self._loading = True
        self.editor.setPlainText(source)
        self._loading = False
        self._baseline = source
        self._save_button.setEnabled(False)
        self._source_label.setText(self._source.display_name)
        self._set_status("Loaded hou.session")
        self._run_lint()

    def save(self) -> None:
        text = self.editor.toPlainText()
        try:
            self._source.save(text, self._baseline)
        except SourceConflictError:
            self._resolve_conflict(text)
            return
        except Exception as exc:
            self._show_error(
                "Could not save hou.session",
                f"Houdini rejected the source. Fix syntax errors and try again.\n\n{exc}",
            )
            return
        self._mark_saved(text)

    def _resolve_conflict(self, text: str) -> None:
        box = QtWidgets.QMessageBox(self)
        box.setIcon(QtWidgets.QMessageBox.Icon.Warning)
        box.setWindowTitle("hou.session changed")
        box.setText("hou.session was changed outside this editor.")
        box.setInformativeText(
            "Reload the external version or overwrite it with this editor's text?"
        )
        reload_button = box.addButton("Reload", QtWidgets.QMessageBox.ButtonRole.DestructiveRole)
        overwrite_button = box.addButton("Overwrite", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        box.addButton(QtWidgets.QMessageBox.StandardButton.Cancel)
        box.exec()
        if box.clickedButton() is reload_button:
            self.reload(force=True)
        elif box.clickedButton() is overwrite_button:
            try:
                self._source.save(text, expected=None)
            except Exception as exc:
                self._show_error("Could not overwrite hou.session", str(exc))
            else:
                self._mark_saved(text)

    def _mark_saved(self, text: str) -> None:
        self._baseline = text
        self._save_button.setEnabled(False)
        self._source_label.setText(self._source.display_name)
        self._set_status("Saved to hou.session")

    def format_code(self) -> None:
        self._set_status("Formatting with Ruff…")
        self._ruff.format(self.editor.toPlainText(), self._source.lint_filename)

    def _format_ready(self, text: str) -> None:
        cursor = self.editor.textCursor()
        position = cursor.position()
        self.editor.setPlainText(text)
        cursor = self.editor.textCursor()
        cursor.setPosition(min(position, max(0, len(text))))
        self.editor.setTextCursor(cursor)
        self._set_status("Formatted with Ruff; save to apply")

    def _format_failed(self, message: str) -> None:
        self._set_status(f"Format failed: {message}", error=True)

    def _run_lint(self) -> None:
        self._ruff.lint(self.editor.toPlainText(), self._source.lint_filename)

    def _lint_ready(self, diagnostics: list[Diagnostic], engine: str) -> None:
        self._diagnostics = diagnostics
        self.editor.set_diagnostics(diagnostics)
        self._problems.clear()
        for diagnostic in diagnostics:
            item = QtWidgets.QTreeWidgetItem(
                [diagnostic.message, diagnostic.code, str(diagnostic.line)]
            )
            item.setData(0, QtCore.Qt.ItemDataRole.UserRole, diagnostic)
            color = "#f44747" if diagnostic.severity == "error" else "#cca700"
            item.setForeground(0, QtGui.QBrush(QtGui.QColor(color)))
            self._problems.addTopLevelItem(item)
        count = len(diagnostics)
        self._lint_badge.setText(f"{engine}: {count} problem{'s' if count != 1 else ''}")
        if count == 0:
            self._set_status(f"No problems found ({engine})")

    def _lint_failed(self, message: str) -> None:
        self._lint_badge.setText("Lint failed")
        self._set_status(message, error=True)

    def _problem_activated(self, item: QtWidgets.QTreeWidgetItem, _column: int) -> None:
        diagnostic = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        if isinstance(diagnostic, Diagnostic):
            self.editor.go_to(diagnostic.line, diagnostic.column)

    def scene_changed(self) -> None:
        self.reload(force=True)

    def _set_status(self, message: str, *, error: bool = False) -> None:
        self._status.setText(message)
        self._status.setStyleSheet("color: #f44747;" if error else "")

    def _show_error(self, title: str, message: str) -> None:
        self._set_status(message, error=True)
        QtWidgets.QMessageBox.critical(self, title, message)

    def shutdown(self) -> None:
        self._lint_timer.stop()
        self._ruff.shutdown()
