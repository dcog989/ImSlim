"""Clipboard intake: turn pasted files or an image into paths to compress."""

import logging
import os
import time

from PySide6.QtCore import QMimeData, QObject, QStandardPaths, QTimer, Signal
from PySide6.QtGui import QClipboard, QImage

from ._i18n import _

logger = logging.getLogger(__name__)

# Wayland hands image data over asynchronously, so the first reads can come
# back empty; retry on the UI thread for about a second.
_IMAGE_READ_ATTEMPTS = 20
_IMAGE_READ_RETRY_MS = 50

# Pasted images live here so the default "next to original" destination is a
# real, discoverable folder instead of a temp dir a reboot wipes.
_PASTE_FOLDER_NAME = "ImSlim"


def urls_to_paths(mime: QMimeData) -> list[str]:
    paths: list[str] = []
    if mime.hasUrls():
        for url in mime.urls():
            local = url.toLocalFile()
            if local:
                paths.append(local)
    return paths


class ClipboardIntake(QObject):
    """Reads a paste request and reports local paths to compress.

    URLs are delivered as-is. A bare image is written into the user's Pictures
    folder so the compressed result has a stable home.
    """

    paths_ready: Signal = Signal(list)
    paste_failed: Signal = Signal(str)

    def __init__(self, clipboard: QClipboard, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._clipboard: QClipboard = clipboard
        # Incremented per request so a stale retry chain cannot report a
        # failure (or save a duplicate) after a newer paste started.
        self._request_token: int = 0

    def request(self) -> None:
        self._request_token += 1
        paths = urls_to_paths(self._clipboard.mimeData())
        if paths:
            self.paths_ready.emit(paths)
            return
        self._read_image(attempts=0, token=self._request_token)

    def _read_image(self, attempts: int, token: int) -> None:
        if token != self._request_token:
            return
        image = self._clipboard.image()
        if not image.isNull():
            self._handle_image(image)
            return
        if attempts >= _IMAGE_READ_ATTEMPTS:
            self.paste_failed.emit(_("No image or file on the clipboard."))
            return
        QTimer.singleShot(_IMAGE_READ_RETRY_MS, lambda: self._read_image(attempts + 1, token))

    def _handle_image(self, image: QImage) -> None:
        try:
            path = self._save_image(image)
        except OSError as err:
            logger.warning("Could not save the pasted image: %s", err)
            path = None
        if path:
            self.paths_ready.emit([path])
        else:
            self.paste_failed.emit(_("Could not save the pasted image."))

    def _save_image(self, image: QImage) -> str | None:
        directory = self._paste_directory()
        path = os.path.join(directory, f"pasted-{time.time_ns()}.png")
        # PySide6's stub types `format` as bytes, but the runtime requires str.
        if image.save(path, "PNG"):  # pyright: ignore[reportCallIssue, reportArgumentType]
            return path
        return None

    @staticmethod
    def _paste_directory() -> str:
        pictures = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.PicturesLocation)
        directory = os.path.join(pictures or os.path.expanduser("~"), _PASTE_FOLDER_NAME)
        os.makedirs(directory, exist_ok=True)
        return directory
