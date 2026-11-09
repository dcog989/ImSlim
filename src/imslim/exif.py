"""Minimal EXIF reader for the Properties dialog.

Only the handful of fields the dialog shows are decoded, from the metadata
block or from the file header, so opening Properties never reads a huge image
in full.
"""

import os
import re
import subprocess
import tempfile
from collections.abc import Callable
from typing import Literal

from ._i18n import _
from .binary_resolver import resolve_tool
from .conversion import decode_commands, run_commands
from .jpeg_metadata import jpeg_exif_payload
from .png_metadata import png_exif_payload, png_size

_EXIF_TOOL_TIMEOUT_SECONDS = 10
_EXIF_PREFIX = b"Exif\x00\x00"
_WEBP_EXIF = b"EXIF"
_JXL_SIZE = re.compile(r"JPEG XL image, (\d+)x(\d+)")

# Tag -> (label, formatter) in display order.
_TAGS: dict[int, tuple[str, str]] = {
    0x010F: (_("Camera make"), "text"),
    0x0110: (_("Camera model"), "text"),
    0x9003: (_("Taken"), "text"),
    0x0132: (_("Modified"), "text"),
    0x0112: (_("Orientation"), "orientation"),
    0x8827: (_("ISO"), "int"),
    0x829A: (_("Exposure"), "exposure"),
    0x829D: (_("Aperture"), "aperture"),
    0x920A: (_("Focal length"), "focal"),
}

_ORIENTATIONS = {
    1: _("Normal"),
    2: _("Mirrored"),
    3: _("Rotated 180°"),
    4: _("Mirrored vertically"),
    5: _("Mirrored, rotated 90°"),
    6: _("Rotated 90° CW"),
    7: _("Mirrored, rotated 270°"),
    8: _("Rotated 90° CCW"),
}

_TYPE_SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 9: 4, 10: 8}
_EXIF_IFD_TAG = 0x8769


def jpeg_orientation(path: str) -> int:
    """EXIF Orientation of a JPEG, or 1 (normal) when absent or unreadable."""
    block = jpeg_exif_payload(path)
    if block is None:
        return 1
    value = _parse_tiff(block).get(0x0112)
    return value if isinstance(value, int) and value in _ORIENTATIONS else 1


def _jxl_info(path: str) -> str | None:
    """jxlinfo output, which carries the size and the metadata kinds present."""
    try:
        completed = subprocess.run(
            [resolve_tool("jxlinfo"), path],
            check=False,
            capture_output=True,
            text=True,
            timeout=_EXIF_TOOL_TIMEOUT_SECONDS,
        )
    except OSError, subprocess.SubprocessError:
        return None
    return completed.stdout if completed.returncode == 0 else None


def _jxl_size(info: str | None) -> tuple[int, int] | None:
    match = _JXL_SIZE.search(info or "")
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2))


def _jxl_exif_payload(path: str, info: str | None) -> bytes | None:
    # jxlinfo is a header-only probe; skip the djxl call when no EXIF is present.
    if info is not None and "exif" not in info.lower():
        return None
    try:
        completed = subprocess.run(
            [resolve_tool("djxl"), path, "-", "--output_format", "exif"],
            check=False,
            capture_output=True,
            timeout=_EXIF_TOOL_TIMEOUT_SECONDS,
        )
    except OSError, subprocess.SubprocessError:
        return None
    return completed.stdout or None


def _avif_metadata(path: str) -> tuple[tuple[int, int] | None, bytes | None]:
    """Decode an AVIF to PNG once and read its size and EXIF chunk."""
    try:
        with tempfile.TemporaryDirectory(prefix="imslim-exif-") as directory:
            destination = os.path.join(directory, "decoded.png")
            run_commands(
                decode_commands("image/avif", path, destination),
                _EXIF_TOOL_TIMEOUT_SECONDS,
            )
            return png_size(destination), png_exif_payload(destination)
    except OSError, subprocess.SubprocessError, ValueError:
        return None, None


def _decoder_metadata(path: str, mime_type: str) -> tuple[tuple[int, int] | None, bytes | None]:
    """Size and EXIF payload from a bundled decoder, using one decode at most."""
    if mime_type == "image/jxl":
        info = _jxl_info(path)
        return _jxl_size(info), _jxl_exif_payload(path, info)
    if mime_type == "image/avif":
        return _avif_metadata(path)
    return None, None


def _webp_exif_payload(path: str) -> bytes | None:
    """Return a WebP RIFF file's EXIF chunk payload, or None."""
    try:
        with open(path, "rb") as handle:
            header = handle.read(12)
            if len(header) < 12 or header[:4] != b"RIFF" or header[8:12] != b"WEBP":
                return None
            while True:
                chunk_header = handle.read(8)
                if len(chunk_header) < 8:
                    return None
                chunk_type = chunk_header[:4]
                length = int.from_bytes(chunk_header[4:8], "little")
                if chunk_type == _WEBP_EXIF:
                    payload = handle.read(length)
                    return payload if len(payload) == length else None
                _res = handle.seek(length + (length & 1), 1)
    except OSError:
        return None


