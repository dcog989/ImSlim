import logging
import os
import platform
import re
import subprocess

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap


def image_filter() -> str:
    return _(
        "Images (*.png *.jpg *.jpeg *.webp *.avif *.svg);;"
        "PNG (*.png);;"
        "JPEG (*.jpg *.jpeg);;"
        "WebP (*.webp);;"
        "AVIF (*.avif);;"
        "SVG (*.svg);;"
        "All files (*)"
    )


def sizeof_fmt(num: float) -> str:
    if num is None or num < 0:
        return ""
    value = float(num)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024.0 or unit == "TB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{value:.1f} TB"


def create_thumbnail(filename: str, max_width: int, max_height: int) -> QPixmap | None:
    try:
        pixmap = QPixmap(filename)
        if pixmap.isNull():
            return None
    except Exception as err:
        logging.error(str(err))
        return None

    width = pixmap.width()
    height = pixmap.height()
    if width <= 0 or height <= 0:
        return None

    if width > height:
        ratio = max_width / float(width)
        new_width = max_width
        new_height = int(height * ratio)
    else:
        ratio = max_height / float(height)
        new_width = int(width * ratio)
        new_height = max_height

    scaled = pixmap.scaled(
        new_width,
        new_height,
        Qt.KeepAspectRatio,
        Qt.SmoothTransformation,
    )
    return scaled


def get_image_paths_from_folder(folder_path: str, recursive: bool = False) -> list[str]:
    images = []
    try:
        with os.scandir(folder_path) as it:
            for entry in it:
                if entry.is_dir(follow_symlinks=False):
                    if recursive:
                        images.extend(get_image_paths_from_folder(entry.path, True))
                    continue
                if entry.is_file(follow_symlinks=False) and _is_image_path(entry.name):
                    images.append(entry.path)
    except OSError:
        pass
    return images


_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".avif", ".svg")


def _is_image_path(path: str) -> bool:
    return path.lower().endswith(_IMAGE_EXTENSIONS)


def debug_infos():
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
    for tool in (
        "cjpegli",
        "djpegli",
        "jpegtran",
        "oxipng",
        "pngquant",
        "cwebp",
        "avifdec",
        "avifenc",
        "svgo",
    ):
        sections.append((tool, _tool_version(_version_flag(tool))))

    debug = "\n".join(f"{key}: {value}" for key, value in sections)
    return debug


def _version_flag(tool: str) -> list[str]:
    if tool == "cwebp":
        return ["cwebp", "-version"]
    return [tool, "--version"]


def _tool_version(argv: list[str]) -> str:
    try:
        text = subprocess.check_output(argv)
        return extract_version(text.decode("utf-8"))
    except Exception:
        return _("Version not found")


def extract_version(text: str) -> str:
    version_regex = r"(\d+\.\d+\.\d+)"
    match = re.search(version_regex, text)
    if match:
        return match.group(1)
    return _("Version not found")
