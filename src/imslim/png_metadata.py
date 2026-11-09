"""Copy optional metadata chunks from one PNG onto another.

pngquant (the lossy PNG step) discards chunks it does not understand, including
eXIf, so a lossy re-encode loses EXIF/XMP unless the chunks are copied back.
"""

from collections.abc import Iterator
from pathlib import Path

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_IEND = b"IEND"
_METADATA_CHUNKS = frozenset({b"eXIf", b"iTXt", b"tEXt", b"zTXt"})


def _chunks(data: bytes) -> Iterator[tuple[bytes, bytes]]:
    if not data.startswith(_PNG_SIGNATURE):
        raise ValueError("not a PNG")
    offset = len(_PNG_SIGNATURE)
    while offset + 12 <= len(data):
        length = int.from_bytes(data[offset : offset + 4], "big")
        chunk_type = data[offset + 4 : offset + 8]
        end = offset + 12 + length
        if end > len(data):
            raise ValueError("bad chunk length")
        yield chunk_type, data[offset:end]
        if chunk_type == _IEND:
            return
        offset = end
    raise ValueError("no IEND")


def transfer_png_metadata(source: str, target: str) -> None:
    """Copy `source`'s metadata chunks onto `target`, replacing existing copies.

    A malformed or unreadable file is ignored: the encoded image must survive a
    failed metadata copy.
    """
    try:
        source_data = Path(source).read_bytes()
        target_data = Path(target).read_bytes()
        metadata = [raw for kind, raw in _chunks(source_data) if kind in _METADATA_CHUNKS]
        kept = [raw for kind, raw in _chunks(target_data) if kind not in _METADATA_CHUNKS]
    except OSError, ValueError:
        return
    if not metadata or not kept or kept[-1][4:8] != _IEND:
        return
    try:
        _res = Path(target).write_bytes(
            _PNG_SIGNATURE + b"".join(kept[:-1]) + b"".join(metadata) + kept[-1]
        )
    except OSError:
        return
