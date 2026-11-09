import struct
import zlib
from pathlib import Path

import pytest
from PySide6.QtGui import QImage

from imslim.png_metadata import normalize_png_exif, transfer_png_metadata


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


def test_metadata_copy_survives_a_failed_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.png"
    _png(source)
    _add_chunk(source, b"eXIf", b"EXIFDATA")
    target = tmp_path / "target.png"
    _png(target)
    expected = target.read_bytes()

    def fail_replace(*_args) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("imslim.file_rewrite.os.replace", fail_replace)
    transfer_png_metadata(str(source), str(target))

    assert target.read_bytes() == expected
    assert not Path(str(target) + ".rewrite").exists()


def test_normalizes_a_prefixed_exif_chunk(tmp_path: Path) -> None:
    target = tmp_path / "target.png"
    _png(target)
    _add_chunk(target, b"eXIf", b"Exif\x00\x00II*\x00\x08\x00\x00\x00")
    temp = tmp_path / "target.normalize.png"

    normalize_png_exif(str(target), str(temp))

    data = target.read_bytes()
    assert b"Exif\x00\x00" not in data
    assert b"II*\x00\x08\x00\x00\x00" in data
    assert not temp.exists()


def test_normalize_leaves_a_valid_exif_chunk_alone(tmp_path: Path) -> None:
    target = tmp_path / "target.png"
    _png(target)
    _add_chunk(target, b"eXIf", b"II*\x00\x08\x00\x00\x00")
    expected = target.read_bytes()
    temp = tmp_path / "target.normalize.png"

    normalize_png_exif(str(target), str(temp))

    assert target.read_bytes() == expected
    assert not temp.exists()
