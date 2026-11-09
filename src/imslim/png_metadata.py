"""Copy optional metadata chunks from one PNG onto another.

pngquant (the lossy PNG step) discards chunks it does not understand, including
eXIf, so a lossy re-encode loses EXIF/XMP unless the chunks are copied back.
"""

import struct
import zlib
from collections.abc import Iterator
from pathlib import Path
from typing import IO

from .file_rewrite import rewrite_file

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_IEND = b"IEND"
_EXIF = b"eXIf"
_EXIF_HEADER = b"Exif\x00\x00"
_METADATA_CHUNKS = frozenset({_EXIF, b"iTXt", b"tEXt", b"zTXt"})


def _source_metadata_chunks(path: str) -> Iterator[bytes]:
    """Yield raw metadata chunks without reading IDAT data into memory."""
    with open(path, "rb") as handle:
        if handle.read(len(_PNG_SIGNATURE)) != _PNG_SIGNATURE:
            raise ValueError("not a PNG")
        while True:
            header = handle.read(8)
            if len(header) < 8:
                raise ValueError("no IEND")
            length = int.from_bytes(header[:4], "big")
            chunk_type = header[4:8]
            if chunk_type in _METADATA_CHUNKS:
                payload = handle.read(length)
                crc = handle.read(4)
                if len(payload) != length or len(crc) != 4:
                    raise ValueError("bad chunk length")
                yield header + payload + crc
            else:
                _res = handle.seek(4 + length, 1)
            if chunk_type == _IEND:
                return


def png_exif_payload(path: str) -> bytes | None:
    """Return the payload of a PNG's eXIf chunk, or None when it has none."""
    try:
        for chunk in _source_metadata_chunks(path):
            if chunk[4:8] == _EXIF:
                return chunk[8:-4]
    except OSError, ValueError:
        return None
    return None


def png_size(path: str) -> tuple[int, int] | None:
    """Return a PNG's pixel size from its header, or None when it is not a PNG."""
    try:
        with open(path, "rb") as handle:
            head = handle.read(24)
    except OSError:
        return None
    if len(head) < 24 or head[:8] != _PNG_SIGNATURE or head[12:16] != b"IHDR":
        return None
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


def _copy_bytes(source: IO[bytes], target: IO[bytes], count: int) -> None:
    while count:
        chunk = source.read(min(count, 64 * 1024))
        if not chunk:
            raise ValueError("truncated")
        _res = target.write(chunk)
        count -= len(chunk)


def _copy_with_metadata(target: str, output: IO[bytes], metadata: list[bytes]) -> None:
    """Copy `target` into `output`, replacing its metadata chunks in one pass."""
    with open(target, "rb") as handle:
        if handle.read(len(_PNG_SIGNATURE)) != _PNG_SIGNATURE:
            raise ValueError("not a PNG")
        _res = output.write(_PNG_SIGNATURE)
        inserted = False
        while True:
            header = handle.read(8)
            if len(header) < 8:
                raise ValueError("no IEND")
            length = int.from_bytes(header[:4], "big")
            chunk_type = header[4:8]
            if chunk_type == _IEND:
                if not inserted:
                    for chunk in metadata:
                        _res = output.write(chunk)
                _res = output.write(header)
                _copy_bytes(handle, output, 4)
                return
            if chunk_type in _METADATA_CHUNKS:
                _res = handle.seek(4 + length, 1)
                continue
            _res = output.write(header)
            _copy_bytes(handle, output, 4 + length)


def transfer_png_metadata(source: str, target: str) -> None:
    """Copy `source`'s metadata chunks onto `target`, replacing existing copies.

    A malformed or unreadable file is ignored: the encoded image must survive a
    failed metadata copy.
    """
    try:
        metadata = list(_source_metadata_chunks(source))
    except OSError, ValueError:
        return
    if not metadata:
        return
    try:
        rewrite_file(target, lambda output: _copy_with_metadata(target, output, metadata))
    except OSError, ValueError:
        return


def _has_prefixed_exif(path: str) -> bool:
    payload = png_exif_payload(path)
    return payload is not None and payload.startswith(_EXIF_HEADER)


def normalize_png_exif(path: str, temp: str) -> None:
    """Strip the JPEG `Exif\\0\\0` prefix from a PNG eXIf chunk, in place.

    avifdec writes the JPEG-style payload into PNG's eXIf, which libpng and
    avifenc reject; normalizing it keeps the EXIF on the next encode.
    """
    try:
        if not _has_prefixed_exif(path):
            return
        with open(path, "rb") as source, open(temp, "wb") as target:
            _res = target.write(_PNG_SIGNATURE)
            _res = source.read(len(_PNG_SIGNATURE))
            while True:
                header = source.read(8)
                if len(header) < 8:
                    raise ValueError("no IEND")
                length = int.from_bytes(header[:4], "big")
                chunk_type = header[4:8]
                if chunk_type == _EXIF:
                    payload = source.read(length)
                    _res = source.read(4)  # discard the old CRC
                    payload = payload.removeprefix(_EXIF_HEADER)
                    _res = target.write(struct.pack(">I", len(payload)))
                    _res = target.write(chunk_type)
                    _res = target.write(payload)
                    _res = target.write(
                        struct.pack(">I", zlib.crc32(chunk_type + payload) & 0xFFFFFFFF)
                    )
                else:
                    _res = target.write(header)
                    _copy_bytes(source, target, 4 + length)
                if chunk_type == _IEND:
                    break
        _res = Path(temp).replace(path)
    except OSError, ValueError:
        Path(temp).unlink(missing_ok=True)
