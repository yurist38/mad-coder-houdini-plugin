"""Asynchronous Ruff integration using Qt's process API."""

from __future__ import annotations

import ast
import os
import shutil
from pathlib import Path

from PySide6 import QtCore

from .diagnostics import Diagnostic, parse_ruff_output


def find_ruff() -> str | None:
    """Find an explicit, bundled, or PATH-provided Ruff executable."""

    configured = os.environ.get("MAD_CODER_RUFF")
    if configured and Path(configured).is_file():
        return configured

    content_root = Path(__file__).resolve().parents[3]
    executable = "ruff.exe" if os.name == "nt" else "ruff"
    bundled = content_root / "bin" / executable
    if bundled.is_file():
        return str(bundled)
    return shutil.which("ruff")


def syntax_diagnostics(text: str, filename: str) -> list[Diagnostic]:
    """Provide syntax errors when Ruff is unavailable."""

    try:
        ast.parse(text, filename=filename)
    except SyntaxError as exc:
        line = max(1, exc.lineno or 1)
        column = max(1, exc.offset or 1)
        end_line = max(line, exc.end_lineno or line)
        end_column = max(column + 1, exc.end_offset or column + 1)
        return [
            Diagnostic(
                line=line,
                column=column,
                end_line=end_line,
                end_column=end_column,
                message=exc.msg,
                code="syntax-error",
                severity="error",
            )
        ]
    return []


class RuffService(QtCore.QObject):
    """Run lint and format operations without blocking Houdini's UI."""

    lint_ready = QtCore.Signal(list, str)
    lint_failed = QtCore.Signal(str)
    format_ready = QtCore.Signal(str)
    format_failed = QtCore.Signal(str)

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self.executable = find_ruff()
        self._lint_process: QtCore.QProcess | None = None
        self._format_process: QtCore.QProcess | None = None
        self._lint_generation = 0

    @property
    def available(self) -> bool:
        return self.executable is not None

    def lint(self, text: str, filename: str) -> None:
        self._lint_generation += 1
        generation = self._lint_generation

        if not self.executable:
            self.lint_ready.emit(syntax_diagnostics(text, filename), "Syntax only")
            return

        if self._lint_process is not None:
            self._lint_process.kill()
            self._lint_process.deleteLater()

        process = QtCore.QProcess(self)
        self._lint_process = process
        encoded = text.encode("utf-8")
        process.started.connect(lambda p=process, data=encoded: self._write_input(p, data))
        process.finished.connect(
            lambda code, status, p=process, g=generation: self._lint_finished(p, g, code, status)
        )
        process.errorOccurred.connect(
            lambda _error, p=process, g=generation: self._process_error(p, g, "lint")
        )
        process.start(
            self.executable,
            [
                "check",
                "--isolated",
                "--output-format",
                "json",
                "--select",
                "E4,E7,E9,F",
                "--target-version",
                "py311",
                "--stdin-filename",
                filename,
                "-",
            ],
        )

    def format(self, text: str, filename: str) -> None:
        if not self.executable:
            self.format_failed.emit(
                "Ruff is unavailable. Install a release archive that includes Ruff or set "
                "MAD_CODER_RUFF."
            )
            return

        if self._format_process is not None:
            self._format_process.kill()
            self._format_process.deleteLater()

        process = QtCore.QProcess(self)
        self._format_process = process
        encoded = text.encode("utf-8")
        process.started.connect(lambda p=process, data=encoded: self._write_input(p, data))
        process.finished.connect(
            lambda code, status, p=process: self._format_finished(p, code, status)
        )
        process.errorOccurred.connect(lambda _error, p=process: self._process_error(p, 0, "format"))
        process.start(
            self.executable,
            [
                "format",
                "--isolated",
                "--target-version",
                "py311",
                "--stdin-filename",
                filename,
                "-",
            ],
        )

    @staticmethod
    def _write_input(process: QtCore.QProcess, data: bytes) -> None:
        process.write(data)
        process.closeWriteChannel()

    def _lint_finished(
        self,
        process: QtCore.QProcess,
        generation: int,
        exit_code: int,
        _exit_status: QtCore.QProcess.ExitStatus,
    ) -> None:
        if generation != self._lint_generation:
            process.deleteLater()
            return
        stdout = bytes(process.readAllStandardOutput()).decode("utf-8", errors="replace")
        stderr = bytes(process.readAllStandardError()).decode("utf-8", errors="replace").strip()
        if exit_code not in (0, 1):
            self.lint_failed.emit(stderr or f"Ruff exited with status {exit_code}")
        else:
            try:
                self.lint_ready.emit(parse_ruff_output(stdout), "Ruff")
            except ValueError as exc:
                self.lint_failed.emit(str(exc))
        if process is self._lint_process:
            self._lint_process = None
        process.deleteLater()

    def _format_finished(
        self,
        process: QtCore.QProcess,
        exit_code: int,
        _exit_status: QtCore.QProcess.ExitStatus,
    ) -> None:
        stdout = bytes(process.readAllStandardOutput()).decode("utf-8", errors="replace")
        stderr = bytes(process.readAllStandardError()).decode("utf-8", errors="replace").strip()
        if exit_code == 0:
            self.format_ready.emit(stdout)
        else:
            self.format_failed.emit(stderr or f"Ruff exited with status {exit_code}")
        if process is self._format_process:
            self._format_process = None
        process.deleteLater()

    def _process_error(self, process: QtCore.QProcess, generation: int, mode: str) -> None:
        if mode == "lint" and generation != self._lint_generation:
            process.deleteLater()
            return
        message = process.errorString() or f"Could not start Ruff {mode} process"
        if mode == "lint":
            if process is self._lint_process:
                self._lint_process = None
            self.lint_failed.emit(message)
        else:
            if process is self._format_process:
                self._format_process = None
            self.format_failed.emit(message)
        process.deleteLater()
    def shutdown(self) -> None:
        for process in (self._lint_process, self._format_process):
            if process is not None and process.state() != QtCore.QProcess.ProcessState.NotRunning:
                process.kill()
                process.waitForFinished(250)
