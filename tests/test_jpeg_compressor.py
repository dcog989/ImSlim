import pytest

from imslim.batch_options import BatchOptions
from imslim.commands import Command
from imslim.compressors.jpeg_compressor import JPEGCompressor
from imslim.formats import FORMAT_DEFAULT_KNOBS, Format
from imslim.result_item import ResultItem


def _options(lossy: bool) -> BatchOptions:
    return BatchOptions(
        save_method=0,
        target_format=Format.JPEG,
        output_folder="",
        recursive=False,
        lossy=lossy,
        metadata=True,
        file_attributes=True,
        compression_timeout=60,
        knobs=FORMAT_DEFAULT_KNOBS,
    )


def _item(mime_type: str) -> ResultItem:
    item = ResultItem()
    item.filename = "photo"
    item.mime_type = mime_type
    item.tmp_filename = "photo.tmp"
    return item


def _argv(commands: list[Command], tool: str) -> list[str]:
    for command in commands:
        if command.argv is not None and command.argv[0].endswith(tool):
            return command.argv
    raise AssertionError("expected command missing")


@pytest.mark.parametrize(
    ("mime_type", "lossy", "expected"),
    [
        ("image/png", False, "100"),  # a lossless request cannot use the lossy knob
        ("image/png", True, "90"),  # the lossy knob's default
        ("image/jpeg", True, "90"),
    ],
)
def test_reencode_quality(mime_type: str, lossy: bool, expected: str) -> None:
    argv = _argv(JPEGCompressor().commands(_item(mime_type), _options(lossy)), "cjpegli")

    assert argv[argv.index("--quality") + 1] == expected


def test_lossless_jpeg_source_still_uses_jpegtran() -> None:
    # Only a non-JPEG source re-encodes; a JPEG source stays a lossless copy.
    commands = JPEGCompressor().commands(_item("image/jpeg"), _options(lossy=False))

    assert len(commands) == 1
    assert "-copy" in _argv(commands, "jpegtran")
