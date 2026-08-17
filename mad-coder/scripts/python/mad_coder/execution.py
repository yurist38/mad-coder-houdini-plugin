"""Capture synchronous Python output produced inside Houdini."""

from __future__ import annotations

import contextlib
import io
import logging
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ExecutionResult:
    """Output and status from one synchronous execution."""

    output: str
    succeeded: bool
    duration_seconds: float
    exception: BaseException | None = None


def capture_execution(action: Callable[[], Any]) -> ExecutionResult:
    """Run an action while capturing stdout, stderr, logging, and tracebacks."""

    output = io.StringIO()
    handler = logging.StreamHandler(output)
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    started = time.perf_counter()
    exception: BaseException | None = None

    try:
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            action()
    except BaseException as exc:
        exception = exc
        traceback.print_exc(file=output)
    finally:
        root_logger.removeHandler(handler)
        handler.close()

    return ExecutionResult(
        output=output.getvalue(),
        succeeded=exception is None,
        duration_seconds=time.perf_counter() - started,
        exception=exception,
    )
