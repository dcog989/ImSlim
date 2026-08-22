import os
import time
from typing import Protocol

from PySide6.QtCore import QMimeDatabase

from ._i18n import _
from .compression_manager import ALLOWED_MIME_TYPES, OUTPUT_EXTENSIONS
from .result_item import ResultItem
from .settings_manager import SAVE_BACKUP_OVERWRITE
from .tools import sizeof_fmt

_mime_db = QMimeDatabase()


class BuildSettings(Protocol):
    """Settings surface ResultItemManager reads while building items.

    Satisfied by SettingsManager on the main thread and by the lightweight
    snapshot passed to a background worker, so QSettings is never touched
    from a non-UI thread.
    """

    save_method: int
    output_folder: str


class ResultItemManager:
    def __init__(self, settings_manager: BuildSettings) -> None:
        self.settings: BuildSettings = settings_manager
        self._used_names: set[str] = set()

    def begin_batch(self) -> bool:
        """Start a new batch: reset name reservations and prepare the output folder.

        Returns False if the output folder cannot be created and the batch
        should be aborted.
        """
        self._used_names.clear()
        if self.settings.output_folder:
            try:
                os.makedirs(self.settings.output_folder, exist_ok=True)
            except OSError:
                return False
        return True

    def build(self, path: str) -> ResultItem:
        result_item = ResultItem()

        try:
            stat = os.stat(path)
        except OSError:
            result_item.set_error(_("This file doesn't exist."))
            return result_item

        result_item.filename = path
        result_item.atime = float(stat.st_atime)
        result_item.mtime = float(stat.st_mtime)
        result_item.size = stat.st_size

        mime = _mime_db.mimeTypeForFile(path).name()
        result_item.mime_type = mime
        if mime not in ALLOWED_MIME_TYPES or result_item.size <= 0:
            result_item.set_error(_("Format of this file is not supported."))
            return result_item

        result_item.subtitle_label = sizeof_fmt(result_item.size)

        result_item.new_filename = self.create_new_filename(result_item.filename, mime)
        result_item.backup_filename = (
            self.create_backup_filename(result_item.filename, mime)
            if self.settings.save_method == SAVE_BACKUP_OVERWRITE
            else ""
        )

        output_dir = os.path.dirname(result_item.new_filename)
        result_item.tmp_filename = os.path.join(
            output_dir, f".{os.path.basename(result_item.new_filename)}.tmp"
        )

        return result_item

    def create_new_filename(self, path: str, mime: str) -> str:
        if self.settings.save_method == SAVE_BACKUP_OVERWRITE and mime not in OUTPUT_EXTENSIONS:
            return path
        return self._output_path(path, "imslim", mime)

    def create_backup_filename(self, path: str, mime: str) -> str:
        return self._output_path(path, "BAK", mime)

    def _output_parent(self, path: str) -> str:
        if self.settings.output_folder:
            return self.settings.output_folder
        return os.path.dirname(path)

    def _output_path(self, path: str, marker: str, mime: str) -> str:
        basename = os.path.basename(path)
        stem, extension = os.path.splitext(basename)
        extension = OUTPUT_EXTENSIONS.get(mime, extension)
        timestamp = time.strftime("%Y%m%d%H%M%S")
        parent = self._output_parent(path)
        base = os.path.join(parent, f"{stem}.{marker}.{timestamp}")
        counter = 0
        while True:
            suffix = "" if counter == 0 else f"-{counter}"
            candidate = f"{base}{suffix}{extension}"
            if not os.path.exists(candidate) and candidate not in self._used_names:
                self._used_names.add(candidate)
                return candidate
            counter += 1
