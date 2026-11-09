"""Decode an image for the comparison pane, including formats Qt cannot read."""

import logging
import os
import subprocess
import tempfile

from PySide6.QtCore import QMimeDatabase, QSize
from PySide6.QtGui import QImage, QImageReader

from .conversion import decode_commands, run_commands
from .formats import DECODER_TOOLS

logger = logging.getLogger(__name__)

# Preview memory bound: a 100 MP source decoded at full size is ~400 MB. The
# pane never shows more than its viewport, so larger sources are downscaled here.
# shortcut: the bundled AVIF/JXL decoders cannot scale on output, so those still
# decode at full size; upgrade with a decoder --size/--downsampling flag if a
# large batch of huge AVIF/JXL previews starts swapping.
_MAX_PREVIEW_SIDE = 4096
_DECODER_TIMEOUT_SECONDS = 30


def load_preview(path: str) -> QImage | None:
    """Return `path` as a QImage, using a bundled decoder when Qt cannot read it.

    Safe to call from a worker thread.
    """
    image = _read_with_qt(path)
    if image is not None:
        return image
    return _read_with_tool(path)


def _read_with_qt(path: str) -> QImage | None:
    reader = QImageReader(path)
    reader.setAutoTransform(True)
    size = reader.size()
    if size.isValid() and max(size.width(), size.height()) > _MAX_PREVIEW_SIDE:
        ratio = _MAX_PREVIEW_SIDE / max(size.width(), size.height())
        reader.setScaledSize(
            QSize(max(1, round(size.width() * ratio)), max(1, round(size.height() * ratio)))
        )
    image = reader.read()
    if image.isNull():
        return None
    return image


def _read_with_tool(path: str) -> QImage | None:
    mime = QMimeDatabase().mimeTypeForFile(path).name()
    if mime not in DECODER_TOOLS:
        return None
    try:
        with tempfile.TemporaryDirectory(prefix="imslim-preview-") as directory:
            destination = os.path.join(directory, "preview.png")
            run_commands(
                decode_commands(mime, path, destination),
                _DECODER_TIMEOUT_SECONDS,
            )
            return _read_with_qt(destination)
    except (OSError, subprocess.SubprocessError) as err:
        logger.warning("Could not decode preview for %s: %s", path, err)
        return None
