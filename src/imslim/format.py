import functools

from PySide6.QtCore import QLocale

# KB is the smallest unit shown and one decimal is as fine as it gets; above
# 100 units the fraction is noise in a list, so it is dropped.
_SIZE_UNITS: tuple[str, ...] = ("KB", "MB", "GB", "TB")
_MIN_KB = 0.1
_MAX_FRACTION_VALUE = 100.0


def sizeof_fmt(num: float | None) -> str:
    if num is None or num < 0:
        return ""
    value = float(num) / 1024.0
    if value < _MIN_KB:
        return "0.1 KB"
    for unit in _SIZE_UNITS:
        if value < 1024.0 or unit == _SIZE_UNITS[-1]:
            if value < _MAX_FRACTION_VALUE:
                return f"{value:.1f}".replace(".", _decimal_separator()) + f" {unit}"
            return f"{value:.0f} {unit}"
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
