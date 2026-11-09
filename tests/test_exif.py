from imslim.exif import _format_value, _parse_tiff, jpeg_orientation, read_exif


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
