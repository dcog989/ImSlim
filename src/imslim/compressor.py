import html
import logging
import os
import subprocess
import threading
import time

logger = logging.getLogger(__name__)
from abc import ABC, abstractmethod
from collections.abc import Callable
from string.templatelib import Interpolation, Template
from typing import IO, NamedTuple, cast

from ._i18n import _
from .output_writer import OutputWriter
from .result_item import ResultItem
from .settings_manager import SettingsManager


class CancelledError(Exception):
    """Raised to abort a compression when the batch is cancelled."""


class Command(NamedTuple):
    argv: list[str]
    stdout_path: str | None = None
    ignore_errors: bool = False


def tokens(template: Template) -> list[str]:
    """Flatten a t-string into argv tokens for a tool invocation.

    Static text is split on whitespace so flag/value boundaries fall out
    naturally, while each interpolation becomes a single token so values that
    contain spaces remain one argument.
    """
    result: list[str] = []
    for part in template:
        if isinstance(part, Interpolation):
            result.append(str(part.value))
        else:
            result.extend(part.split())
    return result


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
            self._processes.append(process)

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


class Compressor(ABC):
    def __init__(self, settings: SettingsManager) -> None:
        super().__init__()
        self.settings: SettingsManager = settings
        self._output_writer: OutputWriter = OutputWriter(settings)

    @classmethod
    @abstractmethod
    def get_file_type(cls) -> str: ...

    @abstractmethod
    def build_command(self, result_item: ResultItem) -> list[Command]: ...

    def adapt_command(self, argv: list[str], _result_item: ResultItem) -> list[str]:
        return argv

    def get_intermediate_files(self, _result_item: ResultItem) -> list[str]:
        return []

    def _png_intermediate_path(self, result_item: ResultItem) -> str:
        return result_item.tmp_filename + ".png"

    @staticmethod
    def _remove_quietly(path: str) -> None:
        try:
            os.remove(path)
        except OSError:
            pass

    def _run_command(
        self, argv: list[str], context: CompressionContext, stdout: int | IO[bytes] | None
    ) -> None:
        """Run one tool invocation as a killable subprocess."""
        process = subprocess.Popen(argv, stdout=stdout, stderr=subprocess.PIPE)
        context.register_process(process)
        try:
            try:
                stdout_data, stderr_data = process.communicate(
                    timeout=self.settings.compression_timeout
                )
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

    def _mark_cancelled(
        self, result_item: ResultItem, c_update_result_item: Callable[..., None]
    ) -> None:
        result_item.cancelled = True
        result_item.running = False
        self._cleanup_temp_files(result_item)
        c_update_result_item(result_item)

    def _cleanup_temp_files(self, result_item: ResultItem) -> None:
        for path in [result_item.tmp_filename, *self.get_intermediate_files(result_item)]:
            self._remove_quietly(path)

    def run(
        self,
        result_item: ResultItem,
        c_update_result_item: Callable[..., None],
        context: CompressionContext,
    ) -> None:
        if context.cancelled:
            self._mark_cancelled(result_item, c_update_result_item)
            return

        last_argv: list[str] | None = None
        try:
            commands = self.build_command(result_item)
            for command in commands:
                argv = self.adapt_command(command.argv, result_item)
                last_argv = argv
                try:
                    if command.stdout_path is not None:
                        # Stream stdout straight to the sidecar file instead of
                        # buffering the whole payload in memory first.
                        with open(command.stdout_path, "wb") as fp:
                            self._run_command(argv, context, stdout=fp)
                    else:
                        self._run_command(argv, context, stdout=subprocess.PIPE)
                except CancelledError:
                    raise
                except Exception:
                    if command.stdout_path is not None:
                        self._remove_quietly(command.stdout_path)
                    if command.ignore_errors:
                        logger.warning("Optional command failed, ignoring: %s", argv)
                        continue
                    raise
        except CancelledError:
            self._mark_cancelled(result_item, c_update_result_item)
            return
        except subprocess.TimeoutExpired as err:
            logger.error(str(err))
            result_item.set_error(
                _("Compression has reached the configured timeout of %s seconds.")
                % self.settings.compression_timeout
            )
        except subprocess.CalledProcessError as err:
            details = str(err)
            err_stderr = cast("str | bytes | None", err.stderr)
            err_stdout = cast("str | bytes | None", err.stdout)
            tool_output = err_stderr if err_stderr else err_stdout
            if tool_output:
                if isinstance(tool_output, str):
                    decoded_output = tool_output.strip()
                else:
                    decoded_output = tool_output.decode(errors="replace").strip()
                details += "\n" + decoded_output
            result_item.set_error(_("Compression failed."), html.escape(details))
            logger.error(result_item.error_details_message)
        except OSError as err:
            result_item.set_error(_("An error has occurred."), html.escape(str(err)))
            logger.error(result_item.error_details_message)
        except Exception as err:
            result_item.set_error(_("An unknown error has occurred."), html.escape(str(err)))
            logger.error(result_item.error_details_message)

        if context.cancelled or result_item.error:
            self._cleanup_temp_files(result_item)
            c_update_result_item(result_item)
            return

        try:
            self._output_writer.finalize(result_item)
        except FileNotFoundError:
            logger.error("Command produced no output file: %s", last_argv)
            result_item.set_error(_("Can't find the compressed file"))

        self._cleanup_temp_files(result_item)

        c_update_result_item(result_item)
