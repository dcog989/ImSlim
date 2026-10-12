import pytest

from imslim.format import savings_percent


@pytest.mark.parametrize(
    ("size", "new_size", "expected"),
    [
        (100, 50, 50),
        (100, 100, 0),
        (200, 300, -50),  # output grew
        (3, 1, 67),  # round(100 - 100 / 3)
        (0, 10, 0),
        (-5, 1, 0),
    ],
)
def test_savings_percent(size: int, new_size: int, expected: int) -> None:
    assert savings_percent(size, new_size) == expected
