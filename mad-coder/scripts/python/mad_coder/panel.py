"""The dockable Mad Coder panel."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

import hou  # type: ignore[import-not-found]
from PySide6 import QtCore, QtGui, QtWidgets  # type: ignore[import-not-found]

from .completion_service import CompletionService
from .console import ExecutionConsole
from .diagnostics import Diagnostic
from .editor import MadCoderEditor
from .execution import capture_execution
from .linting import RuffService
from .preferences import EditorPreferences, PreferencesStore, default_font_family
from .settings_dialog import SettingsDialog
from .source import SessionSource, SourceAdapter, SourceConflictError, code_sources_for_node
from .type_checking import TypeCheckService
from .vex_checking import VccService

_PYTHON_ANALYSIS_DELAY_MS = 400
_VEX_ANALYSIS_DELAY_MS = 1000


class MadCoderPanel(QtWidgets.QWidget):
    """Edit Python and VEX stored in the scene, nodes, and digital assets."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._hou = hou
        self._source = SessionSource(self._hou)
        self._baseline = ""
        self._loading = False
        self._updating_sources = False
        self._running = False
        self._completion_request_explicit = False
        self._selection_callback_registered = False
        self._diagnostics: list[Diagnostic] = []
        self._type_checking_enabled = True
        self._analysis_expected: set[str] = set()
        self._analysis_results: dict[str, list[Diagnostic]] = {}
        self._analysis_engines: dict[str, str] = {}
        self._analysis_failures: dict[str, str] = {}
        self._last_vex_checked_text: str | None = None
        self._vex_check_text: str | None = None
        self._editor_has_focus = False
        self._shutting_down = False

        available_fonts = list(QtGui.QFontDatabase.families())
        system_fixed_font = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.SystemFont.FixedFont)
        default_family = default_font_family(available_fonts, system_fixed_font.family())
        self._preferences = PreferencesStore(
            QtCore.QSettings("Mad Coder", "Mad Coder"),
            default_family,
            available_fonts,
        )

        self._source_selector = QtWidgets.QComboBox()
        self._source_selector.setMinimumContentsLength(28)
        self._source_selector.setSizeAdjustPolicy(
            QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self._source_selector.setToolTip("Choose the Python or VEX source to edit")
        self._follow_selection = QtWidgets.QCheckBox("Follow Selection")
        self._follow_selection.setChecked(True)
        self._follow_selection.setToolTip(
            "Open supported Python or VEX code when a node is selected in the network editor"
        )
        self._use_selected_button = QtWidgets.QPushButton("Use Selected")
        self._settings_button = QtWidgets.QPushButton("Settings…")
        self._settings_button.setToolTip("Configure Mad Coder")
        self._run_button = QtWidgets.QPushButton("Run")
        self._run_button.setToolTip(
            "Save and run the current source inside Houdini (Ctrl/Cmd+Enter)"
        )
        self._save_button = QtWidgets.QPushButton("Save")
        self._reload_button = QtWidgets.QPushButton("Reload")
        self._format_button = QtWidgets.QPushButton("Format")
        self._lint_badge = QtWidgets.QLabel()

        source_toolbar = QtWidgets.QHBoxLayout()
        source_toolbar.setContentsMargins(0, 0, 0, 0)
        source_toolbar.addWidget(self._source_selector, 1)
        source_toolbar.addWidget(self._follow_selection)
        source_toolbar.addWidget(self._use_selected_button)
        source_toolbar.addWidget(self._settings_button)

        action_toolbar = QtWidgets.QHBoxLayout()
        action_toolbar.setContentsMargins(0, 0, 0, 0)
        action_toolbar.addWidget(self._lint_badge)
        action_toolbar.addStretch(1)
        action_toolbar.addWidget(self._run_button)
        action_toolbar.addWidget(self._reload_button)
        action_toolbar.addWidget(self._format_button)
        action_toolbar.addWidget(self._save_button)

        self.editor = MadCoderEditor()
        self._apply_editor_preferences(self._preferences.load())

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

        self._console = ExecutionConsole()
        self._bottom_tabs = QtWidgets.QTabWidget()
        self._bottom_tabs.addTab(self._problems, "Problems")
        self._bottom_tabs.addTab(self._console, "Console")

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        splitter.addWidget(self.editor)
        splitter.addWidget(self._bottom_tabs)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([700, 180])

        self._status = QtWidgets.QLabel()
        self._status.setWordWrap(True)
        self._status.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        layout.addLayout(source_toolbar)
        layout.addLayout(action_toolbar)
        layout.addWidget(splitter, 1)
        layout.addWidget(self._status)

        self._lint_timer = QtCore.QTimer(self)
        self._lint_timer.setSingleShot(True)
        self._lint_timer.setInterval(_PYTHON_ANALYSIS_DELAY_MS)
        self._ruff = RuffService(self)
        self._type_checker = TypeCheckService(self)
        self._vcc = VccService(self)
        self._completion = CompletionService(self)

        self.editor.textChanged.connect(self._text_changed)
        self.editor.focus_changed.connect(self._editor_focus_changed)
        self.editor.completion_requested.connect(self._request_completion)
        self._source_selector.currentIndexChanged.connect(self._source_selected)
        self._follow_selection.toggled.connect(self._follow_selection_toggled)
        self._use_selected_button.clicked.connect(self._use_selected_node)
        self._settings_button.clicked.connect(self.open_settings)
        self._run_button.clicked.connect(self.run_code)
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
        self._completion.completion_ready.connect(self.editor.show_completions)
        self._completion.completion_failed.connect(self._completion_failed)
        self._type_checker.check_ready.connect(self._type_check_ready)
        self._type_checker.check_failed.connect(self._type_check_failed)
        self._vcc.check_ready.connect(self._vex_check_ready)
        self._vcc.check_failed.connect(self._vex_check_failed)

        self._shortcuts = [
            QtGui.QShortcut(QtGui.QKeySequence.StandardKey.Save, self),
            QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Shift+F"), self),
            QtGui.QShortcut(QtGui.QKeySequence("F5"), self),
            # "Ctrl" maps to Cmd on macOS; "Return"/"Enter" cover both the main and keypad keys.
            QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Return"), self),
            QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Enter"), self),
        ]
        self._shortcuts[0].activated.connect(self.save)
        self._shortcuts[1].activated.connect(self.format_code)
        self._shortcuts[2].activated.connect(self.reload)
        self._shortcuts[3].activated.connect(self.run_code)
        self._shortcuts[4].activated.connect(self.run_code)

        self._register_selection_callback()
        self._refresh_sources(follow=True)

    def _register_selection_callback(self) -> None:
        try:
            self._hou.ui.addSelectionCallback(self._selection_changed)
        except Exception as exc:
            self._set_status(f"Could not follow node selection: {exc}", error=True)
        else:
            self._selection_callback_registered = True

    def _selected_node(self, selection: Sequence[object] | None = None) -> object | None:
        if selection is None:
            try:
                selection = list(self._hou.selectedNodes())
            except Exception:
                return None
        for item in reversed(selection):
            if all(hasattr(item, attribute) for attribute in ("path", "type", "parm")):
                return item
        return None

    def _sources_for_selection(
        self, selection: Sequence[object] | None = None
    ) -> list[SourceAdapter]:
        node = self._selected_node(selection)
        if node is None:
            return []
        try:
            return code_sources_for_node(node, self._hou)
        except Exception as exc:
            self._set_status(f"Could not inspect the selected node: {exc}", error=True)
            return []

    def _refresh_sources(
        self,
        selection: Sequence[object] | None = None,
        *,
        follow: bool | None = None,
    ) -> None:
        discovered = self._sources_for_selection(selection)
        session = SessionSource(self._hou)
        sources = [session, *discovered]
        should_follow = self._follow_selection.isChecked() if follow is None else follow
        target = discovered[0] if should_follow and discovered else session

        if not should_follow:
            target = self._source
        if all(source.source_key != self._source.source_key for source in sources):
            sources.append(self._source)

        if target.source_key != self._source.source_key and self._is_dirty():
            target = self._source
            self._set_status(
                "Selection changed, but this editor has unsaved changes. Save or reload before "
                "following the new selection."
            )

        self._rebuild_source_selector(sources, target.source_key)
        if target.source_key != self._source.source_key:
            self._switch_source(target, confirm=False)
        elif not self._baseline and not self.editor.toPlainText():
            self.reload(force=True)

    def _rebuild_source_selector(self, sources: list[SourceAdapter], selected_key: str) -> None:
        self._updating_sources = True
        try:
            self._source_selector.clear()
            selected_index = 0
            for index, source in enumerate(sources):
                self._source_selector.addItem(source.display_name, source)
                if source.source_key == selected_key:
                    selected_index = index
            self._source_selector.setCurrentIndex(selected_index)
        finally:
            self._updating_sources = False
        self._update_source_title()

    def _selection_changed(self, selection: Sequence[object]) -> None:
        if self._follow_selection.isChecked():
            self._refresh_sources(list(selection), follow=True)

    def _follow_selection_toggled(self, enabled: bool) -> None:
        if enabled:
            self._refresh_sources(follow=True)

    def _use_selected_node(self) -> None:
        self._refresh_sources(follow=True)

    def _apply_editor_preferences(self, preferences: EditorPreferences) -> None:
        self.editor.set_code_font(preferences.font_family, preferences.font_size)
        self.editor.set_autocomplete_enabled(preferences.autocomplete_enabled)
        self._type_checking_enabled = preferences.type_checking_enabled

    def open_settings(self) -> None:
        font = self.editor.font()
        current = EditorPreferences(
            font.family(),
            font.pointSize(),
            self.editor.autocomplete_enabled,
            self._type_checking_enabled,
        )
        dialog = SettingsDialog(current, self._preferences.default, self)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        self._preferences.save(dialog.selected_preferences())
        preferences = self._preferences.load()
        self._apply_editor_preferences(preferences)
        if not preferences.autocomplete_enabled:
            self._completion.cancel()
        if not preferences.type_checking_enabled:
            self._type_checker.cancel()
        self._run_lint()
        autocomplete_status = "enabled" if preferences.autocomplete_enabled else "disabled"
        type_checking_status = "enabled" if preferences.type_checking_enabled else "disabled"
        self._set_status(
            f"Editor settings saved — {preferences.font_family} {preferences.font_size} pt; "
            f"autocomplete {autocomplete_status}; type checking {type_checking_status}"
        )

    def _source_selected(self, index: int) -> None:
        if self._updating_sources or index < 0:
            return
        source = cast(SourceAdapter | None, self._source_selector.itemData(index))
        if source is None or source.source_key == self._source.source_key:
            return
        if not self._switch_source(source, confirm=True):
            self._select_source_key(self._source.source_key)

    def _select_source_key(self, source_key: str) -> None:
        self._updating_sources = True
        try:
            for index in range(self._source_selector.count()):
                source = cast(SourceAdapter | None, self._source_selector.itemData(index))
                if source is not None and source.source_key == source_key:
                    self._source_selector.setCurrentIndex(index)
                    break
        finally:
            self._updating_sources = False

    def _switch_source(self, source: SourceAdapter, *, confirm: bool) -> bool:
        if confirm and self._is_dirty():
            answer = QtWidgets.QMessageBox.question(
                self,
                "Discard unsaved changes?",
                "Switching sources will discard the changes in this editor.",
                QtWidgets.QMessageBox.StandardButton.Discard
                | QtWidgets.QMessageBox.StandardButton.Cancel,
                QtWidgets.QMessageBox.StandardButton.Cancel,
            )
            if answer != QtWidgets.QMessageBox.StandardButton.Discard:
                return False

        previous = self._source
        self._source = source
        if self.reload(force=True):
            self._select_source_key(source.source_key)
            return True
        self._source = previous
        self._select_source_key(previous.source_key)
        return False

    def _is_dirty(self) -> bool:
        return self.editor.toPlainText() != self._baseline

    def _read_only_reason(self) -> str | None:
        try:
            return self._source.read_only_reason()
        except Exception as exc:
            return str(exc)

    def _apply_source_state(self) -> str | None:
        reason = self._read_only_reason()
        read_only = reason is not None
        self.editor.setReadOnly(read_only)
        if read_only:
            self.editor.hide_completions()
        python_source = self._source.language == "python"
        self._format_button.setEnabled(not read_only and python_source)
        self._format_button.setToolTip(
            "Format Python with Ruff" if python_source else "Formatting is unavailable for VEX"
        )
        self._save_button.setEnabled(self._is_dirty() and not read_only)
        self._run_button.setEnabled(not self._running)
        return reason

    def _source_notice(self) -> tuple[str, bool]:
        reason = self._read_only_reason()
        if reason:
            return f"view only: {reason}", True
        if self._source.save_warning:
            return self._source.save_warning, False
        return "", False

    def _update_source_title(self) -> None:
        dirty_key = self._source.source_key if self._is_dirty() else None
        for index in range(self._source_selector.count()):
            source = self._source_selector.itemData(index)
            if source is None:
                continue
            suffix = " *" if dirty_key and source.source_key == dirty_key else ""
            self._source_selector.setItemText(index, source.display_name + suffix)

    def _text_changed(self) -> None:
        if self._loading:
            return
        if self.editor.hasFocus():
            self._editor_has_focus = True
        self._apply_source_state()
        self._update_source_title()
        if self._source.language == "vex":
            # Invalidate an in-flight result immediately. The process may finish quietly,
            # so typing never waits for or repeatedly hard-kills vcc.
            self._vcc.cancel()
            self._vex_check_text = None
            self._lint_timer.setInterval(_VEX_ANALYSIS_DELAY_MS)
            if not self._vex_analysis_is_active():
                self._lint_timer.stop()
                self._lint_badge.setText("VEX check paused")
                return
            self._lint_badge.setText("VEX check pending…")
        else:
            self._lint_timer.setInterval(_PYTHON_ANALYSIS_DELAY_MS)
            self._lint_badge.setText("Checking…")
        self._lint_timer.start()

    def reload(self, force: bool = False) -> bool:
        if not force and self._is_dirty():
            answer = QtWidgets.QMessageBox.question(
                self,
                "Discard unsaved changes?",
                f"Reloading {self._source.display_name} will discard the changes in this editor.",
                QtWidgets.QMessageBox.StandardButton.Discard
                | QtWidgets.QMessageBox.StandardButton.Cancel,
                QtWidgets.QMessageBox.StandardButton.Cancel,
            )
            if answer != QtWidgets.QMessageBox.StandardButton.Discard:
                return False

        try:
            source = self._source.load()
        except Exception as exc:  # Houdini reports API failures through several exception types.
            self._show_error(f"Could not read {self._source.display_name}", str(exc))
            return False

        self._completion.cancel()
        self.editor.hide_completions()
        self.editor.set_language(self._source.language)
        self._loading = True
        self.editor.setPlainText(source)
        self._loading = False
        self._baseline = source
        self._last_vex_checked_text = None
        self._vex_check_text = None
        self._apply_source_state()
        self.editor.setPlaceholderText(self._source.placeholder)
        self._update_source_title()
        notice, notice_is_error = self._source_notice()
        message = f"Loaded {self._source.display_name}"
        if notice:
            message += f" — {notice}"
        self._set_status(message, error=notice_is_error)
        self._run_lint()
        return True

    def save(self) -> None:
        reason = self._read_only_reason()
        if reason:
            self._show_error("Source is view-only", reason)
            return
        text = self.editor.toPlainText()
        try:
            self._source.save(text, self._baseline)
        except SourceConflictError:
            self._resolve_conflict(text)
            return
        except Exception as exc:
            self._show_error(f"Could not save {self._source.display_name}", str(exc))
            return
        self._mark_saved(text)

    def _resolve_conflict(self, text: str) -> None:
        box = QtWidgets.QMessageBox(self)
        box.setIcon(QtWidgets.QMessageBox.Icon.Warning)
        box.setWindowTitle("Code source changed")
        box.setText(f"{self._source.display_name} was changed outside this editor.")
        box.setInformativeText(
            "Reload the external version or overwrite it with this editor's text?"
        )
        reload_button = box.addButton("Reload", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        overwrite_button = box.addButton(
            "Overwrite", QtWidgets.QMessageBox.ButtonRole.DestructiveRole
        )
        box.addButton("Cancel", QtWidgets.QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is reload_button:
            self.reload(force=True)
        elif box.clickedButton() is overwrite_button:
            try:
                self._source.save(text, expected=None)
            except Exception as exc:
                self._show_error(f"Could not overwrite {self._source.display_name}", str(exc))
            else:
                self._mark_saved(text)

    def _mark_saved(self, text: str) -> None:
        self._baseline = text
        self._apply_source_state()
        self._update_source_title()
        self._set_status(f"Saved {self._source.display_name}")

    def run_code(self) -> None:
        if self._running:
            return

        read_only_reason = self._read_only_reason()
        text = self.editor.toPlainText()
        if read_only_reason is None:
            try:
                current = self._source.load()
            except Exception as exc:
                self._show_error(f"Could not read {self._source.display_name}", str(exc))
                return
            if current != self._baseline:
                self._resolve_conflict(text)
                return

        self._bottom_tabs.setCurrentWidget(self._console)
        self._console.begin(self._source.display_name)
        self._running = True
        self._apply_source_state()
        self._set_status(f"Running {self._source.display_name}…")
        saved = False

        def execute() -> None:
            nonlocal saved
            if read_only_reason is None:
                self._source.save(text, self._baseline)
                saved = True
            self._source.execute()

        result = capture_execution(execute)
        self._running = False
        if saved:
            self._baseline = text
            self._update_source_title()
        self._apply_source_state()
        self._console.finish(result)

        if result.succeeded:
            self._set_status(f"Completed {self._source.display_name}")
        else:
            self._set_status(
                f"Execution failed: {type(result.exception).__name__}: {result.exception}",
                error=True,
            )

    def format_code(self) -> None:
        if self.editor.isReadOnly() or self._source.language != "python":
            return
        self._set_status("Formatting with Ruff…")
        self._ruff.format(self.editor.toPlainText(), self._source.lint_filename)

    def _format_ready(self, text: str) -> None:
        self._completion.cancel()
        self.editor.hide_completions()
        cursor = self.editor.textCursor()
        position = cursor.position()
        self.editor.setPlainText(text)
        cursor = self.editor.textCursor()
        cursor.setPosition(min(position, max(0, len(text))))
        self.editor.setTextCursor(cursor)
        self._set_status("Formatted with Ruff; save to apply")

    def _format_failed(self, message: str) -> None:
        self._set_status(f"Format failed: {message}", error=True)

    def _request_completion(self, explicit: bool) -> None:
        if self._source.language != "python":
            return
        cursor = self.editor.textCursor()
        self._completion_request_explicit = explicit
        self._completion.complete(
            self.editor.toPlainText(),
            cursor.blockNumber() + 1,
            cursor.positionInBlock(),
            self._source.lint_filename,
            self._source.lint_builtins,
        )

    def _completion_failed(self, message: str) -> None:
        self.editor.hide_completions()
        if self._completion_request_explicit:
            self._set_status(f"Autocomplete unavailable: {message}", error=True)

    def _run_lint(self) -> None:
        text = self.editor.toPlainText()
        filename = self._source.lint_filename
        builtins = self._source.lint_builtins
        ignored_codes = self._source.lint_ignores
        self._analysis_results = {}
        self._analysis_engines = {}
        self._analysis_failures = {}
        if self._source.language == "vex":
            if not self._vex_analysis_is_active():
                self._analysis_expected = set()
                self._vex_check_text = None
                self._lint_badge.setText("VEX check paused")
                return
            self._analysis_expected = {"vex"}
            self._vex_check_text = text
            self._lint_badge.setText("Checking VEX…")
            self._completion.cancel()
            self._ruff.cancel_lint()
            self._type_checker.cancel()
            self._vcc.check(text, filename)
            return

        self._analysis_expected = {"ruff"}
        self._vcc.cancel()
        if self._type_checking_enabled and self._type_checker.available:
            self._analysis_expected.add("ty")
            self._type_checker.check(text, filename, builtins)
        else:
            self._type_checker.cancel()
        self._ruff.lint(text, filename, builtins, ignored_codes)

    def _lint_ready(self, diagnostics: list[Diagnostic], engine: str) -> None:
        self._analysis_ready("ruff", diagnostics, engine)

    def _type_check_ready(self, diagnostics: list[Diagnostic], engine: str) -> None:
        self._analysis_ready("ty", diagnostics, engine)

    def _vex_check_ready(self, diagnostics: list[Diagnostic], engine: str) -> None:
        if self._vex_check_text == self.editor.toPlainText():
            self._last_vex_checked_text = self._vex_check_text
        self._analysis_ready("vex", diagnostics, engine)

    def _analysis_ready(self, source: str, diagnostics: list[Diagnostic], engine: str) -> None:
        if source not in self._analysis_expected:
            return
        self._analysis_results[source] = diagnostics
        self._analysis_engines[source] = engine
        if not self._analysis_expected.issubset(self._analysis_results):
            labels = {"ruff": "Ruff", "ty": "ty", "vex": "VEX"}
            pending = [
                labels[key]
                for key in ("ruff", "ty", "vex")
                if key in self._analysis_expected and key not in self._analysis_results
            ]
            self._lint_badge.setText(f"Checking {' + '.join(pending)}…")
            return

        combined = [
            diagnostic
            for key in ("ruff", "ty", "vex")
            for diagnostic in self._analysis_results.get(key, [])
        ]
        combined.sort(key=lambda diagnostic: (diagnostic.line, diagnostic.column, diagnostic.code))
        engines = [
            self._analysis_engines[key]
            for key in ("ruff", "ty", "vex")
            if key in self._analysis_engines
        ]
        if self._type_checking_enabled and not self._type_checker.available:
            engines.append("ty unavailable")
        self._render_diagnostics(combined, " + ".join(engines))

    def _render_diagnostics(self, diagnostics: list[Diagnostic], engine: str) -> None:
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
            notice, notice_is_error = self._source_notice()
            message = f"No problems found ({engine})"
            if notice:
                message += f" — {notice}"
            self._set_status(message, error=notice_is_error)

    def _lint_failed(self, message: str) -> None:
        self._analysis_failed("ruff", message)

    def _type_check_failed(self, message: str) -> None:
        self._analysis_failed("ty", message)

    def _vex_check_failed(self, message: str) -> None:
        if self._vex_check_text == self.editor.toPlainText():
            self._last_vex_checked_text = self._vex_check_text
        self._analysis_failed("vex", message)

    def _vex_analysis_is_active(self) -> bool:
        return not self._shutting_down and (self._editor_has_focus or self.editor.hasFocus())

    def _pause_vex_analysis(self) -> None:
        if self._source.language != "vex":
            return
        was_pending = self._lint_timer.isActive()
        self._lint_timer.stop()
        if was_pending:
            self._lint_badge.setText("VEX check paused")
        elif self._vcc.running:
            self._lint_badge.setText("Checking VEX in background…")

    def _resume_vex_analysis(self) -> None:
        if self._source.language != "vex" or not self._vex_analysis_is_active():
            return
        text = self.editor.toPlainText()
        if self._vcc.running and self._vex_check_text == text:
            self._lint_badge.setText("Checking VEX…")
            return
        if text == self._last_vex_checked_text:
            return
        self._lint_timer.setInterval(_VEX_ANALYSIS_DELAY_MS)
        self._lint_badge.setText("VEX check pending…")
        self._lint_timer.start()

    def _editor_focus_changed(self, focused: bool) -> None:
        self._editor_has_focus = focused
        if focused:
            self._resume_vex_analysis()
        else:
            self._pause_vex_analysis()

    def showEvent(self, event: QtGui.QShowEvent) -> None:  # noqa: N802 - Qt API name
        super().showEvent(event)
        self._resume_vex_analysis()

    def hideEvent(self, event: QtGui.QHideEvent) -> None:  # noqa: N802 - Qt API name
        self._pause_vex_analysis()
        super().hideEvent(event)

    def _analysis_failed(self, source: str, message: str) -> None:
        if source not in self._analysis_expected:
            return
        self._analysis_failures[source] = message
        labels = {"ruff": "Ruff", "ty": "Type checking", "vex": "VEX syntax check"}
        label = labels[source]
        self._analysis_ready(source, [], f"{label} failed")
        self._set_status(f"{label} failed: {message}", error=True)

    def _problem_activated(self, item: QtWidgets.QTreeWidgetItem, _column: int) -> None:
        diagnostic = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        if isinstance(diagnostic, Diagnostic):
            self.editor.go_to(diagnostic.line, diagnostic.column)

    def scene_changed(self) -> None:
        if self._is_dirty():
            answer = QtWidgets.QMessageBox.question(
                self,
                "Discard unsaved changes?",
                "The scene changed. Reloading will discard the changes in this editor.",
                QtWidgets.QMessageBox.StandardButton.Discard
                | QtWidgets.QMessageBox.StandardButton.Cancel,
                QtWidgets.QMessageBox.StandardButton.Cancel,
            )
            if answer != QtWidgets.QMessageBox.StandardButton.Discard:
                self._refresh_sources(follow=self._follow_selection.isChecked())
                return

        self._source = SessionSource(self._hou)
        self.reload(force=True)
        self._refresh_sources(follow=self._follow_selection.isChecked())

    def _set_status(self, message: str, *, error: bool = False) -> None:
        self._status.setText(message)
        self._status.setStyleSheet("color: #f44747;" if error else "")

    def _show_error(self, title: str, message: str) -> None:
        self._set_status(message, error=True)
        QtWidgets.QMessageBox.critical(self, title, message)

    def shutdown(self) -> None:
        self._shutting_down = True
        if self._selection_callback_registered:
            try:
                self._hou.ui.removeSelectionCallback(self._selection_changed)
            except Exception:
                pass
            self._selection_callback_registered = False
        self._lint_timer.stop()
        self.editor.hide_completions()
        self._completion.shutdown()
        self._type_checker.shutdown()
        self._vcc.shutdown()
        self._ruff.shutdown()
