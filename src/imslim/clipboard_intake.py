"""Clipboard intake: turn pasted files or an image into paths to compress."""

import os
import shutil
import tempfile
import time

from PySide6.QtCore import QMimeData, QObject, QTimer, Signal
from PySide6.QtGui import QClipboard, QImage


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

    URLs are delivered as-is. A bare image is written into a private temp dir
    (removed on `cleanup`) before being reported.
    """

    paths_ready: Signal = Signal(list)

    def __init__(self, clipboard: QClipboard, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._clipboard: QClipboard = clipboard
        self._paste_temp_dir: str | None = None

    def request(self) -> None:
        paths = urls_to_paths(self._clipboard.mimeData())
        if paths:
            self.paths_ready.emit(paths)
            return
        self._read_image(attempts=0)

    def cleanup(self) -> None:
        directory = self._paste_temp_dir
        self._paste_temp_dir = None
        if directory is not None:
            shutil.rmtree(directory, ignore_errors=True)

    def _read_image(self, attempts: int) -> None:
        # On Wayland, image data is transferred asynchronously from the
        # clipboard owner, so the first read may come back empty. Retry on a
        # QTimer instead of sleeping in a loop so the UI thread stays responsive.
        image = self._clipboard.image()
        if not image.isNull():
            self._handle_image(image)
            return
        if attempts >= 20:
            return
        QTimer.singleShot(50, lambda: self._read_image(attempts + 1))

    def _handle_image(self, image: QImage) -> None:
        path = self._save_image(image)
        if path:
            self.paths_ready.emit([path])

    def _save_image(self, image: QImage) -> str | None:
        # Paste sources and their compressed output live in a private (0700)
        # temp dir so nothing predictable is written to shared /tmp; the dir is
        # removed on clear/close.
        directory = self._paste_directory()
        path = os.path.join(directory, f"pasted-{time.time_ns()}.png")
        # PySide6's stub types `format` as bytes, but the runtime requires str.
        if image.save(path, "PNG"):  # pyright: ignore[reportCallIssue, reportArgumentType]
            return path
        return None

    def _paste_directory(self) -> str:
        if self._paste_temp_dir is None:
            self._paste_temp_dir = tempfile.mkdtemp(prefix="imslim-pasted-")
        return self._paste_temp_dir
