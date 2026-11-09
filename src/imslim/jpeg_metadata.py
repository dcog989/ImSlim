"""Copy a JPEG's metadata segments onto a re-encoded JPEG.

cjpegli cannot read JPEG, so a lossy JPEG re-encode is fed a PNG decoded from
the original. djpegli's PNG output carries no EXIF/XMP, so those segments are
moved across from the original file once the encode is done.
"""

import shutil
from pathlib import Path
from typing import IO

from .file_rewrite import rewrite_file

_SOI = b"\xff\xd8"
_APP1 = 0xE1
_APP13 = 0xED
_COM = 0xFE
_SOS = 0xDA
_EXIF = b"Exif\x00\x00"
_XMP = b"http://ns.adobe.com/xap/1.0/\x00"

# Segments carrying user metadata rather than image structure: EXIF, XMP and
# Photoshop's IPTC block live in APP1/APP13, plain text in COM.
_METADATA_MARKERS = (_APP1, _APP13, _COM)


def _is_metadata(marker: int, segment: bytes) -> bool:
    if marker not in _METADATA_MARKERS:
        return False
    if marker == _APP1:
        # Only EXIF and XMP are metadata; APP1 also carries other application data.
        payload = segment[4:]
        return payload.startswith((_EXIF, _XMP))
    return True


def _parse_leading(handle: IO[bytes]) -> tuple[bytes, bytes, int]:
    """Read the marker segments in front of the image data.

    Returns the segments to keep verbatim, the metadata segments, and the
    offset where the image data (start of scan) begins. Reading stops at the
    scan, so entropy-coded bytes are never mistaken for markers.

    Raises ValueError when the stream is not a well-formed JPEG.
    """
    if handle.read(2) != _SOI:
        raise ValueError("not a JPEG")
    kept = bytearray(_SOI)
    metadata = bytearray()
    offset = 2
    while True:
        header = handle.read(2)
        if len(header) < 2:
            raise ValueError("no start-of-scan marker")
        if header[0] != 0xFF:
            raise ValueError(f"expected a marker at offset {offset}")
        marker = header[1]
        if marker == _SOS:
            return bytes(kept), bytes(metadata), offset
        if marker == 0x01 or 0xD0 <= marker <= 0xD7:
            # Standalone markers carry no length field.
            kept += header
            offset += 2
            continue
        length_bytes = handle.read(2)
        if len(length_bytes) < 2:
            raise ValueError(f"truncated segment at offset {offset}")
        length = int.from_bytes(length_bytes, "big")
        if length < 2:
            raise ValueError(f"bad segment length at offset {offset}")
        payload = handle.read(length - 2)
        if len(payload) != length - 2:
            raise ValueError(f"bad segment length at offset {offset}")
        segment = header + length_bytes + payload
        if _is_metadata(marker, segment):
            metadata += segment
        else:
            kept += segment
        offset += 2 + length


def _metadata_segments(source: str) -> bytes:
    with open(source, "rb") as handle:
        _, metadata, _ = _parse_leading(handle)
    return metadata


def _first_payload(segments: bytes, prefix: bytes) -> bytes | None:
    offset = 0
    while offset + 4 <= len(segments):
        length = int.from_bytes(segments[offset + 2 : offset + 4], "big")
        payload = segments[offset + 4 : offset + 2 + length]
        if segments[offset + 1] == _APP1 and payload.startswith(prefix):
            return payload[len(prefix) :]
        offset += 2 + length
    return None


def jpeg_exif_payload(source: str) -> bytes | None:
    """Return the raw EXIF payload of a JPEG, or None when it has none."""
    try:
        metadata = _metadata_segments(source)
    except OSError, ValueError:
        return None
    return _first_payload(metadata, _EXIF)


def _write_kept(
    output: IO[bytes], target: str, kept: bytes, extra: bytes, scan_offset: int
) -> None:
    _res = output.write(kept)
    _res = output.write(extra)
    with open(target, "rb") as source:
        _res = source.seek(scan_offset)
        shutil.copyfileobj(source, output)


def transfer_metadata(source: str, target: str) -> None:
    """Copy the metadata segments of `source` into `target`, in place.

    Does nothing when either file cannot be read or is not a JPEG, so a failed
    copy can never damage the encoded output. Metadata already present in
    `target` is replaced rather than duplicated.
    """
    try:
        source_metadata = _metadata_segments(source)
        with open(target, "rb") as handle:
            target_kept, _, scan_offset = _parse_leading(handle)
    except OSError, ValueError:
        return
    if not source_metadata:
        return
    try:
        rewrite_file(
            target,
            lambda output: _write_kept(output, target, target_kept, source_metadata, scan_offset),
        )
    except OSError:
        return


def strip_metadata(target: str) -> None:
    """Drop EXIF/XMP/comment segments, keeping ICC and color structure."""
    try:
        with open(target, "rb") as handle:
            kept, metadata, scan_offset = _parse_leading(handle)
    except OSError, ValueError:
        return
    if not metadata:
        return
    try:
        rewrite_file(target, lambda output: _write_kept(output, target, kept, b"", scan_offset))
    except OSError:
        return


# cjxl's `-x exif=/xmp=` sidecars contain the raw payload, without the APP1
# marker or the Exif/XMP header that JPEG uses to label it.
_SIDECAR_PREFIXES = {"exif": _EXIF, "xmp": _XMP}


def extract_metadata(source: str, destination: str, kind: str) -> None:
    """Write the source JPEG's EXIF or XMP payload to `destination`.

    A missing or malformed source leaves no file behind, so the caller can
    prune the matching encoder hint and still produce the image.
    """
    prefix = _SIDECAR_PREFIXES[kind]
    try:
        metadata = _metadata_segments(source)
    except OSError, ValueError:
        return
    payload = _first_payload(metadata, prefix)
    if payload is None:
        return
    try:
        _res = Path(destination).write_bytes(payload)
    except OSError:
        Path(destination).unlink(missing_ok=True)
