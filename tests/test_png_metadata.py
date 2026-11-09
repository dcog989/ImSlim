import struct
import zlib
from pathlib import Path

from PySide6.QtGui import QImage

from imslim.png_metadata import transfer_png_metadata


def _png(path: Path) -> None:
    image = QImage(8, 8, QImage.Format.Format_RGB32)
    image.fill(0x336699)
    assert image.save(str(path), "PNG")


def _add_chunk(path: Path, kind: bytes, payload: bytes) -> None:
    data = path.read_bytes()
    chunk = (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )
    iend = data.rfind(b"IEND") - 4
    path.write_bytes(data[:iend] + chunk + data[iend:])


def test_copies_metadata_and_replaces_existing_chunks(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    _png(source)
    _add_chunk(source, b"eXIf", b"EXIFDATA")
    _add_chunk(source, b"tEXt", b"Comment\x00hello")
    target = tmp_path / "target.png"
    _png(target)
    _add_chunk(target, b"eXIf", b"STALE")

    transfer_png_metadata(str(source), str(target))

    data = target.read_bytes()
    assert b"EXIFDATA" in data
    assert b"STALE" not in data
    assert b"hello" in data
    assert data.count(b"eXIf") == 1


def test_ignores_a_malformed_target(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    _png(source)
    _add_chunk(source, b"eXIf", b"EXIFDATA")
    target = tmp_path / "target.png"
    target.write_bytes(b"not a png")

    transfer_png_metadata(str(source), str(target))

    assert target.read_bytes() == b"not a png"


def test_does_nothing_without_source_metadata(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    _png(source)
    target = tmp_path / "target.png"
    _png(target)
    expected = target.read_bytes()

    transfer_png_metadata(str(source), str(target))

    assert target.read_bytes() == expected
