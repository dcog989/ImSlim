import functools
import logging
import os
import platform
import shutil
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# PyInstaller extracts the bundled bin/ tree into _MEIPASS at runtime; when
# frozen the source-tree path (above bin/) is not on disk.
_BIN_ROOT = (
    Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    if getattr(sys, "frozen", False)
    else Path(__file__).parent
)
BIN_DIR = _BIN_ROOT / "bin"

KNOWN_TOOLS = (
    "avifdec",
    "avifenc",
    "cjpegli",
    "cjxl",
    "cwebp",
    "djpegli",
    "djxl",
    "gifsicle",
    "jpegtran",
    "oxipng",
    "pngquant",
    "svgo",
)


def _platform_dir() -> str:
    """Return the binary subdir for the current platform (e.g. linux-x86_64).

    Binaries are only bundled for the platforms built by the release pipeline;
    other platforms fall back to PATH via shutil.which().
    """
    return f"{platform.system().lower()}-{platform.machine().lower()}"


def _tool_file(directory: str, name: str) -> str | None:
    candidate = os.path.join(directory, name)
    if os.path.isfile(candidate):
        return candidate
    return None


@functools.cache
def _resolve(name: str) -> str | None:
    """Return the cached path to a tool, or None if it could not be found."""
    candidate = _tool_file(str(BIN_DIR / _platform_dir()), name)
    if candidate is not None:
        _make_executable(candidate)
        return candidate

    return shutil.which(name)


def resolve_tool(name: str) -> str:
    """Return the path to a compression tool, preferring the bundled binary."""
    if name not in KNOWN_TOOLS:
        raise FileNotFoundError(f"Unknown tool: {name}")

    path = _resolve(name)
    if path is None:
        raise FileNotFoundError(
            f"No bundled binary for '{name}' on {_platform_dir()} and it was not found on PATH."
        )
    return path


def _make_executable(path: str) -> None:
    # Wheel extraction may not preserve the exec bit; ensure the binary runs.
    if os.path.isfile(path) and not os.access(path, os.X_OK):
        try:
            os.chmod(path, 0o755)
        except OSError as err:
            logger.warning("Could not mark %s executable: %s", path, err)
