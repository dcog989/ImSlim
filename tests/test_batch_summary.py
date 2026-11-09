from imslim.batch_summary import BatchSummary


def test_summary_counts_every_outcome() -> None:
    summary = BatchSummary()
    for _ in range(3):
        summary.record_added()

    summary.record_done()
    summary.record_compressed()
    summary.record_done()
    summary.record_skipped()
    summary.record_done()
    summary.record_failed()

    assert summary.total == 3
    assert summary.done == 3
    assert summary.compressed == 1
    assert summary.skipped == 1
    assert summary.failed == 1
