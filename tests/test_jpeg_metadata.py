from pathlib import Path

import pytest

from imslim.jpeg_metadata import transfer_metadata

_SOI = b"\xff\xd8"
# Marker bytes only: everything from the start-of-scan marker on is copied
# verbatim, so the scan itself does not need to be well formed.
_SCAN = b"\xff\xda\x00\x08\x01\x01\x00\x00\x3f\x00"
_SCAN_DATA = b"\x01\x02\x03\xff\xd9"


def _segment(marker: int, payload: bytes) -> bytes:
    return bytes([0xFF, marker]) + (len(payload) + 2).to_bytes(2, "big") + payload


_JFIF = _segment(0xE0, b"JFIF\x00\x01\x02")
_ICC = _segment(0xE2, b"ICC_PROFILE\x00\x01\x01")
_EXIF = _segment(0xE1, b"Exif\x00\x00II*\x00\x08\x00\x00\x00exif-payload")
_XMP = _segment(0xE1, b"http://ns.adobe.com/xap/1.0/\x00<xmp/>")
_COMMENT = _segment(0xFE, b"a comment")
_APP5 = _segment(0xE5, b"not metadata")


def _jpeg(*segments: bytes) -> bytes:
    return _SOI + b"".join(segments) + _SCAN + _SCAN_DATA


def _write(tmp_path: Path, name: str, *segments: bytes) -> str:
    path = tmp_path / name
    path.write_bytes(_jpeg(*segments))
    return str(path)


def test_copies_exif_xmp_and_comments(tmp_path: Path) -> None:
    source = _write(tmp_path, "source.jpg", _JFIF, _EXIF, _XMP, _COMMENT)
    target = _write(tmp_path, "target.jpg", _JFIF, _ICC)
    original_target = Path(target).read_bytes()

    transfer_metadata(source, target)

    result = Path(target).read_bytes()
    assert _EXIF in result
    assert _XMP in result
    assert _COMMENT in result
    # The encoded file keeps its own segments, and its image data is untouched.
    assert _ICC in result
    assert result.endswith(_SCAN + _SCAN_DATA)
    # Metadata sits after the encoder's own segments, before the image data.
    assert result.index(_ICC) < result.index(_EXIF) < result.index(_SCAN)
    assert len(result) == len(original_target) + len(_EXIF) + len(_XMP) + len(_COMMENT)


def test_ignores_non_metadata_segments(tmp_path: Path) -> None:
    source = _write(tmp_path, "source.jpg", _JFIF, _EXIF, _APP5)
    target = _write(tmp_path, "target.jpg", _JFIF)

    transfer_metadata(source, target)

    result = Path(target).read_bytes()
    assert _EXIF in result
    assert _APP5 not in result
    assert _JFIF in result


def test_replaces_metadata_already_in_the_target(tmp_path: Path) -> None:
    source = _write(tmp_path, "source.jpg", _JFIF, _EXIF)
    stale = _segment(0xE1, b"Exif\x00\x00stale")
    target = _write(tmp_path, "target.jpg", _JFIF, stale)

    transfer_metadata(source, target)

    result = Path(target).read_bytes()
    assert stale not in result
    assert result.count(_EXIF) == 1


def test_does_nothing_without_source_metadata(tmp_path: Path) -> None:
    source = _write(tmp_path, "source.jpg", _JFIF, _ICC)
    target = _write(tmp_path, "target.jpg", _JFIF)
    expected = Path(target).read_bytes()

    transfer_metadata(source, target)

    assert Path(target).read_bytes() == expected


@pytest.mark.parametrize("missing", ["source", "target"])
def test_does_nothing_when_a_file_is_missing(tmp_path: Path, missing: str) -> None:
    source = _write(tmp_path, "source.jpg", _JFIF, _EXIF)
    target = _write(tmp_path, "target.jpg", _JFIF)
    expected = Path(target).read_bytes()
    Path(source if missing == "source" else target).unlink()

    transfer_metadata(source, target)

    if missing == "target":
        assert not Path(target).exists()
    else:
        assert Path(target).read_bytes() == expected


def test_does_nothing_when_the_target_is_not_a_jpeg(tmp_path: Path) -> None:
    source = _write(tmp_path, "source.jpg", _JFIF, _EXIF)
    target = tmp_path / "target.jpg"
    target.write_bytes(b"not a jpeg at all")
    expected = target.read_bytes()

    transfer_metadata(source, target)

    assert target.read_bytes() == expected
