import logging
import os

from PySide6.QtCore import QSize
from PySide6.QtGui import QImage, QImageReader

from ._i18n import _

logger = logging.getLogger(__name__)

_IMAGE_EXTENSIONS = (
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".avif",
    ".jxl",
    ".svg",
    ".bmp",
    ".tiff",
    ".tif",
)


def image_filter() -> str:
    all_extensions = " ".join(f"*{ext}" for ext in _IMAGE_EXTENSIONS)
    return _(
        f"Images ({all_extensions});;"
        + "PNG (*.png);;"
        + "JPEG (*.jpg *.jpeg);;"
        + "BMP (*.bmp);;"
        + "GIF (*.gif);;"
        + "WebP (*.webp);;"
        + "AVIF (*.avif);;"
        + "JXL (*.jxl);;"
        + "SVG (*.svg);;"
        + "TIFF (*.tiff *.tif);;"
        + "All files (*)"
    )


def is_image_path(path: str) -> bool:
    return path.lower().endswith(_IMAGE_EXTENSIONS)


def get_image_paths_from_folder(folder_path: str, recursive: bool = False) -> list[str]:
    images: list[str] = []
    try:
        with os.scandir(folder_path) as it:
            for entry in sorted(it, key=lambda e: e.name):
                if entry.is_dir(follow_symlinks=False):
                    if recursive:
                        images.extend(get_image_paths_from_folder(entry.path, True))
                    continue
                if entry.is_file(follow_symlinks=False) and is_image_path(entry.name):
                    images.append(entry.path)
    except OSError as err:
        logger.warning("Could not read folder %s: %s", folder_path, err)
    return images


def create_thumbnail_qimage(filename: str, max_width: int, max_height: int) -> QImage | None:
    """Decode and scale an image for use as a thumbnail, returning a value QImage.

    Safe to call from a non-GUI thread; the caller converts the result to a
    QPixmap on the main thread.
    """
    try:
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
    except Exception as err:
        logger.error(str(err))
        return None
    if image.isNull():
        return None
    return image
