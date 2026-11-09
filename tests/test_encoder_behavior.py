"""Behavior tests that run the bundled encoders on tiny fixtures.

The argv tests in `test_compressor_commands.py` cannot catch a tool that
ignores metadata or orientation, so these tests execute the real commands.
They skip when the bundled tools were not built.
"""

import platform
import shutil
import struct
import subprocess
import zlib
from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtGui import QImage

from imslim import binary_resolver
from imslim.batch_options import BatchOptions
from imslim.binary_resolver import resolve_tool
from imslim.commands import Command
from imslim.compressors.jpeg_compressor import JPEGCompressor
from imslim.compressors.jxl_compressor import JXLCompressor
from imslim.compressors.svg_compressor import SVGCompressor
from imslim.compressors.webp_compressor import WEBPCompressor
from imslim.conversion import decode_commands
from imslim.formats import FORMAT_DEFAULT_KNOBS, Format
from imslim.result_item import ResultItem

_BIN = binary_resolver.BIN_DIR / f"{platform.system().lower()}-{platform.machine().lower()}"
_EXIF_HEADER = b"Exif\x00\x00"


@pytest.fixture(autouse=True)
def _real_tools(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    def resolve(name: str) -> str | None:
        candidate = _BIN / name
        if candidate.is_file():
            return str(candidate)
        return shutil.which(name)

    binary_resolver._RESOLVED.clear()
    monkeypatch.setattr("imslim.binary_resolver._resolve", resolve)
    yield
    binary_resolver._RESOLVED.clear()


def _require(name: str) -> str:
    try:
        return resolve_tool(name)
    except FileNotFoundError:
        pytest.skip(f"{name} is not available")


def _options(target: Format, lossy: bool, metadata: bool = True) -> BatchOptions:
    return BatchOptions(
        save_method=0,
        target_format=target,
        output_folder="",
        recursive=False,
        lossy=lossy,
        metadata=metadata,
        file_attributes=True,
        compression_timeout=60,
        knobs=FORMAT_DEFAULT_KNOBS,
    )


def _run(command: Command) -> None:
    if command.action is not None:
        command.action()
    elif command.argv is not None:
        subprocess.run(command.argv, check=True, capture_output=True)


def _exif_payload(orientation: int = 1) -> bytes:
    tiff = (
        b"II*\x00"
        + (8).to_bytes(4, "little")
        + (1).to_bytes(2, "little")
        + (0x0112).to_bytes(2, "little")
        + (3).to_bytes(2, "little")
        + (1).to_bytes(4, "little")
        + orientation.to_bytes(2, "little")
        + b"\x00\x00"
        + (0).to_bytes(4, "little")
    )
    return _EXIF_HEADER + tiff


def _jpeg_with_orientation(path: Path, orientation: int) -> None:
    app1 = (
        b"\xff\xe1" + (len(payload := _exif_payload(orientation)) + 2).to_bytes(2, "big") + payload
    )
    data = path.read_bytes()
    path.write_bytes(data[:2] + app1 + data[2:])


def _pattern_png(path: Path) -> None:
    image = QImage(4, 2, QImage.Format.Format_RGB32)
    for x in range(4):
        image.setPixelColor(x, 0, 0xFFFF0000)
        image.setPixelColor(x, 1, 0xFF0000FF)
    assert image.save(str(path), "PNG")


def _png_with_exif(path: Path, payload: bytes) -> None:
    _pattern_png(path)
    data = path.read_bytes()
    chunk = (
        struct.pack(">I", len(payload))
        + b"eXIf"
        + payload
        + struct.pack(">I", zlib.crc32(b"eXIf" + payload) & 0xFFFFFFFF)
    )
    iend = data.rfind(b"IEND") - 4
    path.write_bytes(data[:iend] + chunk + data[iend:])


def _pattern_jpeg(path: Path, orientation: int) -> None:
    image = QImage(4, 2, QImage.Format.Format_RGB32)
    for x in range(4):
        image.setPixelColor(x, 0, 0xFFFF0000)
        image.setPixelColor(x, 1, 0xFF0000FF)
    assert image.save(str(path), "JPEG")
    _jpeg_with_orientation(path, orientation)


def _size(path: Path) -> tuple[int, int]:
    image = QImage(str(path))
    assert not image.isNull()
    return image.width(), image.height()


def test_jpeg_conversion_applies_exif_orientation(tmp_path: Path) -> None:
    source = tmp_path / "photo.jpg"
    _pattern_jpeg(source, 6)
    output = tmp_path / "photo.png"

    for command in decode_commands("image/jpeg", str(source), str(output), apply_orientation=True):
        _run(command)

    assert _size(output) == (2, 4)


def test_lossless_jpeg_strips_and_rotates(tmp_path: Path) -> None:
    _require("jpegtran")
    source = tmp_path / "photo.jpg"
    _pattern_jpeg(source, 6)
    output = tmp_path / "out.jpg"
    item = ResultItem(filename=str(source), mime_type="image/jpeg", tmp_filename=str(output))

    for command in JPEGCompressor().build_command(
        item, _options(Format.JPEG, lossy=False, metadata=False), str(source)
    ):
        _run(command)

    assert _size(output) == (2, 4)
    assert _EXIF_HEADER not in output.read_bytes()


def test_webp_strips_metadata_but_keeps_orientation(tmp_path: Path) -> None:
    _require("cwebp")
    source = tmp_path / "photo.jpg"
    _pattern_jpeg(source, 6)
    output = tmp_path / "out.webp"
    item = ResultItem(filename=str(source), mime_type="image/jpeg", tmp_filename=str(output))

    for command in WEBPCompressor().commands(
        item, _options(Format.WEBP, lossy=True, metadata=False)
    ):
        _run(command)

    assert _size(output) == (2, 4)


def test_avif_exif_survives_a_reencode(tmp_path: Path) -> None:
    avifenc = _require("avifenc")
    avifdec = _require("avifdec")
    source_png = tmp_path / "source.png"
    _pattern_png(source_png)
    exif = tmp_path / "exif.bin"
    exif.write_bytes(_exif_payload(1))
    source_avif = tmp_path / "source.avif"
    subprocess.run(
        [avifenc, "--exif", str(exif), "-q", "50", str(source_png), str(source_avif)],
        check=True,
        capture_output=True,
    )
    intermediate = tmp_path / "intermediate.png"
    for command in decode_commands("image/avif", str(source_avif), str(intermediate)):
        _run(command)
    output = tmp_path / "out.avif"
    subprocess.run(
        [avifenc, "-q", "50", str(intermediate), str(output)],
        check=True,
        capture_output=True,
    )

    info = subprocess.run(
        [avifdec, "--info", str(output)], check=True, capture_output=True, text=True
    ).stdout
    assert "Exif Metadata  : Present" in info


def test_jxl_metadata_off_strips_exif(tmp_path: Path) -> None:
    _require("cjxl")
    djxl = _require("djxl")
    source = tmp_path / "source.png"
    _png_with_exif(source, _exif_payload(1))
    item = ResultItem(
        filename=str(source),
        mime_type="image/png",
        tmp_filename=str(tmp_path / "out.jxl"),
    )

    for command in JXLCompressor().build_command(
        item, _options(Format.JXL, lossy=True, metadata=False), str(source)
    ):
        _run(command)

    result = subprocess.run(
        [djxl, item.tmp_filename, "-", "--output_format", "exif"],
        check=True,
        capture_output=True,
    )
    assert result.stdout == b""


def test_svg_keeps_metadata_when_requested(tmp_path: Path) -> None:
    _require("svgo")
    source = tmp_path / "source.svg"
    source.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
        '<metadata><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"/>'
        '</metadata><rect width="10" height="10" fill="red"/></svg>'
    )
    for metadata, expected in ((True, True), (False, False)):
        output = tmp_path / f"out-{metadata}.svg"
        item = ResultItem(filename=str(source), mime_type="image/svg+xml", tmp_filename=str(output))
        for command in SVGCompressor().build_command(
            item, _options(Format.KEEP, lossy=True, metadata=metadata), str(source)
        ):
            _run(command)
        assert ("<metadata>" in output.read_text()) is expected
