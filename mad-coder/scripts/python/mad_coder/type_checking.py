"""Asynchronous ty type checking using Qt's process API."""

from __future__ import annotations

import ast
import os
import re
import shutil
import tempfile
from pathlib import Path

from PySide6 import QtCore  # type: ignore[import-not-found]

from .diagnostics import parse_ty_output
from .type_analysis import type_analysis_source

_RUFF_OWNED_CODES = {"ty:invalid-syntax", "ty:unresolved-reference"}
_CHECK_TIMEOUT_MS = 10_000


def find_ty() -> str | None:
    """Find an explicit, bundled, or PATH-provided ty executable."""

    configured = os.environ.get("MAD_CODER_TY")
    if configured and Path(configured).is_file():
        return configured

    content_root = Path(__file__).resolve().parents[3]
    executable = "ty.exe" if os.name == "nt" else "ty"
    bundled = content_root / "bin" / executable
    if bundled.is_file():
        return str(bundled)
    return shutil.which("ty")


def _safe_filename(filename: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(filename).name).strip("._")
    if not name.endswith(".py"):
        name += ".py"
    return name or "houdini_source.py"


class TypeCheckService(QtCore.QObject):
    """Run ty without blocking Houdini's UI or executing editor code."""

    check_ready = QtCore.Signal(list, str)
    check_failed = QtCore.Signal(str)

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self.executable = find_ty()
        self._process: QtCore.QProcess | None = None
        self._requests: dict[
            QtCore.QProcess,
            tuple[tempfile.TemporaryDirectory[str], int],
        ] = {}
        self._pending: tuple[str, str, tuple[str, ...], int] | None = None
        self._generation = 0

    @property
    def available(self) -> bool:
        return self.executable is not None

    def check(self, text: str, filename: str, builtins: tuple[str, ...] = ()) -> None:
        self._generation += 1
        generation = self._generation
        self._pending = None
        if self._process is not None:
            self._pending = (text, filename, builtins, generation)
            return
        self._start_check(text, filename, builtins, generation)

    def _start_check(
        self,
        text: str,
        filename: str,
        builtins: tuple[str, ...],
        generation: int,
    ) -> None:
        if generation != self._generation:
            return
        if not self.executable:
            self.check_ready.emit([], "Type checking unavailable")
            return

        temporary: tempfile.TemporaryDirectory[str] | None = None
        try:
            # Ruff reports syntax errors. Avoid launching ty when it cannot perform
            # meaningful type analysis of the module.
            ast.parse(text, filename=filename)
            source, line_offset = type_analysis_source(text, builtins)
            temporary = tempfile.TemporaryDirectory(prefix="mad-coder-ty-")
            source_path = Path(temporary.name) / _safe_filename(filename)
            source_path.write_text(source, encoding="utf-8")
        except (OSError, SyntaxError, ValueError) as exc:
            if temporary is not None:
                temporary.cleanup()
            if isinstance(exc, SyntaxError):
                self.check_ready.emit([], "ty")
            else:
                self.check_failed.emit(f"Could not prepare type checking: {exc}")
            return

        process = QtCore.QProcess(self)
        self._process = process
        self._requests[process] = (temporary, line_offset)
        process.finished.connect(
            lambda code, status, p=process, g=generation: self._finished(p, g, code, status)
        )
        process.errorOccurred.connect(
            lambda _error, p=process, g=generation: self._process_error(p, g)
        )
        timeout = QtCore.QTimer(process)
        timeout.setSingleShot(True)
        timeout.timeout.connect(lambda p=process, g=generation: self._timed_out(p, g))
        timeout.start(_CHECK_TIMEOUT_MS)
        stub_path = Path(__file__).resolve().parents[1]
        process.start(
            self.executable,
            [
                "check",
                "--no-progress",
                "--output-format",
                "gitlab",
                "--python-version",
                "3.11",
                "--ignore",
                "unresolved-reference",
                "--extra-search-path",
                str(stub_path),
                str(source_path),
            ],
        )

    def _finished(
        self,
        process: QtCore.QProcess,
        generation: int,
        exit_code: int,
        _exit_status: QtCore.QProcess.ExitStatus,
    ) -> None:
        request = self._requests.get(process)
        if request is None:
            return
        if generation == self._generation:
            stdout = bytes(process.readAllStandardOutput()).decode("utf-8", errors="replace")
            stderr = bytes(process.readAllStandardError()).decode(
                "utf-8", errors="replace"
            ).strip()
            if exit_code not in (0, 1):
                self.check_failed.emit(stderr or f"ty exited with status {exit_code}")
            else:
                try:
                    diagnostics = [
                        diagnostic
                        for diagnostic in parse_ty_output(stdout, request[1])
                        if diagnostic.code not in _RUFF_OWNED_CODES
                    ]
                    self.check_ready.emit(diagnostics, "ty")
                except ValueError as exc:
                    self.check_failed.emit(str(exc))
        if process is self._process:
            self._process = None
        self._dispose_request(process)
        self._start_pending()

    def _process_error(self, process: QtCore.QProcess, generation: int) -> None:
        if process not in self._requests:
            return
        if generation == self._generation:
            self.check_failed.emit(process.errorString() or "Could not start ty type checker")
        if process is self._process:
            self._process = None
        self._dispose_request(process)
        self._start_pending()

    def _timed_out(self, process: QtCore.QProcess, generation: int) -> None:
        if process not in self._requests:
            return
        if process.state() != QtCore.QProcess.ProcessState.NotRunning:
            process.kill()
        if generation == self._generation:
            self._generation += 1
            self.check_failed.emit("ty did not finish within 10 seconds")

    def _dispose_request(self, process: QtCore.QProcess) -> None:
        request = self._requests.pop(process, None)
        if request is not None:
            request[0].cleanup()
        process.deleteLater()

    def _start_pending(self) -> None:
        if self._process is not None or self._pending is None:
            return
        text, filename, builtins, generation = self._pending
        self._pending = None
        self._start_check(text, filename, builtins, generation)

    def cancel(self) -> None:
        self._generation += 1
        self._pending = None

    def shutdown(self) -> None:
        self._generation += 1
        self._pending = None
        for process in list(self._requests):
            if process.state() != QtCore.QProcess.ProcessState.NotRunning:
                process.kill()
                process.waitForFinished(250)
            self._dispose_request(process)
