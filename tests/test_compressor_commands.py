"""Exact argv for every encoder: the flag strings the external tools depend on."""

import os

import pytest

from imslim.batch_options import BatchOptions
from imslim.compressors.avif_compressor import AVIFCompressor
from imslim.compressors.gif_compressor import GIFCompressor
from imslim.compressors.jpeg_compressor import JPEGCompressor
from imslim.compressors.jxl_compressor import JXLCompressor
from imslim.compressors.png_compressor import PNGCompressor
from imslim.compressors.svg_compressor import SVGCompressor
from imslim.compressors.webp_compressor import WEBPCompressor
from imslim.formats import FORMAT_DEFAULT_KNOBS, Format
from imslim.result_item import ResultItem

_SOURCE = "photo"
_TMP = "photo.tmp"
_PNG_INTERMEDIATE = "photo.tmp.png"
_JPEG_ENCODED = "photo.tmp.enc.jpg"
_WEBP_INTERMEDIATE = "photo.tmp.src.png"


def _cmd(line: str) -> list[str]:
    """One expected command line, split into argv the way a shell would."""
    return line.split()


# Every knob gets a value no other knob shares, so a flag wired to the wrong
# knob (or replaced by a literal) shows up as a mismatch.
_KNOBS: dict[str, int | bool] = {
    **FORMAT_DEFAULT_KNOBS,
    "png-lossy-level": 42,
    "png-effort": 3,
    "jpg-lossy-level": 42,
    "webp-lossy-level": 42,
    "webp-effort": 3,
    "avif-lossy-level": 42,
    "avif-effort": 4,
    "jxl-lossy-level": 42,
    "jxl-effort": 3,
    "gif-lossy-level": 42,
    "gif-effort": 3,
}

_PNGQ_LOSSY = _cmd(f"pngquant --quality=0-42 -f {_SOURCE} --output {_TMP}")
_PNGQ_LOSSY_STRIP = _cmd(f"pngquant --quality=0-42 -f --strip {_SOURCE} --output {_TMP}")
_OXI_LOSSY = _cmd(f"oxipng -o 3 -i 0 --preserve {_TMP} --out {_TMP}")
_OXI_SOURCE = _cmd(f"oxipng -o 3 -i 0 --preserve {_SOURCE} --out {_TMP}")
_OXI_LOSSY_STRIP = _cmd(f"oxipng -o 3 -i 0 --strip safe --preserve {_TMP} --out {_TMP}")
_OXI_SOURCE_STRIP = _cmd(f"oxipng -o 3 -i 0 --strip safe --preserve {_SOURCE} --out {_TMP}")
_PNG_LOSSY_KEEP = [_PNGQ_LOSSY, _OXI_LOSSY]
_PNG_LOSSY_STRIP = [_PNGQ_LOSSY_STRIP, _OXI_LOSSY_STRIP]
_PNG_LOSSLESS_KEEP = [_OXI_SOURCE]
_PNG_LOSSLESS_STRIP = [_OXI_SOURCE_STRIP]

_JPEGTRAN_KEEP = _cmd(f"jpegtran -optimize -copy all -outfile {_TMP} {_SOURCE}")
_JPEGTRAN_ICC = _cmd(f"jpegtran -optimize -copy icc -outfile {_TMP} {_SOURCE}")
_JPEGTRAN_ENCODED_ICC = _cmd(f"jpegtran -copy icc -outfile {_TMP} {_JPEG_ENCODED}")
_DJPEGLI = _cmd(f"djpegli {_SOURCE} {_PNG_INTERMEDIATE}")
_CJPEGLI_KEEP = _cmd(f"cjpegli {_PNG_INTERMEDIATE} {_TMP} --quality 42 --progressive_level=0")
_CJPEGLI_STRIP = _cmd(
    f"cjpegli {_PNG_INTERMEDIATE} {_JPEG_ENCODED} --quality 42 --progressive_level=0"
)
_JPEG_LOSSY_KEEP = [_DJPEGLI, _CJPEGLI_KEEP, None]
_JPEG_LOSSY_STRIP = [_DJPEGLI, _CJPEGLI_STRIP, _JPEGTRAN_ENCODED_ICC]

