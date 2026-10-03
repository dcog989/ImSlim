import subprocess
import threading
import time
from typing import IO


class CancelledError(Exception):
    """Raised to abort a compression when the batch is cancelled."""


# Bound on how long a termination attempt waits before escalating to kill.
_KILL_GRACE_SECONDS = 0.5


class CompressionContext:
    """Shared cancellation state for one compression batch."""

    def __init__(self) -> None:
        self._cancel_event: threading.Event = threading.Event()
        self._processes: list[subprocess.Popen[bytes]] = []
        self._lock: threading.Lock = threading.Lock()

    @property
    def cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def register_process(self, process: subprocess.Popen[bytes]) -> None:
        with self._lock:
            if not self._cancel_event.is_set():
                self._processes.append(process)
                return
        try:
            process.terminate()
        except OSError:
            pass

    def unregister_process(self, process: subprocess.Popen[bytes]) -> None:
        with self._lock:
            if process in self._processes:
                self._processes.remove(process)

    def cancel(self) -> None:
        if self._cancel_event.is_set():
            return
        self._cancel_event.set()
        with self._lock:
            processes = list(self._processes)
        deadline = time.monotonic() + _KILL_GRACE_SECONDS
        for process in processes:
            try:
                process.terminate()
            except OSError:
                pass
        for process in processes:
            try:
                remaining = max(0.0, deadline - time.monotonic())
                _res = process.wait(timeout=remaining)
            except subprocess.TimeoutExpired, OSError:
                try:
                    process.kill()
                except OSError:
                    pass


class CommandRunner:
    """Run one tool invocation as a killable subprocess."""

    def run(
        self,
        argv: list[str],
        context: CompressionContext,
        stdout: int | IO[bytes] | None,
        timeout: int,
    ) -> None:
        process: subprocess.Popen[bytes] = subprocess.Popen(
            argv, stdout=stdout, stderr=subprocess.PIPE
        )
        context.register_process(process)
        try:
            try:
                stdout_data, stderr_data = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                _res = process.communicate()
                raise
        finally:
            context.unregister_process(process)
        if context.cancelled:
            raise CancelledError
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, argv, stdout_data, stderr_data)
