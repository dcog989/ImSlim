from __future__ import annotations

import os
from typing import Protocol, TypeVar, cast, final

from PySide6.QtCore import QSettings, QStandardPaths

from .formats import FORMAT_DEFAULT_KNOBS, Format

_LOG_FILE_NAME = "imslim.log"

_T = TypeVar("_T")


def log_file_path() -> str:
    """Absolute path of the app's rotating log file.

    Logs are state, not data, so they follow $XDG_STATE_HOME (~/.local/state)
    where available, falling back to the home directory.
    """
    base = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.GenericStateLocation
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


SAVE_NEXT_TO_ORIGINAL = 0
SAVE_BACKUP_OVERWRITE = 1
SAVE_OUTPUT_FOLDER = 2

BASE_DEFAULTS: dict[str, str | int | bool] = {
    "save-method": SAVE_NEXT_TO_ORIGINAL,
    "target-format": Format.KEEP,
    "output-folder": "",
    "default-open-dialog-directory": "",
    "recursive": True,
    "metadata": True,
    "file-attributes": True,
    "lossy": False,
    "compression-timeout": 15,
    "log-level": "INFO",
    "log-max-size": 2,
    "log-backups": 3,
}

# Per-format knobs are defined by the format table; base settings live here.
DEFAULTS: dict[str, str | int | bool] = {**BASE_DEFAULTS, **FORMAT_DEFAULT_KNOBS}


@final
class SettingsManager:
    def __init__(self) -> None:
        self._settings: QSettings = QSettings("ImSlim", "ImSlim")
        self._migrate()

    def _migrate(self) -> None:
        # Older builds had "save to a new file" write into a configured output
        # folder, silently overriding it. Surface that as its own save method so
        # existing configurations keep their destination.
        if self._settings.contains("save-method-migrated"):
            return
        if self.save_method == SAVE_NEXT_TO_ORIGINAL and self.output_folder:
            self.save_method = SAVE_OUTPUT_FOLDER
        self._settings.setValue("save-method-migrated", True)

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

    def knob(self, key: str) -> int | bool:
        """Read a per-format setting by its table-defined key."""
        return cast("int | bool", self._get(key))

    def set_knob(self, key: str, value: int | bool) -> None:
        self._set(key, value)

    @property
    def target_format(self) -> Format:
        return Format(str(self._get("target-format")))

    @target_format.setter
    def target_format(self, value: Format) -> None:
        self._set("target-format", value.value)

    save_method = _setting("save-method", int)
    output_folder = _setting("output-folder", str)
    default_open_dialog_directory = _setting("default-open-dialog-directory", str)
    lossy = _setting("lossy", bool)
    recursive = _setting("recursive", bool)
    metadata = _setting("metadata", bool)
    file_attributes = _setting("file-attributes", bool)
    compression_timeout = _setting("compression-timeout", int)
    log_level = _setting("log-level", str)
    log_max_size = _setting("log-max-size", int)
    log_backups = _setting("log-backups", int)