_CWEBP_LOSSY = _cmd(f"cwebp -metadata all -mt -m 3 -q 42 -o {_TMP} {_SOURCE}")
_CWEBP_LOSSY_ICC = _cmd(f"cwebp -metadata icc -mt -m 3 -q 42 -o {_TMP} {_SOURCE}")
_CWEBP_LL = _cmd(f"cwebp -metadata all -lossless -mt -m 3 -q 100 -o {_TMP} {_SOURCE}")
_CWEBP_LL_ICC = _cmd(f"cwebp -metadata icc -lossless -mt -m 3 -q 100 -o {_TMP} {_SOURCE}")
_CWEBP_BMP = _cmd(f"cwebp -metadata all -mt -m 3 -q 42 -o {_TMP} {_WEBP_INTERMEDIATE}")

_AVIF_LOSSY = _cmd(f"avifenc -q 42 -a tune=iq -d 10 --speed 6 {_SOURCE} {_TMP}")
_AVIF_LOSSY_STRIP = _cmd(
    f"avifenc --ignore-exif --ignore-xmp -q 42 -a tune=iq -d 10 --speed 6 {_SOURCE} {_TMP}"
)
_AVIF_LL = _cmd(f"avifenc --lossless --speed 6 {_SOURCE} {_TMP}")
_AVIF_LL_STRIP = _cmd(f"avifenc --ignore-exif --ignore-xmp --lossless --speed 6 {_SOURCE} {_TMP}")

_CJXL_LOSSY = _cmd(f"cjxl -q 42 -e 3 {_SOURCE} {_TMP}")
_CJXL_LOSSLESS = _cmd(f"cjxl -q 100 -e 3 {_SOURCE} {_TMP}")
_DJXL_DECODE = _cmd(f"djxl {_SOURCE} {_PNG_INTERMEDIATE}")
_DJXL_EXIF = _cmd(f"djxl {_SOURCE} - --output_format exif")
_DJXL_XMP = _cmd(f"djxl {_SOURCE} - --output_format xmp")
_DJXL_JUMBF = _cmd(f"djxl {_SOURCE} - --output_format jumbf")
_CJXL_SIDECARS = _cmd(
    "cjxl -q 42 -e 3 "
    "-x exif=photo.tmp.exif -x xmp=photo.tmp.xmp -x jumbf=photo.tmp.jumbf "
    f"{_PNG_INTERMEDIATE} {_TMP}"
)
_JXL_WITH_SIDECARS = [_DJXL_DECODE, _DJXL_EXIF, _DJXL_XMP, _DJXL_JUMBF, _CJXL_SIDECARS]
_JXL_SIDECAR_PATHS = [None, "photo.tmp.exif", "photo.tmp.xmp", "photo.tmp.jumbf", None]

_GIF_LOSSY = _cmd(f"gifsicle --optimize=3 --lossy=42 -o {_TMP} {_SOURCE}")
_GIF_LOSSY_STRIP = _cmd(
    f"gifsicle --optimize=3 --lossy=42 --no-extensions --no-comments --no-names -o {_TMP} {_SOURCE}"
)
_GIF_LOSSLESS = _cmd(f"gifsicle --optimize=3 -o {_TMP} {_SOURCE}")
_GIF_ANIMATED_STRIP = _cmd(f"gifsicle --optimize=3 --no-comments --no-names -o {_TMP} {_SOURCE}")


def _options(
    target_format: Format,
    lossy: bool,
    metadata: bool = True,
    file_attributes: bool = True,
    knobs: dict[str, int | bool] | None = None,
) -> BatchOptions:
    return BatchOptions(
        save_method=0,
        target_format=target_format,
        output_folder="",
        recursive=False,
        lossy=lossy,
        metadata=metadata,
        file_attributes=file_attributes,
        compression_timeout=60,
        knobs=_KNOBS if knobs is None else knobs,
    )


def _item(mime_type: str) -> ResultItem:
    return ResultItem(filename=_SOURCE, mime_type=mime_type, tmp_filename=_TMP)


