import zlib
from pathlib import Path
from subprocess import CompletedProcess

from imslim.commands import Command
from imslim.exif import (
    _format_value,
    _parse_tiff,
    jpeg_orientation,
    read_exif,
    read_exif_and_size,
)


def _tiff_block() -> bytes:
    """Little-endian TIFF with Make (ASCII) and Orientation (SHORT)."""
    data_offset = 38
    block = bytearray(b"II" + (42).to_bytes(2, "little") + (8).to_bytes(4, "little"))
    block += (2).to_bytes(2, "little")
    block += (0x010F).to_bytes(2, "little") + (2).to_bytes(2, "little")
    block += (5).to_bytes(4, "little") + data_offset.to_bytes(4, "little")
    block += (0x0112).to_bytes(2, "little") + (3).to_bytes(2, "little")
    block += (1).to_bytes(4, "little") + (6).to_bytes(2, "little") + b"\x00\x00"
    block += (0).to_bytes(4, "little")
    assert len(block) == data_offset
    block += b"ACME\x00"
    return bytes(block)


def _chunk(kind: bytes, data: bytes) -> bytes:
    return (
        len(data).to_bytes(4, "big")
        + kind
        + data
        + (zlib.crc32(kind + data) & 0xFFFFFFFF).to_bytes(4, "big")
    )


def _png_with_exif(width: int, height: int, payload: bytes) -> bytes:
    ihdr = width.to_bytes(4, "big") + height.to_bytes(4, "big") + b"\x08\x02\x00\x00\x00"
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"eXIf", payload)
        + _chunk(b"IEND", b"")
    )


def _fake_jxl_run(exif: bytes, info: str):
    def fake_run(argv, **kwargs):
        if kwargs.get("text"):
            return CompletedProcess(argv, 0, stdout=info, stderr="")
        return CompletedProcess(argv, 0, stdout=exif, stderr=b"")

    return fake_run


def test_parse_tiff_reads_ascii_and_short_values() -> None:
    values = _parse_tiff(_tiff_block())

    assert values[0x010F] == "ACME"
    assert values[0x0112] == 6


def test_format_value_renders_orientation_and_rationals() -> None:
    assert _format_value("orientation", 6) == "Rotated 90° CW"
    assert _format_value("exposure", 1 / 125) == "1/125 s"
    assert _format_value("aperture", 2.8) == "f/2.8"
    assert _format_value("focal", 24.0) == "24 mm"
    assert _format_value("int", 400) == "400"


def test_read_exif_reads_a_tiff_file(tmp_path) -> None:
    path = tmp_path / "photo.tif"
    path.write_bytes(_tiff_block())

    assert read_exif(str(path)) == [
        ("Camera make", "ACME"),
        ("Orientation", "Rotated 90° CW"),
    ]


def test_read_exif_reads_an_ifd_past_one_megabyte(tmp_path) -> None:
    ifd_offset = 2 * 1024 * 1024
    make_offset = ifd_offset + 2 + 2 * 12 + 4
    header = b"II" + (42).to_bytes(2, "little") + ifd_offset.to_bytes(4, "little")
    entries = (
        (0x010F).to_bytes(2, "little")
        + (2).to_bytes(2, "little")
        + (5).to_bytes(4, "little")
        + make_offset.to_bytes(4, "little")
        + (0x0112).to_bytes(2, "little")
        + (3).to_bytes(2, "little")
        + (1).to_bytes(4, "little")
        + (6).to_bytes(2, "little")
        + b"\x00\x00"
    )
    ifd = (2).to_bytes(2, "little") + entries + (0).to_bytes(4, "little") + b"ACME\x00"
    path = tmp_path / "photo.tif"
    path.write_bytes(header + b"\x00" * (ifd_offset - len(header)) + ifd)

    assert read_exif(str(path)) == [
        ("Camera make", "ACME"),
        ("Orientation", "Rotated 90° CW"),
    ]


def test_read_exif_reads_a_png_with_a_jpeg_prefix(tmp_path) -> None:
    path = tmp_path / "photo.png"
    path.write_bytes(_png_with_exif(40, 30, b"Exif\x00\x00" + _tiff_block()))

    assert read_exif(str(path), "image/png") == [
        ("Camera make", "ACME"),
        ("Orientation", "Rotated 90° CW"),
    ]


