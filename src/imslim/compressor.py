import html
import logging
import os
import shutil
import subprocess
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import NamedTuple

from .result_item import ResultItem
from .settings_manager import SAVE_BACKUP_OVERWRITE


class Command(NamedTuple):
    argv: list[str]
    stdout_path: str | None = None
    ignore_errors: bool = False


class Compressor(ABC):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings

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

    def _cleanup_temp_files(self, result_item: ResultItem) -> None:
        for path in [result_item.tmp_filename, *self.get_intermediate_files(result_item)]:
            self._remove_quietly(path)

    def run(self, result_item: ResultItem, c_update_result_item: Callable) -> None:
        commands = self.build_command(result_item)
        last_argv: list[str] | None = None
        try:
            for command in commands:
                argv = self.adapt_command(command.argv, result_item)
                last_argv = argv
                try:
                    if command.stdout_path is not None:
                        # Stream stdout straight to the sidecar file instead of
                        # buffering the whole payload in memory first.
                        with open(command.stdout_path, "wb") as fp:
                            subprocess.run(
                                argv,
                                stdout=fp,
                                stderr=subprocess.PIPE,
                                check=True,
                                timeout=self.settings.compression_timeout,
                            )
                    else:
                        subprocess.run(
                            argv,
                            capture_output=True,
                            check=True,
                            timeout=self.settings.compression_timeout,
                        )
                except Exception:
                    if command.stdout_path is not None:
                        self._remove_quietly(command.stdout_path)
                    if command.ignore_errors:
                        logging.warning("Optional command failed, ignoring: %s", argv)
                        continue
                    raise
        except subprocess.TimeoutExpired as err:
            logging.error(str(err))
            result_item.error_message = (
                _("Compression has reached the configured timeout of %s seconds.")
                % self.settings.compression_timeout
            )
            result_item.error = True
        except Exception as err:
            details = str(err)
            if isinstance(err, subprocess.CalledProcessError):
                tool_output = err.stderr if err.stderr else err.stdout
                if tool_output:
                    details += "\n" + tool_output.decode(errors="replace").strip()
            result_item.set_error(_("An unknown error has occurred."), html.escape(details))
            logging.error(result_item.error_details_message)

        if result_item.error:
            self._cleanup_temp_files(result_item)
            c_update_result_item(result_item)
            return

        if os.path.exists(result_item.tmp_filename):
            result_item.new_size = os.path.getsize(result_item.tmp_filename)

            if result_item.new_size >= result_item.size:
                # Output is larger (or equal) than input
                # Don't use compressed temp file
                result_item.skipped = True
            else:
                # Output is smaller than input; copy the compressed temp file
                overwriting = (
                    self.settings.save_method == SAVE_BACKUP_OVERWRITE
                    and result_item.filename == result_item.new_filename
                )
                if overwriting:
                    try:
                        shutil.copy2(result_item.filename, result_item.backup_filename)
                    except OSError as err:
                        result_item.set_error(
                            _("Can't backup the original file"), html.escape(str(err))
                        )
                        logging.error(result_item.error_details_message)

                if not result_item.error:
                    final_path = result_item.filename if overwriting else result_item.new_filename
                    shutil.copy2(result_item.tmp_filename, final_path)
                    if self.settings.file_attributes and (
                        result_item.atime > 0 and result_item.mtime > 0
                    ):
                        try:
                            os.utime(final_path, (result_item.atime, result_item.mtime))
                        except OSError:
                            pass

            # Remove the temp file
            self._remove_quietly(result_item.tmp_filename)
        else:
            logging.error("Command produced no output file: %s", last_argv)
            result_item.error_message = _("Can't find the compressed file")
            result_item.error = True

        self._cleanup_temp_files(result_item)

        c_update_result_item(result_item)
