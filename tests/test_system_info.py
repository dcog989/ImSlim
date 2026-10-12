import pytest

from imslim.system_info import extract_version


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("libjxl 0.10.2", "0.10.2"),
        ("pngquant 2.18.0 (July 2023)", "2.18.0"),
        ("LC_VERSION=2.16", "2.16"),  # two-part version
        ("oxipng 1.3.0", "1.3.0"),
        ("no digits here", "Version not available"),
    ],
)
def test_extract_version(text: str, expected: str) -> None:
    assert extract_version(text) == expected