def _argv(commands) -> list[list[str] | None]:
    return [command.argv for command in commands]


def _tool_argv(commands, tool: str) -> list[str]:
    for command in commands:
        if command.argv is not None and command.argv[0] == tool:
            return command.argv
    raise AssertionError(f"no {tool} command")


@pytest.mark.parametrize(
    ("lossy", "metadata", "expected"),
    [
        pytest.param(True, True, _PNG_LOSSY_KEEP, id="lossy-keep"),
        pytest.param(True, False, _PNG_LOSSY_STRIP, id="lossy-strip"),
        pytest.param(False, True, _PNG_LOSSLESS_KEEP, id="lossless-keep"),
        pytest.param(False, False, _PNG_LOSSLESS_STRIP, id="lossless-strip"),
    ],
)
def test_png_command(lossy: bool, metadata: bool, expected: list[list[str]]) -> None:
    options = _options(Format.PNG, lossy, metadata)

    assert _argv(PNGCompressor().commands(_item("image/png"), options)) == expected


def test_png_drops_preserve_when_file_attributes_off() -> None:
    options = _options(Format.PNG, lossy=False, file_attributes=False)
    argv = _argv(PNGCompressor().commands(_item("image/png"), options))

    assert "--preserve" not in argv[0]


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        pytest.param(True, _JPEGTRAN_KEEP, id="keep-metadata"),
        pytest.param(False, _JPEGTRAN_ICC, id="strip-metadata"),
    ],
)
def test_jpeg_lossless_command(metadata: bool, expected: list[str]) -> None:
    options = _options(Format.JPEG, lossy=False, metadata=metadata)
    commands = JPEGCompressor().commands(_item("image/jpeg"), options)

    assert _argv(commands) == [expected]


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        pytest.param(True, _JPEG_LOSSY_KEEP, id="keep-metadata"),
        pytest.param(False, _JPEG_LOSSY_STRIP, id="strip-metadata"),
    ],
)
def test_jpeg_lossy_command(metadata: bool, expected: list[list[str] | None]) -> None:
    options = _options(Format.JPEG, lossy=True, metadata=metadata)
    commands = JPEGCompressor().commands(_item("image/jpeg"), options)

    assert _argv(commands) == expected


def test_jpeg_lossy_keep_metadata_copies_exif_back() -> None:
    options = _options(Format.JPEG, lossy=True)
    commands = JPEGCompressor().commands(_item("image/jpeg"), options)

    assert commands[-1].argv is None
    assert commands[-1].action is not None


@pytest.mark.parametrize(
    ("lossy", "tool", "expected"),
    [
        (False, "jpegtran", "-progressive"),
        (True, "cjpegli", "--progressive_level=2"),
    ],
)
def test_jpeg_progressive_flag(lossy: bool, tool: str, expected: str) -> None:
    options = _options(Format.JPEG, lossy, knobs={**_KNOBS, "jpg-progressive": True})
    commands = JPEGCompressor().commands(_item("image/jpeg"), options)

    assert expected in _tool_argv(commands, tool)


@pytest.mark.parametrize(
    ("lossy", "metadata", "expected"),
    [
        pytest.param(True, True, _CWEBP_LOSSY, id="lossy-keep"),
        pytest.param(True, False, _CWEBP_LOSSY_ICC, id="lossy-strip"),
        pytest.param(False, True, _CWEBP_LL, id="lossless-keep"),
        pytest.param(False, False, _CWEBP_LL_ICC, id="lossless-strip"),
    ],
)
def test_webp_command(lossy: bool, metadata: bool, expected: list[str]) -> None:
    options = _options(Format.WEBP, lossy, metadata)
    commands = WEBPCompressor().commands(_item("image/png"), options)

    assert _argv(commands) == [expected]


def test_webp_decodes_bmp_source_first() -> None:
    # BMP/TIFF have no target format of their own: they re-encode to WebP with
    # the target kept, so cwebp reads the decoder's intermediate PNG.
    options = _options(Format.KEEP, lossy=True)
    commands = WEBPCompressor().commands(_item("image/bmp"), options)

    assert commands[0].argv is None
    assert commands[0].action is not None
    assert commands[1].argv == _CWEBP_BMP


