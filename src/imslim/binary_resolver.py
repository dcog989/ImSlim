import logging
import os
import platform
import shutil
from pathlib import Path

BIN_DIR = Path(__file__).parent / "bin"

_TOOLS = (
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
    """Return the binary subdir for the current platform (e.g. linux-x86_64)."""
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "windows":
        machine = "x86_64"
    return f"{system}-{machine}"


def resolve_tool(name: str) -> str:
    """Return the path to a compression tool, preferring the bundled binary."""
    if name not in _TOOLS:
        raise FileNotFoundError(f"Unknown tool: {name}")

    override_dir = os.environ.get("IMSLIM_TOOLS_PATH")
    if override_dir:
        candidate = os.path.join(override_dir, name)
        if os.path.isfile(candidate):
            _make_executable(candidate)
            return candidate

    bundled = BIN_DIR / _platform_dir() / name
    if bundled.is_file():
        _make_executable(str(bundled))
        return str(bundled)

    found = shutil.which(name)
    if found:
        return found

    raise FileNotFoundError(
        f"No bundled binary for '{name}' on {_platform_dir()} and it was not found on PATH."
    )


def _make_executable(path: str) -> None:
    # Wheel extraction may not preserve the exec bit; ensure the binary runs.
    if os.path.isfile(path) and not os.access(path, os.X_OK):
        try:
            os.chmod(path, 0o755)
        except OSError as err:
            logging.warning("Could not mark %s executable: %s", path, err)
