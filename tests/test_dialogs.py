from PySide6.QtWidgets import QApplication

from imslim.batch_summary import BatchSummary
from imslim.dialogs import _MAX_LISTED, CompletionDialog, _elapsed_text, batch_size_totals
from imslim.result_item import ResultItem, ResultState


def _item(size: int, new_size: int = 0, state: ResultState = ResultState.DONE) -> ResultItem:
    return ResultItem(size=size, new_size=new_size, state=state)


def test_batch_size_totals_keeps_a_larger_output() -> None:
    assert batch_size_totals([_item(100, 150)]) == (100, 150)


def test_batch_size_totals_keeps_unprocessed_files_at_original_size() -> None:
    items = [
        _item(100, 50),
        _item(200, state=ResultState.SKIPPED),
        _item(300, state=ResultState.CANCELLED),
    ]
    assert batch_size_totals(items) == (600, 550)


def test_batch_size_totals_excludes_failed_items() -> None:
    items = [_item(100, 50), _item(999, state=ResultState.ERROR)]
    assert batch_size_totals(items) == (100, 50)


def test_elapsed_text_carries_rounded_seconds_into_minutes() -> None:
    assert _elapsed_text(119.6) == "2 min 0 s"
    assert _elapsed_text(3599.6) == "60 min 0 s"


def test_completion_reports_cancelled_items() -> None:
    summary = BatchSummary()
    summary.total = 2
    summary.compressed = 1
    items = [
        ResultItem(filename="ok.png", size=100, new_size=50, state=ResultState.DONE),
        ResultItem(filename="stopped.png", size=100, state=ResultState.CANCELLED),
    ]

    dialog = CompletionDialog(summary, items, 1.0, "")

    assert dialog.headline.text() == "Compression cancelled"
    assert dialog.list.item(1).text() == "Cancelled: stopped.png"


def test_completion_copies_the_summary_and_every_row() -> None:
    summary = BatchSummary()
    summary.total = 2
    summary.failed = 1
    items = [
        ResultItem(filename="/p/ok.png", size=100, new_size=50, state=ResultState.DONE),
        ResultItem(
            filename="/p/bad.png",
            size=100,
            state=ResultState.ERROR,
            error_message="boom",
        ),
    ]

    dialog = CompletionDialog(summary, items, 1.0, "")
    dialog._copy_results()

    text = QApplication.clipboard().text()
    assert text.splitlines()[0] == "Compression finished"
    assert "Images: 2" in text
    assert "Failed: 1" in text
    assert "ok.png — 50%" in text
    assert "Failed: bad.png — boom" in text


def test_completion_dialog_saves_and_restores_its_geometry() -> None:
    class _Settings:
        completion_geometry = b""

    summary = BatchSummary()
    summary.total = 1
    settings = _Settings()
    dialog = CompletionDialog(summary, [], 1.0, "", settings=settings)  # type: ignore[arg-type]
    dialog.show()
    dialog.resize(700, 480)
    assert dialog.close()

    assert settings.completion_geometry

    again = CompletionDialog(summary, [], 1.0, "", settings=settings)  # type: ignore[arg-type]
    assert again.width() == 700


def test_completion_lists_a_skipped_file_by_name_first() -> None:
    summary = BatchSummary()
    summary.total = 1
    summary.skipped = 1
    items = [ResultItem(filename="/p/big.png", size=100, state=ResultState.SKIPPED)]

    dialog = CompletionDialog(summary, items, 1.0, "")

    assert dialog._row_text(items[0]) == "big.png — Skipped"


def test_completion_list_shows_failures_first_and_caps_rows() -> None:
    summary = BatchSummary()
    summary.total = 300
    summary.failed = 250
    summary.compressed = 50
    items = [
        ResultItem(
            filename=f"bad{index}.png",
            size=100,
            state=ResultState.ERROR,
            error_message="boom",
        )
        for index in range(250)
    ]
    items += [
        ResultItem(filename=f"ok{index}.png", size=100, new_size=50, state=ResultState.DONE)
        for index in range(50)
    ]

    dialog = CompletionDialog(summary, items, 1.0, "")

    assert dialog.list.count() == _MAX_LISTED + 1
    for index in range(_MAX_LISTED):
        assert dialog.list.item(index).text().startswith("Failed:")
    assert dialog.list.item(_MAX_LISTED).text() == "… and 100 more files"