def read_exif(path: str, mime_type: str = "") -> list[tuple[str, str]]:
    """Return the EXIF fields the UI shows, in a stable order."""
    if mime_type in ("image/avif", "image/jxl"):
        _, block = _decoder_metadata(path, mime_type)
    else:
        block = jpeg_exif_payload(path) or png_exif_payload(path) or _webp_exif_payload(path)
        if block is None:
            return _rows_from_values(_parse_tiff_file(path))
    if block is None:
        return []
    return _rows_from_values(_parse_tiff(block))


def read_exif_and_size(
    path: str, mime_type: str = ""
) -> tuple[tuple[int, int] | None, list[tuple[str, str]]]:
    """Return dimensions and EXIF rows, decoding AVIF/JXL at most once.

    Other formats return no size because Qt reports it without decoding.
    """
    if mime_type in ("image/avif", "image/jxl"):
        size, block = _decoder_metadata(path, mime_type)
        rows = [] if block is None else _rows_from_values(_parse_tiff(block))
        return size, rows
    return None, read_exif(path, mime_type)


def _rows_from_values(values: dict[int, object]) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for tag, (label, kind) in _TAGS.items():
        raw = values.get(tag)
        if raw is None:
            continue
        text = _format_value(kind, raw)
        if text:
            rows.append((label, text))
    return rows


def _parse_tiff(block: bytes) -> dict[int, object]:
    block = block.removeprefix(_EXIF_PREFIX)
    return _parse_tiff_stream(len(block), lambda offset, count: block[offset : offset + count])


def _parse_tiff_file(path: str) -> dict[int, object]:
    """Parse a TIFF file in place, so an IFD anywhere in the file is reachable."""
    try:
        with open(path, "rb") as handle:
            _res = handle.seek(0, os.SEEK_END)
            length = handle.tell()

            def read(offset: int, count: int) -> bytes:
                if offset < 0 or count < 0 or offset + count > length:
                    return b""
                _res = handle.seek(offset)
                return handle.read(count)

            return _parse_tiff_stream(length, read)
    except OSError:
        return {}


def _parse_tiff_stream(length: int, read: Callable[[int, int], bytes]) -> dict[int, object]:
    head = read(0, 8)
    if len(head) < 8:
        return {}
    endian = head[:2]
    byteorder: Literal["little", "big"]
    if endian == b"II":
        byteorder = "little"
    elif endian == b"MM":
        byteorder = "big"
    else:
        return {}
    values: dict[int, object] = {}
    first_ifd = int.from_bytes(head[4:8], byteorder)
    _read_ifd(length, read, byteorder, first_ifd, values, set())
    return values


def _read_ifd(
    length: int,
    read: Callable[[int, int], bytes],
    byteorder: Literal["little", "big"],
    offset: int,
    values: dict[int, object],
    seen: set[int],
) -> None:
    # Iterative: a crafted chain of Exif IFD pointers must not recurse.
    while offset > 0 and offset + 2 <= length and offset not in seen:
        seen.add(offset)
        count_bytes = read(offset, 2)
        if len(count_bytes) < 2:
            return
        count = int.from_bytes(count_bytes, byteorder)
        exif_ifd = 0
        for index in range(count):
            entry = offset + 2 + index * 12
            if entry + 12 > length:
                return
            entry_bytes = read(entry, 12)
            if len(entry_bytes) < 12:
                return
            tag = int.from_bytes(entry_bytes[0:2], byteorder)
            value_type = int.from_bytes(entry_bytes[2:4], byteorder)
            number = int.from_bytes(entry_bytes[4:8], byteorder)
            raw = entry_bytes[8:12]
            value = _entry_value(length, read, byteorder, value_type, number, raw)
            if value is not None:
                values[tag] = value
            if tag == _EXIF_IFD_TAG:
                exif_ifd = int.from_bytes(raw, byteorder)
        offset = exif_ifd


def _entry_value(
    length: int,
    read: Callable[[int, int], bytes],
    byteorder: Literal["little", "big"],
    value_type: int,
    number: int,
    raw: bytes,
) -> object | None:
    size = _TYPE_SIZES.get(value_type)
    if size is None or number <= 0:
        return None
    total = size * number
    if total > 4:
        data_offset = int.from_bytes(raw, byteorder)
        if data_offset + total > length:
            return None
        payload = read(data_offset, total)
        if len(payload) != total:
            return None
    else:
        payload = raw[:total]
    if value_type == 2:
        return payload.split(b"\x00", 1)[0].decode("utf-8", errors="replace").strip()
    if value_type in (1, 3, 4, 9):
        signed = value_type == 9
        return int.from_bytes(payload[:size], byteorder, signed=signed)
    if value_type in (5, 10):
        signed = value_type == 10
        numerator = int.from_bytes(payload[:4], byteorder, signed=signed)
        denominator = int.from_bytes(payload[4:8], byteorder, signed=signed)
        return numerator / denominator if denominator else None
    return None


def _format_value(kind: str, value: object) -> str:
    match kind:
        case "orientation":
            return _ORIENTATIONS.get(value, "") if isinstance(value, int) else ""
        case "int":
            return str(value) if isinstance(value, int) else ""
        case "exposure":
            if isinstance(value, float):
                if value <= 0:
                    return ""
                if value < 1:
                    return f"1/{round(1 / value)} s"
                return f"{value:g} s"
            return ""
        case "aperture":
            return f"f/{value:g}" if isinstance(value, float) else ""
        case "focal":
            return f"{value:g} mm" if isinstance(value, float) else ""
        case _:
            return str(value).strip() if isinstance(value, str) else ""
