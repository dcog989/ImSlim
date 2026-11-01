import logging
import os
import re
from collections.abc import Callable
from typing import TYPE_CHECKING

from PySide6.QtCore import QSize

from .formats import IMAGE_EXTENSIONS

if TYPE_CHECKING:
    from PySide6.QtGui import QImage

# SVG animation comes from SMIL (<animate>/<set>) or CSS (@keyframes/animation).
# A source scan is enough to know the rasterized output would drop it.
_SVG_ANIMATION_PATTERN = re.compile(
    rb"<\s*animate|<\s*set[\s>]|@keyframes|animation\s*:", re.IGNORECASE
)

logger = logging.getLogger(__name__)


def is_image_path(path: str) -> bool:
    return path.lower().endswith(IMAGE_EXTENSIONS)


def is_animated_image(filename: str, mime_type: str) -> bool:
    """True when the source carries animation (GIF frames or SVG animation).

    GIF counts come from Qt; an unknown (-1) count is treated as animated so an
    animated source is never silently flattened. Other formats are static.
    """
    if mime_type == "image/gif":
        # Imported lazily: QtGui needs system GL libraries that a headless
        # environment may lack, and importing this module must not require them.
        from PySide6.QtGui import QImageReader

        return QImageReader(filename).imageCount() != 1
    if mime_type == "image/svg+xml":
        try:
            with open(filename, "rb") as fp:
                return _SVG_ANIMATION_PATTERN.search(fp.read()) is not None
        except OSError:
            return False
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
    """Decode and scale an image for use as a thumbnail, returning a value QImage.

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
    ratio = min(max_width / width, max_height / height, 1.0)
    reader.setScaledSize(QSize(max(1, int(width * ratio)), max(1, int(height * ratio))))
    image = reader.read()
    if image.isNull():
        return None
    return image
