"""Asynchronous integration with Houdini's bundled VEX compiler."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

from PySide6 import QtCore  # type: ignore[import-not-found]

from .vex import VexAnalysisSource, parse_vcc_output, vex_snippet_source

_CHECK_TIMEOUT_MS = 10_000


def find_vcc() -> str | None:
    """Find an explicit or Houdini-provided VEX compiler."""

    configured = os.environ.get("MAD_CODER_VCC")
    if configured and Path(configured).is_file():
        return configured

    executable_name = "vcc.exe" if os.name == "nt" else "vcc"
    hfs = os.environ.get("HFS")
    candidates = []
    if hfs:
        candidates.append(Path(hfs) / "bin" / executable_name)
    candidates.append(Path(sys.executable).resolve().with_name(executable_name))
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return shutil.which("vcc")


class VccService(QtCore.QObject):
    """Compile analysis-only VEX snippets without blocking Houdini's UI."""

    check_ready = QtCore.Signal(list, str)
    check_failed = QtCore.Signal(str)

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self.executable = find_vcc()
        self._process: QtCore.QProcess | None = None
        self._requests: dict[
            QtCore.QProcess,
            tuple[tempfile.TemporaryDirectory[str], VexAnalysisSource],
        ] = {}
        self._pending: tuple[str, str, int] | None = None
        self._generation = 0

    @property
    def available(self) -> bool:
        return self.executable is not None

    @property
    def running(self) -> bool:
        return self._process is not None

    def check(self, text: str, filename: str) -> None:
        """Check the latest text, queueing it behind a compiler already in flight."""

        self._generation += 1
        generation = self._generation
        self._pending = None
        if self._process is not None:
            self._pending = (text, filename, generation)
            return
        self._start_check(text, filename, generation)

    def _start_check(self, text: str, filename: str, generation: int) -> None:
        if generation != self._generation:
            return
        if not self.executable:
            self.check_ready.emit([], "VEX syntax unavailable")
            return

        try:
            analysis = vex_snippet_source(text)
            temporary = tempfile.TemporaryDirectory(prefix="mad-coder-vcc-")
            source_path = Path(temporary.name) / Path(filename).name
            output_path = Path(temporary.name) / "mad_coder_check.vex"
            source_path.write_text(analysis.source, encoding="utf-8")
        except (OSError, ValueError) as exc:
            self.check_failed.emit(f"Could not prepare VEX syntax check: {exc}")
            return

        process = QtCore.QProcess(self)
        self._process = process
        self._requests[process] = (temporary, analysis)
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
        process.start(
            self.executable,
            [
                "--context",
                "cvex",
                "--compile-all",
                "--no-optimize",
                "--Wno-info",
                "--vex-output",
                str(output_path),
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
        if process not in self._requests:
            return
        if generation == self._generation:
            stderr = bytes(process.readAllStandardError()).decode(
                "utf-8", errors="replace"
            ).strip()
            request = self._requests.get(process)
            analysis = request[1] if request is not None else None
            diagnostics = parse_vcc_output(stderr, analysis=analysis)
            if diagnostics or exit_code == 0:
                self.check_ready.emit(diagnostics, "VEX")
            else:
                self.check_failed.emit(stderr or f"vcc exited with status {exit_code}")
        if process is self._process:
            self._process = None
        self._dispose_request(process)
        self._start_pending()

    def _process_error(self, process: QtCore.QProcess, generation: int) -> None:
        if process not in self._requests:
            return
        if generation == self._generation:
            self.check_failed.emit(process.errorString() or "Could not start the VEX compiler")
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
            self.check_failed.emit("vcc did not finish within 10 seconds")

    def _start_pending(self) -> None:
        if self._process is not None or self._pending is None:
            return
        text, filename, generation = self._pending
        self._pending = None
        self._start_check(text, filename, generation)

    def _dispose_request(self, process: QtCore.QProcess) -> None:
        request = self._requests.pop(process, None)
        if request is not None:
            request[0].cleanup()
        process.deleteLater()

    def cancel(self) -> None:
        """Invalidate current results without killing an in-flight compiler."""

        self._generation += 1
        self._pending = None

    def shutdown(self) -> None:
        self._generation += 1
        self._pending = None
        # It is safe to wait during panel destruction, and doing so prevents Qt from
        # destroying a QProcess while the native compiler is still exiting.
        for process in list(self._requests):
            if process.state() != QtCore.QProcess.ProcessState.NotRunning:
                process.kill()
                process.waitForFinished(250)
            self._dispose_request(process)
        self._process = None
