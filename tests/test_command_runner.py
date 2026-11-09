import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from imslim.command_runner import CancelledError, CommandRunner, CompressionContext

_SLEEP = "import time; time.sleep(10)"


def _python(code: str) -> list[str]:
    return [sys.executable, "-c", code]


def test_timeout_kills_a_slow_process() -> None:
    start = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        CommandRunner().run(_python(_SLEEP), CompressionContext(), subprocess.PIPE, timeout=0.2)
    assert time.monotonic() - start < 5


def _run_in_thread(context: CompressionContext) -> tuple[threading.Thread, list[BaseException]]:
    errors: list[BaseException] = []

    def run() -> None:
        try:
            CommandRunner().run(_python(_SLEEP), context, subprocess.PIPE, 30)
        except BaseException as err:
            errors.append(err)

    thread = threading.Thread(target=run)
    thread.start()
    return thread, errors


def test_cancel_stops_a_running_process() -> None:
    context = CompressionContext()
    thread, errors = _run_in_thread(context)

    context.cancel()
    thread.join(5)

    assert not thread.is_alive()
    assert len(errors) == 1
    assert isinstance(errors[0], CancelledError)


def test_cancel_kills_a_process_that_ignores_sigterm(tmp_path: Path) -> None:
    marker = tmp_path / "ready"
    code = (
        "import pathlib, signal, time; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        f"pathlib.Path({str(marker)!r}).write_text('ready'); "
        "time.sleep(10)"
    )
    context = CompressionContext()
    errors: list[BaseException] = []

    def run() -> None:
        try:
            CommandRunner().run(_python(code), context, subprocess.PIPE, 30)
        except BaseException as err:
            errors.append(err)

    thread = threading.Thread(target=run)
    thread.start()
    deadline = time.monotonic() + 5
    while not marker.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert marker.exists()

    context.cancel()
    thread.join(5)

    assert not thread.is_alive()
    assert len(errors) == 1
    assert isinstance(errors[0], CancelledError)
