import logging
import os
import re
import time
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QMimeDatabase

from ._i18n import _
from .batch_options import BatchOptions
from .formats import ALLOWED_MIME_TYPES, OUTPUT_EXTENSIONS, TARGET_EXTENSIONS, is_converting
from .image_utils import is_animated_image
from .result_item import ResultItem, ResultState
from .settings_manager import SAVE_BACKUP_OVERWRITE, SAVE_OUTPUT_FOLDER

logger = logging.getLogger(__name__)

_mime_db = QMimeDatabase()

_OUTPUT_MARKER = "imslim"
_BACKUP_MARKER = "BAK"
_TIMESTAMP_FORMAT = "%Y%m%d%H%M%S"

# Files this app wrote: <stem>.<marker>.<timestamp>[-<n>].<ext>. They keep the
# source image extension, so a rescan of a folder would pick them up as inputs.
_GENERATED_OUTPUT_PATTERN = re.compile(
    rf"\.(?:{_OUTPUT_MARKER}|{_BACKUP_MARKER})\.\d{{14}}(?:-\d+)?\.[^.]+$",
    re.IGNORECASE,
)
# With the timestamp directory enabled, outputs keep plain names inside a
# directory named after the batch; the directory is what marks them as generated.
_GENERATED_DIR_PATTERN = re.compile(rf"^{_OUTPUT_MARKER}-\d{{14}}$", re.IGNORECASE)


def is_generated_output(path: str) -> bool:
    """True when `path` is an output or backup this app created."""
    if any(_GENERATED_DIR_PATTERN.match(part) for part in Path(path).parts):
        return True
    return _GENERATED_OUTPUT_PATTERN.search(os.path.basename(path)) is not None


class ResultItemManager:
    def __init__(self, options: BatchOptions) -> None:
        self.options: BatchOptions = options
        self._used_names: set[str] = set()
        self._timestamp_dirs: set[str] = set()
        self._batch_timestamp: str = time.strftime(_TIMESTAMP_FORMAT)

    def begin_batch(self) -> bool:
        """Start a new batch: reset name reservations and prepare the output folder.

        Returns False if the output folder cannot be created and the batch
        should be aborted.
        """
        self._used_names.clear()
        self._timestamp_dirs.clear()
        self._batch_timestamp = time.strftime(_TIMESTAMP_FORMAT)
        if self.options.save_method == SAVE_OUTPUT_FOLDER and self.options.output_folder:
            try:
                os.makedirs(self.options.output_folder, exist_ok=True)
            except OSError:
                return False
        return True

    def build(self, path: str) -> ResultItem:
        """Read one source's metadata; output names are assigned at batch start."""
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

        # Sniffed once and carried on the item: the GIF compressor needs it to
        # pick lossy vs lossless, and a conversion that would drop the animation
        # warns here. Other formats answer without touching the file.
        if mime == "image/gif" or is_converting(self.options.target_format):
            result_item.is_animated = is_animated_image(path, mime)

        result_item.warning_message = self._animation_warning(result_item)
        return result_item

    def prepare(self, result_item: ResultItem) -> None:
        """Assign output names and reset the outcome for a new batch.

        Runs at Process time so an output name always matches the format and
        destination in effect when the batch starts. Items that failed analysis
        keep their error and are not prepared.
        """
        if not result_item.filename or result_item.mime_type not in ALLOWED_MIME_TYPES:
            return
        result_item.state = ResultState.IDLE
        result_item.new_size = 0
        result_item.error_message = ""
        result_item.error_details_message = ""
        result_item.warning_message = self._animation_warning(result_item)
        result_item.new_filename = self.create_new_filename(
            result_item.filename, result_item.mime_type
        )
        result_item.backup_filename = (
            self.create_backup_filename(result_item.filename, result_item.mime_type)
            if self.options.save_method == SAVE_BACKUP_OVERWRITE
            and result_item.new_filename == result_item.filename
            else ""
        )
        # Random token: a predictable name in a shared folder could be a
        # symlink another user pre-created for the encoders to write through.
        output_dir = os.path.dirname(result_item.new_filename)
        result_item.tmp_filename = os.path.join(
            output_dir, f".{os.path.basename(result_item.new_filename)}.{uuid4().hex[:8]}.tmp"
        )

    def create_new_filename(self, path: str, mime: str, *, create_dir: bool = True) -> str:
        """The output path for `path`; `create_dir` false only predicts it."""
        # None keeps the source extension; only re-encoded formats swap it.
        extension = (
            TARGET_EXTENSIONS[self.options.target_format]
            if is_converting(self.options.target_format)
            else OUTPUT_EXTENSIONS.get(mime)
        )
        # Overwriting in place keeps the original name (only the extension can
        # change); every other destination gets the marker so nothing clashes.
        overwrite = self.options.save_method == SAVE_BACKUP_OVERWRITE
        return self._output_path(
            path,
            _OUTPUT_MARKER,
            mime,
            extension,
            create_dir=create_dir,
            keep_stem=overwrite,
            allow_source=overwrite,
        )

    def create_backup_filename(self, path: str, mime: str) -> str:
        return self._output_path(path, _BACKUP_MARKER, mime)

    def _animation_warning(self, result_item: ResultItem) -> str:
        if result_item.is_animated and is_converting(self.options.target_format):
            return _("Animation will be lost: only the first frame is kept.")
        return ""

    def _uses_timestamp_dir(self) -> bool:
        # Overwriting in place has no destination folder to put a directory in.
        return self.options.timestamp_dir and self.options.save_method != SAVE_BACKUP_OVERWRITE

    def _output_parent(self, path: str, *, create_dir: bool = True) -> str:
        parent = (
            self.options.output_folder
            if self.options.save_method == SAVE_OUTPUT_FOLDER and self.options.output_folder
            else os.path.dirname(path)
        )
        if not self._uses_timestamp_dir():
            return parent
        stamp_dir = os.path.join(parent, f"{_OUTPUT_MARKER}-{self._batch_timestamp}")
        if create_dir and stamp_dir not in self._timestamp_dirs:
            try:
                os.makedirs(stamp_dir, exist_ok=True)
            except OSError as err:
                # The write itself reports the failure; the batch keeps going.
                logger.warning("Could not create %s: %s", stamp_dir, err)
            self._timestamp_dirs.add(stamp_dir)
        return stamp_dir

    def _output_path(
        self,
        path: str,
        marker: str,
        mime: str,
        extension_override: str | None = None,
        *,
        create_dir: bool = True,
        keep_stem: bool = False,
        allow_source: bool = False,
    ) -> str:
        basename = os.path.basename(path)
        stem, extension = os.path.splitext(basename)
        extension = (
            extension_override
            if extension_override is not None
            else OUTPUT_EXTENSIONS.get(mime, extension)
        )
        parent = self._output_parent(path, create_dir=create_dir)
        if keep_stem or self._uses_timestamp_dir():
            base = os.path.join(parent, stem)
        else:
            base = os.path.join(parent, f"{stem}.{marker}.{self._batch_timestamp}")
        counter = 0
        while True:
            suffix = "" if counter == 0 else f"-{counter}"
            candidate = f"{base}{suffix}{extension}"
            # Overwriting in place may reuse the source's own path; any other
            # existing file still wins the name so unrelated files survive.
            if (allow_source and candidate == path) or (
                not os.path.exists(candidate) and candidate not in self._used_names
            ):
                self._used_names.add(candidate)
                return candidate
            counter += 1
