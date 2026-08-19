import html
import logging
import os
import subprocess
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import NamedTuple

from .output_writer import OutputWriter
from .result_item import ResultItem


class CancelledError(Exception):
    """Raised to abort a compression when the batch is cancelled."""


class Command(NamedTuple):
    argv: list[str]
    stdout_path: str | None = None
    ignore_errors: bool = False


class Compressor(ABC):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self._output_writer = OutputWriter(settings)

    @classmethod
    @abstractmethod
    def get_file_type(cls) -> str: ...

    @abstractmethod
    def build_command(self, result_item: ResultItem) -> list[Command]: ...

    def adapt_command(self, argv: list[str], result_item: ResultItem) -> list[str]:
        return argv

    def get_intermediate_files(self, result_item: ResultItem) -> list[str]:
        return []

    def _png_intermediate_path(self, result_item: ResultItem) -> str:
        return result_item.tmp_filename + ".png"

    @staticmethod
    def _remove_quietly(path: str) -> None:
        try:
            os.remove(path)
        except OSError:
            pass

    def _run_command(self, argv: list[str], context, stdout) -> None:
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
                process.communicate()
                raise
        finally:
            context.unregister_process(process)
        if context.cancelled:
            raise CancelledError
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, argv, stdout_data, stderr_data)

    def _mark_cancelled(self, result_item: ResultItem, c_update_result_item: Callable) -> None:
        result_item.cancelled = True
        result_item.running = False
        self._cleanup_temp_files(result_item)
        c_update_result_item(result_item)

    def _cleanup_temp_files(self, result_item: ResultItem) -> None:
        for path in [result_item.tmp_filename, *self.get_intermediate_files(result_item)]:
            self._remove_quietly(path)

    def run(self, result_item: ResultItem, c_update_result_item: Callable, context) -> None:
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
                        logging.warning("Optional command failed, ignoring: %s", argv)
                        continue
                    raise
        except CancelledError:
            self._mark_cancelled(result_item, c_update_result_item)
            return
        except subprocess.TimeoutExpired as err:
            logging.error(str(err))
            result_item.set_error(
                _("Compression has reached the configured timeout of %s seconds.")
                % self.settings.compression_timeout
            )
        except subprocess.CalledProcessError as err:
            details = str(err)
            tool_output = err.stderr if err.stderr else err.stdout
            if tool_output:
                details += "\n" + tool_output.decode(errors="replace").strip()
            result_item.set_error(_("Compression failed."), html.escape(details))
            logging.error(result_item.error_details_message)
        except OSError as err:
            result_item.set_error(_("An error has occurred."), html.escape(str(err)))
            logging.error(result_item.error_details_message)
        except Exception as err:
            result_item.set_error(_("An unknown error has occurred."), html.escape(str(err)))
            logging.error(result_item.error_details_message)

        if context.cancelled or result_item.error:
            self._cleanup_temp_files(result_item)
            c_update_result_item(result_item)
            return

        try:
            self._output_writer.finalize(result_item)
        except FileNotFoundError:
            logging.error("Command produced no output file: %s", last_argv)
            result_item.set_error(_("Can't find the compressed file"))

        self._cleanup_temp_files(result_item)

        c_update_result_item(result_item)
