from __future__ import annotations

import os
from typing import Protocol, TypeVar, cast, final

from PySide6.QtCore import QSettings, QStandardPaths

_LOG_FILE_NAME = "imslim.log"

_T = TypeVar("_T")


def log_file_path() -> str:
    """Absolute path of the app's rotating log file."""
    base = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.GenericDataLocation
    ) or QStandardPaths.writableLocation(QStandardPaths.StandardLocation.HomeLocation)
    return os.path.join(base, "ImSlim", _LOG_FILE_NAME)


def _coerce_bool(raw: object) -> bool:
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in ("true", "1", "yes", "on")


def _coerce_int(raw: object, default: int) -> int:
    if isinstance(raw, int) and not isinstance(raw, bool):
        return raw
    try:
        return int(str(raw))
    except ValueError:
        return default


class _SettingDescriptor(Protocol[_T]):
    """The descriptor interface `_setting()` returns, generic over its value type."""

    def __get__(self, instance: SettingsManager | None, owner: type[SettingsManager]) -> _T: ...

    def __set__(self, instance: SettingsManager, value: _T) -> None: ...


def _setting[T](key: str, _type: type[T]) -> _SettingDescriptor[T]:
    """Build a property binding an attribute name to a settings key."""

    def getter(self: SettingsManager) -> T:
        return cast(T, self._get(key))  # pyright: ignore[reportPrivateUsage]

    def setter(self: SettingsManager, value: T) -> None:
        self._set(key, cast("str | int | bool", value))  # pyright: ignore[reportPrivateUsage]

    return cast(_SettingDescriptor[T], cast(object, property(getter, setter)))


SAVE_NEW_FILE = 0
SAVE_BACKUP_OVERWRITE = 1

DEFAULTS: dict[str, str | int | bool] = {
    "save-method": SAVE_NEW_FILE,
    "output-folder": "",
    "default-open-dialog-directory": "",
    "recursive": True,
    "metadata": True,
    "file-attributes": True,
    "lossy": False,
    "png-lossy-level": 90,
    "png-lossless-level": 2,
    "jpg-lossy-level": 90,
    "jpg-progressive": False,
    "webp-lossy-level": 70,
    "webp-lossless-level": 4,
    "avif-lossy-level": 70,
    "avif-lossless-level": 6,
    "jxl-lossy-level": 70,
    "jxl-lossless-level": 6,
    "gif-lossy-level": 80,
    "gif-lossless-level": 3,
    "svg-maximum-level": False,
    "compression-timeout": 15,
    "log-level": "INFO",
    "log-max-size": 2,
    "log-backups": 3,
}


@final
class SettingsManager:
    def __init__(self) -> None:
        self._settings: QSettings = QSettings("ImSlim", "ImSlim")

    def set_boolean(self, key: str, value: bool) -> None:
        self._settings.setValue(key, bool(value))

    def set_int(self, key: str, value: int) -> None:
        self._settings.setValue(key, int(value))

    def set_string(self, key: str, value: str) -> None:
        self._settings.setValue(key, str(value))

    def sync(self) -> None:
        self._settings.sync()

    def _get(self, key: str) -> str | int | bool:
        default = DEFAULTS[key]
        raw = self._settings.value(key, default)
        if isinstance(default, bool):
            return _coerce_bool(raw)
        if isinstance(default, int):
            return _coerce_int(raw, default)
        return str(raw)

    def _set(self, key: str, value: str | int | bool) -> None:
        default = DEFAULTS[key]
        if isinstance(default, bool):
            self.set_boolean(key, cast(bool, value))
        elif isinstance(default, int):
            self.set_int(key, cast(int, value))
        else:
            self.set_string(key, cast(str, value))

    save_method = _setting("save-method", int)
    output_folder = _setting("output-folder", str)
    default_open_dialog_directory = _setting("default-open-dialog-directory", str)
    lossy = _setting("lossy", bool)
    recursive = _setting("recursive", bool)
    metadata = _setting("metadata", bool)
    file_attributes = _setting("file-attributes", bool)
    png_lossy_level = _setting("png-lossy-level", int)
    png_lossless_level = _setting("png-lossless-level", int)
    jpg_lossy_level = _setting("jpg-lossy-level", int)
    jpg_progressive = _setting("jpg-progressive", bool)
    webp_lossy_level = _setting("webp-lossy-level", int)
    webp_lossless_level = _setting("webp-lossless-level", int)
    avif_lossy_level = _setting("avif-lossy-level", int)
    avif_lossless_level = _setting("avif-lossless-level", int)
    jxl_lossy_level = _setting("jxl-lossy-level", int)
    jxl_lossless_level = _setting("jxl-lossless-level", int)
    gif_lossy_level = _setting("gif-lossy-level", int)
    gif_lossless_level = _setting("gif-lossless-level", int)
    svg_maximum_level = _setting("svg-maximum-level", bool)
    compression_timeout = _setting("compression-timeout", int)
    log_level = _setting("log-level", str)
    log_max_size = _setting("log-max-size", int)
    log_backups = _setting("log-backups", int)