def test_read_exif_reads_a_webp_exif_chunk(tmp_path) -> None:
    payload = _tiff_block()
    body = b"WEBP" + b"EXIF" + len(payload).to_bytes(4, "little") + payload
    path = tmp_path / "photo.webp"
    path.write_bytes(b"RIFF" + len(body).to_bytes(4, "little") + body)

    assert read_exif(str(path), "image/webp") == [
        ("Camera make", "ACME"),
        ("Orientation", "Rotated 90° CW"),
    ]


def test_read_exif_uses_djxl_for_a_jxl_file(tmp_path, monkeypatch) -> None:
    info = "JPEG XL image, 64x48, lossy, 8-bit RGB\nBrotli-compressed Exif metadata: 20 bytes\n"
    monkeypatch.setattr("imslim.exif.subprocess.run", _fake_jxl_run(_tiff_block(), info))
    path = tmp_path / "photo.jxl"
    path.write_bytes(b"")

    assert read_exif(str(path), "image/jxl") == [
        ("Camera make", "ACME"),
        ("Orientation", "Rotated 90° CW"),
    ]


def test_read_exif_and_size_reports_the_jxl_size(tmp_path, monkeypatch) -> None:
    info = "JPEG XL image, 5000x4000, lossy, 8-bit RGB\n"
    monkeypatch.setattr("imslim.exif.subprocess.run", _fake_jxl_run(b"", info))
    path = tmp_path / "photo.jxl"
    path.write_bytes(b"")

    size, rows = read_exif_and_size(str(path), "image/jxl")

    assert size == (5000, 4000)
    assert rows == []


def test_read_exif_and_size_decodes_avif_once(tmp_path, monkeypatch) -> None:
    path = tmp_path / "photo.avif"
    path.write_bytes(b"")
    calls: list[str] = []

    def fake_decode_commands(source_mime: str, source: str, destination: str, **_kwargs):
        def write() -> None:
            calls.append(source)
            Path(destination).write_bytes(_png_with_exif(5000, 4000, _tiff_block()))

        return [Command(action=write)]

    monkeypatch.setattr("imslim.exif.decode_commands", fake_decode_commands)

    size, rows = read_exif_and_size(str(path), "image/avif")

    assert size == (5000, 4000)
    assert rows == [
        ("Camera make", "ACME"),
        ("Orientation", "Rotated 90° CW"),
    ]
    assert calls == [str(path)]


def test_read_exif_ignores_non_image_data(tmp_path) -> None:
    path = tmp_path / "notes.txt"
    path.write_bytes(b"not an image")

    assert read_exif(str(path)) == []


def test_jpeg_orientation_reads_the_app1_block(tmp_path) -> None:
    payload = b"Exif\x00\x00" + _tiff_block()
    app1 = b"\xff\xe1" + (len(payload) + 2).to_bytes(2, "big") + payload
    path = tmp_path / "photo.jpg"
    path.write_bytes(b"\xff\xd8" + app1 + b"\xff\xda")

    assert jpeg_orientation(str(path)) == 6


def test_jpeg_orientation_reads_past_a_megabyte_of_segments(tmp_path) -> None:
    payload = b"Exif\x00\x00" + _tiff_block()
    app1 = b"\xff\xe1" + (len(payload) + 2).to_bytes(2, "big") + payload
    filler = (b"\xff\xe5" + (60000).to_bytes(2, "big") + b"x" * 59998) * 18
    path = tmp_path / "photo.jpg"
    path.write_bytes(b"\xff\xd8" + filler + app1 + b"\xff\xda")

    assert jpeg_orientation(str(path)) == 6


def test_jpeg_orientation_defaults_to_normal(tmp_path) -> None:
    path = tmp_path / "photo.jpg"
    path.write_bytes(b"not an image")

    assert jpeg_orientation(str(path)) == 1


def test_parse_tiff_ignores_a_cyclic_exif_ifd() -> None:
    block = bytearray(b"II" + (42).to_bytes(2, "little") + (8).to_bytes(4, "little"))
    block += (1).to_bytes(2, "little")
    block += (0x8769).to_bytes(2, "little") + (4).to_bytes(2, "little")
    block += (1).to_bytes(4, "little") + (8).to_bytes(4, "little")
    block += (0).to_bytes(4, "little")

    values = _parse_tiff(bytes(block))

    assert values[0x8769] == 8
