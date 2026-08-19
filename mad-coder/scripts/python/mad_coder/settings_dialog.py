"""Mad Coder settings dialog."""

from __future__ import annotations

from PySide6 import QtGui, QtWidgets

from .preferences import (
    MAX_FONT_SIZE,
    MIN_FONT_SIZE,
    EditorPreferences,
)


class SettingsDialog(QtWidgets.QDialog):
    """Sectioned settings window with editor font controls."""

    def __init__(
        self,
        current: EditorPreferences,
        defaults: EditorPreferences,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._defaults = defaults
        self.setWindowTitle("Mad Coder Settings")
        self.setModal(True)
        self.resize(620, 360)

        self._sections = QtWidgets.QListWidget()
        self._sections.setFixedWidth(140)
        self._sections.addItem("Editor")

        self._font_family = QtWidgets.QFontComboBox()
        self._font_family.setFontFilters(QtWidgets.QFontComboBox.FontFilter.MonospacedFonts)
        self._font_size = QtWidgets.QSpinBox()
        self._font_size.setRange(MIN_FONT_SIZE, MAX_FONT_SIZE)
        self._font_size.setSuffix(" pt")

        form = QtWidgets.QFormLayout()
        form.addRow("Font family", self._font_family)
        form.addRow("Font size", self._font_size)

        self._preview = QtWidgets.QPlainTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setPlainText(
            "def create_point(position=(1.0, 2.0, 3.0)):\n"
            "    point = hou.pwd().geometry().createPoint()\n"
            "    point.setPosition(position)\n"
            "    return point"
        )
        self._preview.setMaximumBlockCount(20)

        editor_page = QtWidgets.QWidget()
        editor_layout = QtWidgets.QVBoxLayout(editor_page)
        editor_layout.setContentsMargins(12, 0, 0, 0)
        editor_layout.addLayout(form)
        editor_layout.addWidget(QtWidgets.QLabel("Preview"))
        editor_layout.addWidget(self._preview, 1)

        self._pages = QtWidgets.QStackedWidget()
        self._pages.addWidget(editor_page)

        content = QtWidgets.QHBoxLayout()
        content.addWidget(self._sections)
        content.addWidget(self._pages, 1)

        self._buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
            | QtWidgets.QDialogButtonBox.StandardButton.RestoreDefaults
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(content, 1)
        layout.addWidget(self._buttons)

        self._sections.currentRowChanged.connect(self._pages.setCurrentIndex)
        self._font_family.currentFontChanged.connect(self._update_preview)
        self._font_size.valueChanged.connect(self._update_preview)
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        restore = self._buttons.button(QtWidgets.QDialogButtonBox.StandardButton.RestoreDefaults)
        if restore is not None:
            restore.clicked.connect(self._restore_defaults)

        self._set_preferences(current)
        self._sections.setCurrentRow(0)

    def selected_preferences(self) -> EditorPreferences:
        return EditorPreferences(self._font_family.currentFont().family(), self._font_size.value())

    def _set_preferences(self, preferences: EditorPreferences) -> None:
        self._font_family.setCurrentFont(QtGui.QFont(preferences.font_family))
        self._font_size.setValue(preferences.font_size)
        self._update_preview()

    def _restore_defaults(self) -> None:
        self._set_preferences(self._defaults)

    def _update_preview(self, *_args: object) -> None:
        font = QtGui.QFont(self._font_family.currentFont().family(), self._font_size.value())
        font.setStyleHint(QtGui.QFont.StyleHint.Monospace)
        self._preview.setFont(font)
