import pytest

from imslim.result_item import ResultItem, ResultState
from imslim.result_item_row import _savings_text


@pytest.mark.parametrize(
    "state",
    [
        ResultState.IDLE,
        ResultState.CANCELLED,
        ResultState.ERROR,
        ResultState.SKIPPED,
    ],
)
def test_savings_text_is_blank_without_a_saving(state: ResultState) -> None:
    # The IDLE guard fixes queued rows showing 100% before compression runs.
    assert _savings_text(ResultItem(size=100, new_size=50, state=state)) == ""


@pytest.mark.parametrize(
    ("size", "new_size", "expected"),
    [
        (100, 50, "50%"),
        (100, 150, "-50%"),
        (0, 50, "0%"),
    ],
)
def test_savings_text_reports_the_done_saving(size: int, new_size: int, expected: str) -> None:
    item = ResultItem(size=size, new_size=new_size, state=ResultState.DONE)
    assert _savings_text(item) == expected
