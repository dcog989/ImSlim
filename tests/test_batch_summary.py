from imslim.batch_summary import BatchSummary


def test_summary_text_counts_every_outcome() -> None:
    summary = BatchSummary()
    for _ in range(3):
        summary.record_added()

    summary.record_done()
    summary.record_compressed(2048)
    summary.record_done()
    summary.record_skipped()
    summary.record_done()
    summary.record_failed()

    text = summary.text()

    assert "3 of 3 images done" in text
    assert "1 compressed" in text
    assert "2.0 KiB saved" in text
    assert "1 skipped" in text
    assert "1 failed" in text


def test_converting_summary_reports_conversions_not_size() -> None:
    summary = BatchSummary()
    summary.record_added()
    summary.record_done()
    summary.record_compressed(2048)

    text = summary.text(converting=True)

    assert "1 converted" in text
    assert "saved" not in text
