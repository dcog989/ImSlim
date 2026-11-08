from imslim.dialogs import batch_size_totals
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
