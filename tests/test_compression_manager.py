"""The submission loop must keep every worker fed and cancel cleanly."""

import threading
from pathlib import Path

from imslim.batch_options import BatchOptions
from imslim.command_runner import CompressionContext
from imslim.compression_manager import CompressionManager
from imslim.formats import FORMAT_DEFAULT_KNOBS, CompressorType, Format
from imslim.result_item import ResultItem, ResultState
from imslim.settings_manager import SAVE_NEXT_TO_ORIGINAL


class _FakePipeline:
    """Records start order and blocks the first item on a released gate."""

    def __init__(self, fast_total: int) -> None:
        self.started: list[str] = []
        self.lock: threading.Lock = threading.Lock()
        self.slow_started: threading.Event = threading.Event()
        self.release_slow: threading.Event = threading.Event()
        self.fast_all: threading.Event = threading.Event()
        self.fast_total: int = fast_total
        self.fast_started: int = 0

    def run(self, *_args: object) -> None:
        item = _args[1]
        assert isinstance(item, ResultItem)
        with self.lock:
            self.started.append(item.filename)
        if item.filename.endswith("slow.png"):
            self.slow_started.set()
            self.release_slow.wait(5)
            return
        with self.lock:
            self.fast_started += 1
            if self.fast_started >= self.fast_total:
                self.fast_all.set()


def _options() -> BatchOptions:
    return BatchOptions(
        save_method=SAVE_NEXT_TO_ORIGINAL,
        target_format=Format.KEEP,
        output_folder="",
        recursive=False,
        lossy=False,
        metadata=True,
        file_attributes=False,
        compression_timeout=30,
        knobs=FORMAT_DEFAULT_KNOBS,
    )


def _item(tmp_path: Path, name: str) -> ResultItem:
    source = tmp_path / name
    source.write_bytes(b"x")
    return ResultItem(filename=str(source), mime_type="image/png", size=1)


def _manager(pipeline: _FakePipeline) -> CompressionManager:
    manager = CompressionManager()
    manager.compressors[CompressorType.PNG] = object()  # type: ignore[assignment]
    manager._pipeline = pipeline  # type: ignore[assignment]
    return manager


def test_a_slow_first_file_does_not_block_later_submissions(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("imslim.compression_manager.worker_count", lambda minimum=1: 2)
    items = [_item(tmp_path, "slow.png")]
    items += [_item(tmp_path, f"fast{index}.png") for index in range(5)]
    pipeline = _FakePipeline(fast_total=5)
    manager = _manager(pipeline)

    thread = threading.Thread(
        target=manager._compress,
        args=(items, _options(), lambda _item: None, lambda _enabled: None, CompressionContext()),
    )
    thread.start()
    try:
        assert pipeline.slow_started.wait(2)
        fast_before_release = pipeline.fast_all.wait(2)
    finally:
        pipeline.release_slow.set()
        thread.join(5)

    assert not thread.is_alive()
    assert fast_before_release, "the slow first file held up submission"
    assert len(pipeline.started) == 6


def test_cancelling_before_prepare_marks_every_item_cancelled(tmp_path: Path) -> None:
    items = [_item(tmp_path, f"photo{index}.png") for index in range(3)]
    context = CompressionContext()
    context.cancel()
    updates: list[ResultItem] = []

    _manager(_FakePipeline(fast_total=0))._compress(
        items, _options(), updates.append, lambda _enabled: None, context
    )

    assert [item.state for item in items] == [ResultState.CANCELLED] * 3
    assert len(updates) == 3
