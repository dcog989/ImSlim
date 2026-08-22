import functools
import locale
import logging
import os
import platform
import re
import subprocess

from PySide6.QtCore import QLocale, QSize
from PySide6.QtGui import QImage, QImageReader

from ._i18n import _
from .binary_resolver import KNOWN_TOOLS, resolve_tool

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


@functools.cache
def _decimal_separator() -> str:
    """Return the host locale's decimal separator (e.g. "." or ",").

    Read from Qt's system locale instead of mutating the process-wide locale
    with locale.setlocale().
    """
    return QLocale().decimalPoint()


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


def get_image_paths_from_folder(folder_path: str, recursive: bool = False) -> list[str]:
    images: list[str] = []
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
        logger.warning("Could not read folder %s: %s", folder_path, err)
    return images


def _is_image_path(path: str) -> bool:
    return path.lower().endswith(_IMAGE_EXTENSIONS)


def static_about_pairs() -> list[tuple[str, str]]:
    python_version = platform.python_version()
    try:
        import PySide6

        qt_version = PySide6.__version__
    except Exception:
        qt_version = _("Version not available")
    return [
        ("Python", python_version),
        ("PySide6/Qt", qt_version),
    ]


# cjpegli/djpegli ship as part of libjxl and expose no version flag; their
# version matches the sibling cjxl/djxl build, so derive it from there.
_JPEGLI_SIBLING = {"cjpegli": "cjxl", "djpegli": "djxl"}


def tool_version_pairs() -> list[tuple[str, str]]:
    resolved: dict[str, str | None] = {}
    for tool in KNOWN_TOOLS:
        try:
            resolved[tool] = resolve_tool(tool)
        except OSError:
            resolved[tool] = None
    pairs: list[tuple[str, str]] = []
    for tool in KNOWN_TOOLS:
        path = resolved[tool]
        if path is None:
            pairs.append((tool, _("Version not available")))
            continue
        sibling = _JPEGLI_SIBLING.get(tool)
        if sibling is not None:
            sibling_path = resolved.get(sibling)
            if sibling_path is not None:
                pairs.append((tool, _tool_version(_version_flag(sibling_path, sibling))))
                continue
        pairs.append((tool, _tool_version(_version_flag(path, tool))))
    return pairs


def system_info_pairs() -> list[tuple[str, str]]:
    """Collects system details useful for debugging bug reports."""
    distro, distro_version = _distro()
    language, encoding = locale.getlocale()
    locale_label = f"{language} ({encoding})" if language and encoding else language or _("Unknown")
    pairs: list[tuple[str, str]] = [
        ("OS", f"{distro} {distro_version}".strip()),
        ("Kernel", platform.release()),
        ("Architecture", platform.machine()),
        ("Processor", _cpu_model()),
        ("CPU Count", str(os.cpu_count() or _("Unknown"))),
        ("Memory", _total_memory()),
        ("Locale", locale_label),
    ]
    return pairs


def _distro() -> tuple[str, str]:
    # platform.* reports the kernel, not the distribution; read os-release.
    try:
        with open("/etc/os-release") as fh:
            data: dict[str, str] = {}
            for line in fh:
                line = line.strip()
                if "=" in line:
                    key, value = line.split("=", 1)
                    data[key] = value.strip().strip('"')
            name = data.get("NAME", "")
            version = data.get("VERSION_ID", "")
            if name:
                return name, version
    except OSError:
        pass
    return platform.system(), ""


def _cpu_model() -> str:
    # platform.processor() is empty on Linux; read the model name instead.
    try:
        with open("/proc/cpuinfo") as fh:
            for line in fh:
                if line.lower().startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or _("Unknown")


def _total_memory() -> str:
    try:
        if hasattr(os, "sysconf") and os.sysconf_names.get("SC_PAGE_SIZE") is not None:
            page_size = os.sysconf("SC_PAGE_SIZE")
            phys_pages = os.sysconf("SC_PHYS_PAGES")
            if page_size and phys_pages:
                return sizeof_fmt(page_size * phys_pages)
    except ValueError, OSError:
        pass
    try:
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    return sizeof_fmt(kb * 1024)
    except OSError:
        pass
    return _("Unknown")


def debug_pairs() -> list[tuple[str, str]]:
    return [
        *static_about_pairs(),
        *system_info_pairs(),
        *tool_version_pairs(),
    ]


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
        return _("Version not available")


def extract_version(text: str) -> str:
    # Accept both three-part (4.1.5) and two-part (gifsicle's 1.96) versions.
    version_regex = r"(\d+\.\d+(?:\.\d+)?)"
    match = re.search(version_regex, text)
    if match:
        return match.group(1)
    return _("Version not available")
