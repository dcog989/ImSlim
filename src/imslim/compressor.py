import html
import logging
import os
import shutil
import subprocess
from abc import ABC, abstractmethod
from collections.abc import Callable

from .result_item import ResultItem
from .settings_manager import SAVE_BACKUP_OVERWRITE


class Compressor(ABC):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings

    @classmethod
    @abstractmethod
    def get_file_type(cls) -> str:
        return ""

    @abstractmethod
    def build_command(
        self, result_item: ResultItem
    ) -> list[tuple[list[str], str | None] | tuple[list[str], str | None, bool]]:
        return []

    def adapt_command(self, argv: list[str], result_item: ResultItem) -> list[str]:
        return argv

    def get_intermediate_files(self, result_item: ResultItem) -> list[str]:
        return []

    def run(self, result_item: ResultItem, c_update_result_item: Callable) -> None:
        commands = self.build_command(result_item)
        output = None
        try:
            # Each command is a (argv, stdout_path) tuple; an optional third
            # element (True) marks the command as non-fatal: on failure it is
            # logged and skipped instead of failing the whole item.
            for command in commands:
                argv, stdout_path = command[0], command[1]
                ignore_errors = command[2] if len(command) > 2 else False
                argv = self.adapt_command(argv, result_item)
                try:
                    output = subprocess.run(
                        argv,
                        capture_output=True,
                        check=True,
                        timeout=self.settings.compression_timeout,
                    )
                    if stdout_path is not None:
                        with open(stdout_path, "wb") as fp:
                            fp.write(output.stdout)
                except Exception:
                    if ignore_errors:
                        logging.warning("Optional command failed, ignoring: %s", argv)
                        continue
                    raise
        except subprocess.TimeoutExpired as err:
            logging.error(str(err))
            result_item.error_message = _(
                f"Compression has reached the configured timeout of {self.settings.compression_timeout} seconds."
            )
            result_item.error = True
        except Exception as err:
            result_item.error_message = _("An unknown error has occurred.")
            result_item.error_details_message = html.escape(str(err))
            logging.error(result_item.error_details_message)
            result_item.error = True
            result_item.error_details = True

        if result_item.error:
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
                if self.settings.save_method == SAVE_BACKUP_OVERWRITE:
                    try:
                        shutil.copy2(result_item.filename, result_item.backup_filename)
                    except OSError as err:
                        result_item.error = True
                        result_item.error_message = _("Can't backup the original file")
                        result_item.error_details_message = html.escape(str(err))
                        result_item.error_details = True
                        logging.error(result_item.error_details_message)

                if not result_item.error:
                    final_path = (
                        result_item.filename
                        if self.settings.save_method == SAVE_BACKUP_OVERWRITE
                        else result_item.new_filename
                    )
                    shutil.copy2(result_item.tmp_filename, final_path)
                    if self.settings.file_attributes and (
                        result_item.atime > 0 and result_item.mtime > 0
                    ):
                        try:
                            os.utime(final_path, (result_item.atime, result_item.mtime))
                        except OSError:
                            pass

            # Remove the temp file
            try:
                os.remove(result_item.tmp_filename)
            except OSError:
                pass
        else:
            logging.error(str(output))
            result_item.error_message = _("Can't find the compressed file")
            result_item.error = True

        for path in self.get_intermediate_files(result_item):
            try:
                os.remove(path)
            except OSError:
                pass

        c_update_result_item(result_item)
