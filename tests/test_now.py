from imslim.batch_summary import BatchSummary
from imslim.now import EXIT_FAILED, EXIT_OK, exit_code


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
