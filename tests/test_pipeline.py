"""The pipeline's outcome branches: skip, cancel, failure cleanup."""

from pathlib import Path

from imslim.batch_options import BatchOptions
from imslim.command_runner import CompressionContext
from imslim.commands import Command
from imslim.compressor import Compressor
from imslim.formats import FORMAT_DEFAULT_KNOBS, CompressorType, Format
from imslim.pipeline import CompressionPipeline
from imslim.result_item import ResultItem, ResultState
from imslim.settings_manager import SAVE_NEXT_TO_ORIGINAL


class _FakeCompressor(Compressor):
    def __init__(self, commands: list[Command]) -> None:
        self._commands = commands

    @classmethod
    def get_file_type(cls) -> CompressorType:
        return CompressorType.PNG

    def build_command(
        self, result_item: ResultItem, options: BatchOptions, input_path: str
    ) -> list[Command]:
        return self._commands


def _options() -> BatchOptions:
    return BatchOptions(
        save_method=SAVE_NEXT_TO_ORIGINAL,
        target_format=Format.KEEP,
        output_folder="",
        recursive=False,
        lossy=True,
        metadata=True,
        file_attributes=False,
        compression_timeout=60,
        knobs=FORMAT_DEFAULT_KNOBS,
    )


def _item(tmp_path: Path) -> ResultItem:
    source = tmp_path / "photo.png"
    source.write_bytes(b"x" * 100)
    return ResultItem(
        filename=str(source),
        new_filename=str(tmp_path / "photo.imslim.20240101000000.png"),
        tmp_filename=str(tmp_path / ".photo.tmp"),
        mime_type="image/png",
        size=100,
    )


def _write_command(path: str, payload: bytes) -> Command:
    def write() -> None:
        Path(path).write_bytes(payload)

    return Command(action=write, temp_files=(path,))


def _run(commands: list[Command], item: ResultItem, context: CompressionContext) -> None:
    CompressionPipeline().run(
        _FakeCompressor(commands), item, lambda _item: None, context, _options()
    )


def test_skip_keeps_the_original_and_removes_the_temp(tmp_path: Path) -> None:
    item = _item(tmp_path)
    context = CompressionContext()

    _run([_write_command(item.tmp_filename, b"x" * 200)], item, context)

    assert item.state is ResultState.SKIPPED
    assert Path(item.filename).read_bytes() == b"x" * 100
    assert not Path(item.new_filename).exists()
    assert not Path(item.tmp_filename).exists()


def test_cancel_marks_the_item_and_does_no_work(tmp_path: Path) -> None:
    item = _item(tmp_path)
    context = CompressionContext()
    context.cancel()

    _run([_write_command(item.tmp_filename, b"x" * 10)], item, context)

    assert item.state is ResultState.CANCELLED
    assert not Path(item.tmp_filename).exists()


def test_failure_marks_the_item_and_cleans_temp_files(tmp_path: Path) -> None:
    item = _item(tmp_path)
    sidecar = str(tmp_path / ".sidecar")
    context = CompressionContext()

    def fail() -> None:
        Path(sidecar).write_bytes(b"partial")
        raise OSError("tool failed")

    _run([Command(action=fail, temp_files=(sidecar,))], item, context)

    assert item.state is ResultState.ERROR
    assert item.error_message
    assert Path(item.filename).read_bytes() == b"x" * 100
    assert not Path(sidecar).exists()


def test_optional_command_failure_is_ignored(tmp_path: Path) -> None:
    item = _item(tmp_path)
    sidecar = str(tmp_path / ".sidecar")
    context = CompressionContext()

    def fail() -> None:
        raise OSError("optional step failed")

    commands = [
        Command(action=fail, ignore_errors=True, temp_files=(sidecar,)),
        _write_command(item.tmp_filename, b"x" * 50),
    ]

    _run(commands, item, context)

    assert item.state is ResultState.DONE
    assert Path(item.new_filename).read_bytes() == b"x" * 50
