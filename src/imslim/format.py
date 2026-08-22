import functools

from PySide6.QtCore import QLocale


def sizeof_fmt(num: float | None) -> str:
    if num is None or num < 0:
        return ""
    value = float(num)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024.0 or unit == "TiB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f}".replace(".", _decimal_separator()) + f" {unit}"
        value /= 1024.0
    return ""


def savings_percent(size: int, new_size: int) -> int:
    """Percentage of the original size saved, 0 when size is not positive."""
    if size <= 0:
        return 0
    return round(100 - (new_size * 100 / size))


@functools.cache
def _decimal_separator() -> str:
    """Return the host locale's decimal separator (e.g. "." or ",").

    Read from Qt's system locale instead of mutating the process-wide locale
    with locale.setlocale().
    """
    return QLocale().decimalPoint()
