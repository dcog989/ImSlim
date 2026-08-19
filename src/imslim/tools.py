import locale
import logging
import os
import platform
import re
import subprocess

from PySide6.QtCore import QSize
from PySide6.QtGui import QImage, QImageReader

from .binary_resolver import KNOWN_TOOLS, resolve_tool


def image_filter() -> str:
    return _(
        "Images (*.png *.jpg *.jpeg *.gif *.webp *.avif *.jxl *.svg *.bmp *.tiff *.tif);;"
        "PNG (*.png);;"
        "JPEG (*.jpg *.jpeg);;"
        "BMP (*.bmp);;"
        "GIF (*.gif);;"
        "WebP (*.webp);;"
        "AVIF (*.avif);;"
        "JXL (*.jxl);;"
        "SVG (*.svg);;"
        "TIFF (*.tiff *.tif);;"
        "All files (*)"
    )


def sizeof_fmt(num: float | None) -> str:
    if num is None or num < 0:
        return ""
    value = float(num)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024.0 or unit == "TiB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f}".replace(".", _decimal_separator()) + f" {unit}"
        value /= 1024.0
    return ""


def _decimal_separator() -> str:
    """Return the host locale's decimal separator (e.g. "." or ",")."""
    separator = getattr(_decimal_separator, "_cached", None)
    if separator is not None:
        return separator
    try:
        locale.setlocale(locale.LC_NUMERIC, "")
        separator = locale.localeconv()["decimal_point"]
    except (locale.Error, ValueError, AttributeError, KeyError):
        separator = "."
    _decimal_separator._cached = separator
    return separator


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
        logging.error(str(err))
        return None
    if image.isNull():
        return None
    return image


def get_image_paths_from_folder(folder_path: str, recursive: bool = False) -> list[str]:
    images = []
    try:
        with os.scandir(folder_path) as it:
            for entry in sorted(it, key=lambda e: e.name):
                if entry.is_dir(follow_symlinks=False):
                    if recursive:
                        images.extend(get_image_paths_from_folder(entry.path, True))
                    continue
                if entry.is_file(follow_symlinks=False) and _is_image_path(entry.name):
                    images.append(entry.path)
    except OSError as err:
        logging.warning("Could not read folder %s: %s", folder_path, err)
    return images


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


def _is_image_path(path: str) -> bool:
    return path.lower().endswith(_IMAGE_EXTENSIONS)


def debug_pairs() -> list[tuple[str, str]]:
    python_version = platform.python_version()
    try:
        import PySide6

        qt_version = PySide6.__version__
    except Exception:
        qt_version = _("Version not found")

    sections = [
        ("Python", python_version),
        ("PySide6/Qt", qt_version),
    ]
    for tool in KNOWN_TOOLS:
        try:
            path = resolve_tool(tool)
        except OSError:
            path = None
        if path is None:
            sections.append((tool, _("Version not found")))
            continue
        sections.append((tool, _tool_version(_version_flag(path, tool))))

    return sections


def _version_flag(path: str, tool: str) -> list[str]:
    if tool in ("cwebp", "jpegtran"):
        return [path, "-version"]
    return [path, "--version"]


_VERSION_TIMEOUT = 10


def _tool_version(argv: list[str]) -> str:
    try:
        # Some tools (e.g. the bundled mozjpeg jpegtran) print the version to
        # stderr, so capture both streams rather than stdout alone.
        completed = subprocess.run(argv, capture_output=True, check=False, timeout=_VERSION_TIMEOUT)
        text = completed.stdout + completed.stderr
        return extract_version(text.decode("utf-8", errors="replace"))
    except Exception:
        return _("Version not found")


def extract_version(text: str) -> str:
    # Accept both three-part (4.1.5) and two-part (gifsicle's 1.96) versions.
    version_regex = r"(\d+\.\d+(?:\.\d+)?)"
    match = re.search(version_regex, text)
    if match:
        return match.group(1)
    return _("Version not found")
