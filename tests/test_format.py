import pytest

from imslim.format import savings_percent, sizeof_fmt


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


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        (0, "0.1 KB"),
        (50, "0.1 KB"),
        (1024, "1.0 KB"),
        (10 * 1024, "10.0 KB"),
        (150 * 1024, "150 KB"),
        (int(2.5 * 1024 * 1024), "2.5 MB"),
        (int(150.4 * 1024 * 1024), "150 MB"),
        (None, ""),
        (-1, ""),
    ],
)
def test_sizeof_fmt_uses_smart_units(
    size: int | None, expected: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("imslim.format._decimal_separator", lambda: ".")
    assert sizeof_fmt(size) == expected
