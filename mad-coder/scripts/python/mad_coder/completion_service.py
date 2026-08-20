"""Serialized background completion service for Houdini's Qt UI."""

from __future__ import annotations

from PySide6 import QtCore  # type: ignore[import-not-found]

from .completion import complete_python


class _CompletionWorker(QtCore.QObject):
    ready = QtCore.Signal(int, list)
    failed = QtCore.Signal(int, str)

    @QtCore.Slot(int, str, int, int, str, object)
    def complete(
        self,
        generation: int,
        text: str,
        line: int,
        column: int,
        filename: str,
        builtins: object,
    ) -> None:
        try:
            items = complete_python(text, line, column, filename, tuple(builtins))  # type: ignore[arg-type]
        except Exception as exc:
            self.failed.emit(generation, str(exc))
        else:
            self.ready.emit(generation, items)


class CompletionService(QtCore.QObject):
    """Run one Jedi request at a time and ignore superseded results."""

    completion_ready = QtCore.Signal(list)
    completion_failed = QtCore.Signal(str)
    _request = QtCore.Signal(int, str, int, int, str, object)

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._generation = 0
        self._stopped = False
        self._thread = QtCore.QThread(self)
        self._worker = _CompletionWorker()
        self._worker.moveToThread(self._thread)
        self._request.connect(self._worker.complete)
        self._worker.ready.connect(self._completed)
        self._worker.failed.connect(self._failed)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.start()

    def complete(
        self,
        text: str,
        line: int,
        column: int,
        filename: str,
        builtins: tuple[str, ...] = (),
    ) -> None:
        if self._stopped:
            return
        self._generation += 1
        self._request.emit(self._generation, text, line, column, filename, builtins)

    def cancel(self) -> None:
        """Invalidate any result that has not returned to the UI yet."""

        self._generation += 1

    @QtCore.Slot(int, list)
    def _completed(self, generation: int, items: list[object]) -> None:
        if not self._stopped and generation == self._generation:
            self.completion_ready.emit(items)

    @QtCore.Slot(int, str)
    def _failed(self, generation: int, message: str) -> None:
        if not self._stopped and generation == self._generation:
            self.completion_failed.emit(message)

    def shutdown(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        self._generation += 1
        self._thread.quit()
        self._thread.wait()
