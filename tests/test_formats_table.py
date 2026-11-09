from imslim.binary_resolver import KNOWN_TOOLS
from imslim.compressors import ALL_COMPRESSORS
from imslim.formats import (
    CONFIGURED_COMPRESSOR_TYPES,
    DECODER_TOOLS,
    FORMAT_SPECS,
    Format,
    is_format_change,
)


def test_decoders_are_known_tools() -> None:
    assert set(DECODER_TOOLS.values()) <= set(KNOWN_TOOLS)


def test_every_spec_has_a_mime_and_an_extension() -> None:
    # Drag-and-drop uses MIME types while folder scans use extensions, so a
    # spec missing either accepts files one way and rejects them the other.
    for spec in FORMAT_SPECS:
        assert spec.source_mimes, spec.key
        assert spec.source_extensions, spec.key


def test_every_configured_compressor_is_registered() -> None:
    assert {compressor.get_file_type() for compressor in ALL_COMPRESSORS} == set(
        CONFIGURED_COMPRESSOR_TYPES
    )


def test_format_change_uses_the_written_format() -> None:
    assert not is_format_change("image/jpeg", Format.JPEG)
    assert not is_format_change("image/png", Format.KEEP)
    assert is_format_change("image/jpeg", Format.PNG)
    assert is_format_change("image/bmp", Format.KEEP)
