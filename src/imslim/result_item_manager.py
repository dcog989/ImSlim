import os
import re
import time

from PySide6.QtCore import QMimeDatabase

from ._i18n import _
from .batch_options import BatchOptions
from .conversion import is_converting
from .formats import ALLOWED_MIME_TYPES, OUTPUT_EXTENSIONS, TARGET_EXTENSIONS
from .image_utils import is_animated_image
from .result_item import ResultItem
from .settings_manager import SAVE_BACKUP_OVERWRITE, SAVE_OUTPUT_FOLDER

_mime_db = QMimeDatabase()

_OUTPUT_MARKER = "imslim"
_BACKUP_MARKER = "BAK"

# Files this app wrote: <stem>.<marker>.<timestamp>[-<n>].<ext>. They keep the
# source image extension, so a rescan of a folder would pick them up as inputs.
_GENERATED_OUTPUT_PATTERN = re.compile(
    rf"\.(?:{_OUTPUT_MARKER}|{_BACKUP_MARKER})\.\d{{14}}(?:-\d+)?\.[^.]+$",
    re.IGNORECASE,
)


def is_generated_output(path: str) -> bool:
    """True when `path` is an output or backup this app created."""
    return _GENERATED_OUTPUT_PATTERN.search(os.path.basename(path)) is not None


class ResultItemManager:
    def __init__(self, options: BatchOptions) -> None:
        self.options: BatchOptions = options
        self._used_names: set[str] = set()

    def begin_batch(self) -> bool:
        """Start a new batch: reset name reservations and prepare the output folder.

        Returns False if the output folder cannot be created and the batch
        should be aborted.
        """
        self._used_names.clear()
        if self.options.save_method == SAVE_OUTPUT_FOLDER and self.options.output_folder:
            try:
                os.makedirs(self.options.output_folder, exist_ok=True)
            except OSError:
                return False
        return True

    def build(self, path: str) -> ResultItem:
        result_item = ResultItem()
        result_item.filename = path

        try:
            stat = os.stat(path)
        except OSError:
            result_item.set_error(_("This file doesn't exist."))
            return result_item

        result_item.atime = float(stat.st_atime)
        result_item.mtime = float(stat.st_mtime)
        result_item.mode = stat.st_mode
        result_item.size = stat.st_size

        mime = _mime_db.mimeTypeForFile(path).name()
        result_item.mime_type = mime
        if mime not in ALLOWED_MIME_TYPES or result_item.size <= 0:
            result_item.set_error(_("Format of this file is not supported."))
            return result_item

        if is_converting(self.options.target_format) and is_animated_image(path, mime):
            result_item.warning_message = _("Animation will be lost: only the first frame is kept.")

        result_item.new_filename = self.create_new_filename(result_item.filename, mime)
        result_item.backup_filename = (
            self.create_backup_filename(result_item.filename, mime)
            if self.options.save_method == SAVE_BACKUP_OVERWRITE
            and not is_converting(self.options.target_format)
            else ""
        )

        output_dir = os.path.dirname(result_item.new_filename)
        result_item.tmp_filename = os.path.join(
            output_dir, f".{os.path.basename(result_item.new_filename)}.tmp"
        )

        return result_item

    def create_new_filename(self, path: str, mime: str) -> str:
        if is_converting(self.options.target_format):
            # Conversion always writes a new file in the target's format; it
            # must never overwrite a source that may have a different extension.
            return self._output_path(
                path, _OUTPUT_MARKER, mime, TARGET_EXTENSIONS[self.options.target_format]
            )
        if self.options.save_method == SAVE_BACKUP_OVERWRITE and mime not in OUTPUT_EXTENSIONS:
            return path
        return self._output_path(path, _OUTPUT_MARKER, mime)

    def create_backup_filename(self, path: str, mime: str) -> str:
        return self._output_path(path, _BACKUP_MARKER, mime)

    def _output_parent(self, path: str) -> str:
        if self.options.save_method == SAVE_OUTPUT_FOLDER and self.options.output_folder:
            return self.options.output_folder
        return os.path.dirname(path)

    def _output_path(
        self, path: str, marker: str, mime: str, extension_override: str | None = None
    ) -> str:
        basename = os.path.basename(path)
        stem, extension = os.path.splitext(basename)
        extension = (
            extension_override
            if extension_override is not None
            else OUTPUT_EXTENSIONS.get(mime, extension)
        )
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
