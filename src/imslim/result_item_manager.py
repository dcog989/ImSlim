import logging
import os
import re
import time
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QMimeDatabase

from ._i18n import _
from .batch_options import BatchOptions
from .formats import (
    ALLOWED_MIME_TYPES,
    OUTPUT_EXTENSIONS,
    TARGET_EXTENSIONS,
    Format,
    is_converting,
    is_format_change,
)
from .image_utils import ANIMATED_MIME_TYPES, is_animated_image
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
    rf"\.(?:{_OUTPUT_MARKER}|{_BACKUP_MARKER})\.\d{{14}}(?:-\d+)*\.[^.]+$",
    re.IGNORECASE,
)
# With the timestamp directory enabled, outputs keep plain names inside a
# directory named after the batch; the directory is what marks them as generated.
_GENERATED_DIR_PATTERN = re.compile(rf"^{_OUTPUT_MARKER}-\d{{14}}(?:-\d+)?$", re.IGNORECASE)


def is_generated_output(path: str) -> bool:
    """True when `path` is an output or backup this app created."""
    if any(_GENERATED_DIR_PATTERN.match(part) for part in Path(path).parts):
        return True
    return _GENERATED_OUTPUT_PATTERN.search(os.path.basename(path)) is not None


class ResultItemManager:
    def __init__(self, options: BatchOptions) -> None:
        self.options: BatchOptions = options
        self._used_names: set[str] = set()
        self._next_counters: dict[str, int] = {}
        self._timestamp_dirs: set[str] = set()
        self._batch_timestamp: str = self._new_timestamp()

    @staticmethod
    def _new_timestamp() -> str:
        # The PID keeps two --now batches started in the same second from
        # choosing the same output and backup names.
        return f"{time.strftime(_TIMESTAMP_FORMAT)}-{os.getpid()}"

    def begin_batch(self) -> bool:
        """Start a new batch: reset name reservations and prepare the output folder.

        Returns False if the output folder is missing or cannot be created and
        the batch should be aborted.
        """
        self._used_names.clear()
        self._next_counters.clear()
        self._timestamp_dirs.clear()
        self._batch_timestamp = self._new_timestamp()
        if self.options.save_method == SAVE_OUTPUT_FOLDER:
            if not self.options.output_folder:
                return False
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

        # Sniffed once and carried on the item: the GIF/PNG/WebP compressors use
        # it to keep or warn about animation. Other formats answer without
        # touching the file.
        if mime in ANIMATED_MIME_TYPES or is_converting(self.options.target_format):
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
        # Refresh the metadata read at analysis time: the file may have changed
        # or vanished while it sat in the queue.
        try:
            stat = os.stat(result_item.filename)
        except OSError:
            result_item.set_error(_("This file doesn't exist."))
            return
        if stat.st_size <= 0:
            result_item.set_error(_("Format of this file is not supported."))
            return
        result_item.atime = float(stat.st_atime)
        result_item.mtime = float(stat.st_mtime)
        result_item.mode = stat.st_mode
        result_item.size = stat.st_size
        result_item.state = ResultState.IDLE
        result_item.new_size = 0
        result_item.new_filename = ""
        result_item.backup_filename = ""
        result_item.tmp_filename = ""
        result_item.error_message = ""
        result_item.error_details_message = ""
        result_item.warning_message = self._animation_warning(result_item)
        try:
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
                output_dir,
                f".{os.path.basename(result_item.new_filename)}.{uuid4().hex[:8]}.tmp",
            )
        except OSError as err:
            # The timestamp directory could not be created; report it per item
            # so the encoder never runs for an output that cannot be written.
            logger.warning("Could not prepare the output for %s: %s", result_item.filename, err)
            result_item.set_error(_("Can't create the output folder."), str(err))

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
        # A same-format re-encode must reuse the source file, .jpeg included:
        # otherwise the original is left behind without a backup.
        if overwrite and not is_format_change(mime, self.options.target_format):
            extension = None
        return self._output_path(
            path,
            _OUTPUT_MARKER,
            mime,
            extension,
            create_dir=create_dir,
            allow_source=overwrite,
        )

    def create_backup_filename(self, path: str, mime: str) -> str:
        return self._output_path(path, _BACKUP_MARKER, mime)

    def _animation_warning(self, result_item: ResultItem) -> str:
        if not result_item.is_animated:
            return ""
        target = self.options.target_format
        # Same-format PNG keeps its animation (the lossy step is skipped), and
        # GIF/SVG keep theirs through their own encoders.
        if result_item.mime_type == "image/png" and target in (Format.KEEP, Format.PNG):
            return ""
        if target == Format.KEEP and result_item.mime_type in ("image/gif", "image/svg+xml"):
            return ""
        if is_converting(target) or result_item.mime_type == "image/webp":
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
                # Let the caller report a per-item error instead of encoding a
                # file whose destination does not exist.
                logger.warning("Could not create %s: %s", stamp_dir, err)
                raise
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
        if allow_source or self._uses_timestamp_dir():
            base = os.path.join(parent, stem)
        else:
            base = os.path.join(parent, f"{stem}.{marker}.{self._batch_timestamp}")
        # One counter per prefix: repeated names skip straight to the next free
        # suffix instead of probing from zero for every file.
        key = f"{base}{extension}"
        counter = self._next_counters.get(key, 0)
        while True:
            suffix = "" if counter == 0 else f"-{counter}"
            candidate = f"{base}{suffix}{extension}"
            # Overwriting in place may reuse the source's own path; any other
            # existing file still wins the name so unrelated files survive.
            if (allow_source and candidate == path) or (
                not os.path.exists(candidate) and candidate not in self._used_names
            ):
                self._used_names.add(candidate)
                self._next_counters[key] = counter + 1
                return candidate
            counter += 1
