"""Minimal EXIF reader for the Properties dialog.

Only the handful of fields the dialog shows are decoded, and only from the
head of the file, so opening Properties never reads a huge image in full.
"""

from typing import Literal

from ._i18n import _
from .jpeg_metadata import jpeg_exif_payload
from .png_metadata import png_exif_payload

_HEAD_BYTES = 1024 * 1024

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


def read_exif(path: str) -> list[tuple[str, str]]:
    """Return the EXIF fields the UI shows, in a stable order."""
    block = jpeg_exif_payload(path) or png_exif_payload(path)
    if block is None:
        try:
            with open(path, "rb") as handle:
                # TIFF can point anywhere in the file, so only a head read is safe.
                block = _tiff_block(handle.read(_HEAD_BYTES))
        except OSError:
            return []
    if block is None:
        return []
    values = _parse_tiff(block)
    rows: list[tuple[str, str]] = []
    for tag, (label, kind) in _TAGS.items():
        raw = values.get(tag)
        if raw is None:
            continue
        text = _format_value(kind, raw)
        if text:
            rows.append((label, text))
    return rows


def _tiff_block(data: bytes) -> bytes | None:
    if data.startswith((b"II*\x00", b"MM\x00*")):
        return data
    return None


def _parse_tiff(block: bytes) -> dict[int, object]:
    if len(block) < 8:
        return {}
    endian = block[:2]
    byteorder: Literal["little", "big"]
    if endian == b"II":
        byteorder = "little"
    elif endian == b"MM":
        byteorder = "big"
    else:
        return {}
    values: dict[int, object] = {}
    first_ifd = int.from_bytes(block[4:8], byteorder)
    _read_ifd(block, byteorder, first_ifd, values, set())
    return values


def _read_ifd(
    block: bytes,
    byteorder: Literal["little", "big"],
    offset: int,
    values: dict[int, object],
    seen: set[int],
) -> None:
    # Iterative: a crafted chain of Exif IFD pointers must not recurse.
    while offset > 0 and offset + 2 <= len(block) and offset not in seen:
        seen.add(offset)
        count = int.from_bytes(block[offset : offset + 2], byteorder)
        exif_ifd = 0
        for index in range(count):
            entry = offset + 2 + index * 12
            if entry + 12 > len(block):
                return
            tag = int.from_bytes(block[entry : entry + 2], byteorder)
            value_type = int.from_bytes(block[entry + 2 : entry + 4], byteorder)
            number = int.from_bytes(block[entry + 4 : entry + 8], byteorder)
            raw = block[entry + 8 : entry + 12]
            value = _entry_value(block, byteorder, value_type, number, raw)
            if value is not None:
                values[tag] = value
            if tag == _EXIF_IFD_TAG:
                exif_ifd = int.from_bytes(raw, byteorder)
        offset = exif_ifd


def _entry_value(
    block: bytes,
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
        if data_offset + total > len(block):
            return None
        payload = block[data_offset : data_offset + total]
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
