from PySide6.QtCore import QObject, Signal

from imslim.batch_summary import BatchSummary
from imslim.now import EXIT_FAILED, EXIT_OK, NowRunner, exit_code


def _summary(total: int, compressed: int, skipped: int = 0, failed: int = 0) -> BatchSummary:
    summary = BatchSummary()
    for _ in range(total):
        summary.record_added()
    for _ in range(compressed):
        summary.record_compressed()
    for _ in range(skipped):
        summary.record_skipped()
    for _ in range(failed):
        summary.record_failed()
    return summary


def test_a_finished_batch_exits_zero() -> None:
    assert exit_code(_summary(3, 2, skipped=1)) == EXIT_OK


def test_a_failed_batch_exits_one() -> None:
    assert exit_code(_summary(3, 2, failed=1)) == EXIT_FAILED


def test_a_cancelled_batch_exits_one() -> None:
    # One of three files was never compressed.
    assert exit_code(_summary(3, 2)) == EXIT_FAILED


class _Flow(QObject):
    """Just the signals and calls NowRunner needs, without threads or dialogs."""

    items_added = Signal(list)
    items_ready = Signal()
    batch_started = Signal()
    compression_enabled = Signal(bool)
    summary_changed = Signal()
    no_files = Signal()
    output_folder_error = Signal()
    analyze_failed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.cancelled = False

    def analyze(self, _paths: list[str]) -> None:
        pass

    def start_batch(self, _items: list[object]) -> None:
        pass

    def cancel(self) -> None:
        self.cancelled = True

    def shutdown(self) -> None:
        pass


class _Settings:
    output_folder = ""
    save_method = 0


def test_cancelling_analysis_exits_failed() -> None:
    flow = _Flow()
    runner = NowRunner(_Settings(), flow)  # type: ignore[arg-type]
    runner._cancel()  # pyright: ignore[reportPrivateUsage]
    # The flow emits this when the cancelled analysis stops; there is no batch
    # summary to read, so the code set by _cancel must stand.
    flow.compression_enabled.emit(True)
    assert flow.cancelled
    assert runner._code == EXIT_FAILED  # pyright: ignore[reportPrivateUsage]