@pytest.mark.parametrize(
    ("lossy", "metadata", "expected"),
    [
        pytest.param(True, True, _AVIF_LOSSY, id="lossy-keep"),
        pytest.param(True, False, _AVIF_LOSSY_STRIP, id="lossy-strip"),
        pytest.param(False, True, _AVIF_LL, id="lossless-keep"),
        pytest.param(False, False, _AVIF_LL_STRIP, id="lossless-strip"),
    ],
)
def test_avif_command(lossy: bool, metadata: bool, expected: list[str]) -> None:
    options = _options(Format.AVIF, lossy, metadata)
    commands = AVIFCompressor().commands(_item("image/png"), options)

    assert _argv(commands) == [expected]


@pytest.mark.parametrize(
    ("lossy", "expected"),
    [
        pytest.param(True, _CJXL_LOSSY, id="lossy"),
        pytest.param(False, _CJXL_LOSSLESS, id="lossless"),
    ],
)
def test_jxl_quality_ignores_metadata(lossy: bool, expected: list[str]) -> None:
    for metadata in (True, False):
        options = _options(Format.JXL, lossy, metadata)
        commands = JXLCompressor().commands(_item("image/png"), options)

        assert _argv(commands) == [expected]


def test_jxl_extracts_metadata_sidecars_for_non_png_source() -> None:
    # A native JXL source is not the 'keep' target's conversion, so the encoder
    # decodes it itself and must re-inject EXIF/XMP/JUMBF as sidecars.
    options = _options(Format.KEEP, lossy=True)
    commands = JXLCompressor().commands(_item("image/jxl"), options)

    assert _argv(commands) == _JXL_WITH_SIDECARS
    assert [command.stdout_path for command in commands] == _JXL_SIDECAR_PATHS


def test_jxl_prunes_sidecar_hints_that_were_not_produced(tmp_path) -> None:
    produced = tmp_path / "photo.tmp.exif"
    produced.write_bytes(b"exif")
    options = _options(Format.JXL, lossy=True)
    command = JXLCompressor().build_command(_item("image/png"), options, _SOURCE)[0]
    argv = ["cjxl", "-x", f"exif={produced}", "-x", f"xmp={tmp_path / 'photo.tmp.xmp'}", _TMP]

    assert command.adapt is not None
    assert command.adapt(argv) == ["cjxl", "-x", f"exif={produced}", _TMP]


@pytest.mark.parametrize(
    ("animated", "lossy", "metadata", "expected"),
    [
        pytest.param(False, True, True, _GIF_LOSSY, id="static-lossy"),
        pytest.param(False, True, False, _GIF_LOSSY_STRIP, id="static-lossy-strip"),
        pytest.param(False, False, True, _GIF_LOSSLESS, id="static-lossless"),
        pytest.param(True, True, False, _GIF_ANIMATED_STRIP, id="animated-strip"),
    ],
)
def test_gif_command(
    animated: bool,
    lossy: bool,
    metadata: bool,
    expected: list[str],
) -> None:
    item = _item("image/gif")
    item.is_animated = animated
    options = _options(Format.KEEP, lossy, metadata)
    commands = GIFCompressor().commands(item, options)

    assert _argv(commands) == [expected]


@pytest.mark.parametrize(
    ("maximum", "expected_name"),
    [(False, "svgo.config.cjs"), (True, "svgo.maximum.config.cjs")],
)
def test_svg_command(maximum: bool, expected_name: str) -> None:
    options = _options(Format.KEEP, lossy=True, knobs={**_KNOBS, "svg-maximum-level": maximum})
    argv = _argv(SVGCompressor().commands(_item("image/svg+xml"), options))[0]

    assert argv[:2] == ["svgo", "--config"]
    assert os.path.basename(argv[2]) == expected_name
    assert argv[3:] == ["-i", _SOURCE, "-o", _TMP]
