import logging
import os
import re
from collections.abc import Callable
from typing import TYPE_CHECKING

from PySide6.QtCore import QSize

from .formats import IMAGE_EXTENSIONS

if TYPE_CHECKING:
    from PySide6.QtGui import QImage

# SVG animation comes from SMIL (<animate>/<set>) or CSS keyframes. A source
# scan is enough to know the rasterized output would drop it.
_SVG_ANIMATION_PATTERN = re.compile(rb"<\s*animate|<\s*set[\s>]|@keyframes", re.IGNORECASE)
_SVG_SCAN_CHUNK = 64 * 1024
# Keeps a tag that straddles a chunk boundary matchable without loading the
# whole file (a large SVG is usually an embedded bitmap).
_SVG_SCAN_OVERLAP = 1024
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
# Scaling a long, thin source's short side to the box makes the long side
# enormous; cap the decoded size so one thumbnail cannot eat gigabytes.
_MAX_THUMBNAIL_SIDE = 2048

# Formats whose animation the app has to detect before choosing an encoder.
ANIMATED_MIME_TYPES: frozenset[str] = frozenset(
    {"image/gif", "image/webp", "image/png", "image/svg+xml"}
)

logger = logging.getLogger(__name__)


def is_image_path(path: str) -> bool:
    return path.lower().endswith(IMAGE_EXTENSIONS)


def _png_is_animated(filename: str) -> bool:
    try:
        with open(filename, "rb") as fp:
            if fp.read(len(_PNG_SIGNATURE)) != _PNG_SIGNATURE:
                return False
            while True:
                header = fp.read(8)
                if len(header) < 8:
                    return False
                length = int.from_bytes(header[:4], "big")
                chunk_type = header[4:8]
                if chunk_type == b"acTL":
                    return True
                if chunk_type in (b"IDAT", b"IEND"):
                    return False
                _res = fp.seek(4 + length, 1)
    except OSError:
        return False


def _svg_is_animated(filename: str) -> bool:
    try:
        with open(filename, "rb") as fp:
            tail = b""
            while chunk := fp.read(_SVG_SCAN_CHUNK):
                if _SVG_ANIMATION_PATTERN.search(tail + chunk):
                    return True
                tail = chunk[-_SVG_SCAN_OVERLAP:]
    except OSError:
        return False
    return False


def is_animated_image(filename: str, mime_type: str) -> bool:
    """True when the source carries animation (GIF/WebP/PNG frames or SVG animation).

    Animated counts come from Qt; an unknown (-1) count is treated as animated
    so an animated source is never silently flattened. APNG is detected from its
    `acTL` chunk, which Qt's PNG reader does not report.
    """
    if mime_type in ("image/gif", "image/webp"):
        # Imported lazily: QtGui needs system GL libraries that a headless
        # environment may lack, and importing this module must not require them.
        from PySide6.QtGui import QImageReader

        return QImageReader(filename).imageCount() != 1
    if mime_type == "image/png":
        return _png_is_animated(filename)
    if mime_type == "image/svg+xml":
        return _svg_is_animated(filename)
    return False


def get_image_paths_from_folder(
    folder_path: str,
    recursive: bool = False,
    is_cancelled: Callable[[], bool] | None = None,
) -> list[str]:
    images: list[str] = []
    try:
        with os.scandir(folder_path) as it:
            for entry in sorted(it, key=lambda e: e.name):
                if is_cancelled is not None and is_cancelled():
                    return images
                if entry.is_dir(follow_symlinks=False):
                    if recursive:
                        images.extend(get_image_paths_from_folder(entry.path, True, is_cancelled))
                    continue
                # Files may be symlinks (only the directory walk must not follow
                # links, or a cycle would recurse forever).
                if entry.is_file() and is_image_path(entry.name):
                    images.append(entry.path)
    except OSError as err:
        logger.warning("Could not read folder %s: %s", folder_path, err)
    return images


def create_thumbnail_qimage(filename: str, max_width: int, max_height: int) -> QImage | None:
    """Decode a square, cover-cropped thumbnail, returning a value QImage.

    The shortest side fills the box and the longer side is centre-cropped, so
    every thumbnail fills its cell without letterboxing.

    Safe to call from a non-GUI thread; the caller converts the result to a
    QPixmap on the main thread.
    """
    from PySide6.QtGui import QImageReader

    reader = QImageReader(filename)
    reader.setAutoTransform(True)
    size = reader.size()
    width = size.width()
    height = size.height()
    if width <= 0 or height <= 0:
        return None
    # Scale the shortest side to the box, then crop the square afterwards so
    # rounding and EXIF rotation cannot leave a non-square result.
    ratio = max(max_width, max_height) / min(width, height)
    ratio = min(ratio, _MAX_THUMBNAIL_SIDE / max(width, height))
    reader.setScaledSize(QSize(max(1, round(width * ratio)), max(1, round(height * ratio))))
    image = reader.read()
    if image.isNull():
        return None
    side = min(image.width(), image.height())
    left = (image.width() - side) // 2
    top = (image.height() - side) // 2
    return image.copy(left, top, side, side)
