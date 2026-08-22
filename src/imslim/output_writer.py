import html
import logging
import os
import shutil

from ._i18n import _
from .result_item import ResultItem
from .settings_manager import SAVE_BACKUP_OVERWRITE, SettingsManager


class OutputWriter:
    """Move a compressed temp file into place, handling backups and attributes."""

    def __init__(self, settings: SettingsManager) -> None:
        self.settings: SettingsManager = settings

    def finalize(self, result_item: ResultItem) -> None:
        """Copy the compressed temp file to its destination and restore file
        attributes. Marks the item skipped/error as appropriate."""
        if not os.path.exists(result_item.tmp_filename):
            raise FileNotFoundError(f"Missing compressed output: {result_item.tmp_filename}")

        result_item.new_size = os.path.getsize(result_item.tmp_filename)

        if result_item.new_size >= result_item.size:
            # Output is larger (or equal) than input; keep the original.
            result_item.skipped = True
            return

        overwriting = (
            self.settings.save_method == SAVE_BACKUP_OVERWRITE
            and result_item.filename == result_item.new_filename
        )
        if overwriting:
            try:
                _res = shutil.copy2(result_item.filename, result_item.backup_filename)
            except OSError as err:
                result_item.set_error(_("Can't backup the original file"), html.escape(str(err)))
                logging.error(result_item.error_details_message)
                return

        final_path = result_item.filename if overwriting else result_item.new_filename
        try:
            _res = shutil.copy2(result_item.tmp_filename, final_path)
        except OSError as err:
            result_item.set_error(_("Can't write the compressed file"), html.escape(str(err)))
            logging.error(result_item.error_details_message)
            return

        self._restore_attributes(result_item, final_path)

    def _restore_attributes(self, result_item: ResultItem, final_path: str) -> None:
        if self.settings.file_attributes and result_item.atime > 0 and result_item.mtime > 0:
            try:
                os.utime(final_path, (result_item.atime, result_item.mtime))
            except OSError:
                pass
