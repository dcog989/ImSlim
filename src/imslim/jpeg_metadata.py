"""Copy a JPEG's metadata segments onto a re-encoded JPEG.

cjpegli cannot read JPEG, so a lossy JPEG re-encode is fed a PNG decoded from
the original. djpegli's PNG output carries no EXIF/XMP, so those segments are
moved across from the original file once the encode is done.
"""

from pathlib import Path

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


def _split_leading(data: bytes) -> tuple[bytes, bytes, int]:
    """Split a JPEG's leading marker segments.

    Returns the segments to keep verbatim, the metadata segments, and the offset
    where the image data (start of scan) begins. Parsing stops at the scan, so
    entropy-coded bytes are never mistaken for markers.

    Raises ValueError when `data` is not a well-formed JPEG.
    """
    if not data.startswith(_SOI):
        raise ValueError("not a JPEG")
    kept = bytearray(_SOI)
    metadata = bytearray()
    offset = 2
    while offset + 4 <= len(data):
        if data[offset] != 0xFF:
            raise ValueError(f"expected a marker at offset {offset}")
        marker = data[offset + 1]
        if marker == _SOS:
            return bytes(kept), bytes(metadata), offset
        if marker == 0x01 or 0xD0 <= marker <= 0xD7:
            # Standalone markers carry no length field.
            kept += data[offset : offset + 2]
            offset += 2
            continue
        length = int.from_bytes(data[offset + 2 : offset + 4], "big")
        if length < 2 or offset + 2 + length > len(data):
            raise ValueError(f"bad segment length at offset {offset}")
        segment = data[offset : offset + 2 + length]
        if _is_metadata(marker, segment):
            metadata += segment
        else:
            kept += segment
        offset += 2 + length
    raise ValueError("no start-of-scan marker")


def transfer_metadata(source: str, target: str) -> None:
    """Copy the metadata segments of `source` into `target`, in place.

    Does nothing when either file cannot be read or is not a JPEG, so a failed
    copy can never damage the encoded output. Metadata already present in
    `target` is replaced rather than duplicated.
    """
    try:
        source_data = Path(source).read_bytes()
        target_data = Path(target).read_bytes()
        _, source_metadata, _ = _split_leading(source_data)
        target_kept, _, scan_offset = _split_leading(target_data)
    except OSError, ValueError:
        return
    if not source_metadata:
        return
    _res = Path(target).write_bytes(target_kept + source_metadata + target_data[scan_offset:])
