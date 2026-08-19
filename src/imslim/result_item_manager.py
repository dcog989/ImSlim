import os

from PySide6.QtCore import QMimeDatabase

from .result_item import ResultItem
from .tools import sizeof_fmt

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/avif",
    "image/gif",
    "image/svg+xml",
}

_mime_db = QMimeDatabase()


class ResultItemManager:
    def __init__(self, settings_manager):
        self.settings = settings_manager

    def build(self, path: str) -> ResultItem:
        result_item = ResultItem()

        if not os.path.exists(path):
            result_item.set_error(_("This file doesn't exist."))
            return result_item

        try:
            stat = os.stat(path)
        except OSError:
            result_item.set_error(_("This file doesn't exist."))
            return result_item

        result_item.filename = path
        result_item.atime = float(stat.st_atime)
        result_item.mtime = float(stat.st_mtime)
        result_item.name = os.path.basename(path)
        result_item.size = stat.st_size

        mime = _mime_db.mimeTypeForFile(path).name()
        result_item.mime_type = mime
        if mime not in ALLOWED_MIME_TYPES or result_item.size <= 0:
            result_item.set_error(_("Format of this file is not supported."))
            return result_item

        result_item.subtitle_label = sizeof_fmt(result_item.size)

        result_item.new_filename = self.create_new_filename(result_item.filename)
        result_item.backup_filename = self.create_backup_filename(result_item.filename)

        base_dir, fname = os.path.split(result_item.new_filename)
        result_item.tmp_filename = os.path.join(base_dir, f".{fname}.tmp")

        return result_item

    def create_new_filename(self, path):
        new_filename = path
        basename = os.path.basename(path)
        splitext = os.path.splitext(basename)
        parent = path.replace(basename, "")
        stem = splitext[0]
        extension = splitext[1]
        suffix_prefix = self.settings.suffix_prefix

        if self.settings.new_file and not self.settings.backup:
            if self.settings.naming_mode == 0:  # Suffix selected
                new_filename = f"{parent}/{stem}{suffix_prefix}{extension}"
            else:  # Prefix selected
                new_filename = f"{parent}/{suffix_prefix}{stem}{extension}"

        return new_filename

    def create_backup_filename(self, path):
        basename = os.path.basename(path)
        splitext = os.path.splitext(basename)
        parent = path.replace(basename, "")
        return f"{parent}/{splitext[0]}.bak{splitext[1]}"
