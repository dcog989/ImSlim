from __future__ import annotations

import os
from typing import Protocol, TypeVar, cast, final

from PySide6.QtCore import QByteArray, QSettings, QStandardPaths

from .formats import FORMAT_DEFAULT_KNOBS, FORMAT_KNOB_BOUNDS, Format

LOG_FILE_NAME = "imslim.log"

_T = TypeVar("_T")


def log_file_path(name: str = LOG_FILE_NAME) -> str:
    """Absolute path of a rotating log file.

    Logs are state, not data, so they follow $XDG_STATE_HOME (~/.local/state)
    where available, falling back to the home directory.
    """
    base = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.GenericStateLocation
    ) or QStandardPaths.writableLocation(QStandardPaths.StandardLocation.HomeLocation)
    return os.path.join(base, "ImSlim", name)


def config_file_path() -> str:
    """Absolute path of the QSettings file that stores the app's options."""
    return QSettings("ImSlim", "ImSlim").fileName()


_TRUE_WORDS = frozenset(("true", "1", "yes", "on"))
_FALSE_WORDS = frozenset(("false", "0", "no", "off"))


def _coerce_bool(raw: object, default: bool) -> bool:
    if isinstance(raw, bool):
        return raw
    text = str(raw).strip().lower()
    if text in _TRUE_WORDS:
        return True
    if text in _FALSE_WORDS:
        return False
    # A typo must not silently flip a default-on option off.
    return default


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


def _setting[T](key: str, _type: type[T], *, sync: bool = True) -> _SettingDescriptor[T]:
    """Build a property binding an attribute name to a settings key.

    `_type` is never read at runtime; it exists so the value type is bound at
    the call sites (e.g. `lossy = _setting("lossy", bool)`), which the type
    checker otherwise cannot infer. `sync=False` keeps hot UI state (view mode,
    thumbnail size) out of the per-change disk flush.
    """

    def getter(self: SettingsManager) -> T:
        return cast(T, self._get(key))  # pyright: ignore[reportPrivateUsage]

    def setter(self: SettingsManager, value: T) -> None:
        self._set(key, cast("str | int | bool", value), sync=sync)  # pyright: ignore[reportPrivateUsage]

    return cast(_SettingDescriptor[T], cast(object, property(getter, setter)))


SAVE_NEXT_TO_ORIGINAL = 0
SAVE_BACKUP_OVERWRITE = 1
SAVE_OUTPUT_FOLDER = 2

# Bounds for the per-file tool timeout, shared by the spin box and the batch
# snapshot so a hand-edited 0 cannot fail every file.
COMPRESSION_TIMEOUT_MIN = 1
COMPRESSION_TIMEOUT_MAX = 300

# Where the Add Files/Directory dialogs start.
START_HOME = 0
START_PICTURES = 1
START_LAST = 2
START_CUSTOM = 3

BASE_DEFAULTS: dict[str, str | int | bool] = {
    "save-method": SAVE_NEXT_TO_ORIGINAL,
    "target-format": Format.KEEP,
    "output-folder": "",
    "start-location": START_HOME,
    "default-open-dialog-directory": "",
    "last-open-dialog-directory": "",
    "recursive": True,
    "metadata": True,
    "file-attributes": True,
    "skip-if-larger": True,
    "timestamp-dir": False,
    "lossy": False,
    "view-mode": "details",
    "thumbnail-size": 64,
    "compression-timeout": 30,
    "log-level": "INFO",
    "log-max-size": 1,
    "log-backups": 9,
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

    def set_boolean(self, key: str, value: bool, *, sync: bool = True) -> None:
        self._settings.setValue(key, bool(value))
        if sync:
            self._settings.sync()

    def set_int(self, key: str, value: int, *, sync: bool = True) -> None:
        self._settings.setValue(key, int(value))
        if sync:
            self._settings.sync()

    def set_string(self, key: str, value: str, *, sync: bool = True) -> None:
        self._settings.setValue(key, str(value))
        if sync:
            self._settings.sync()

    def sync(self) -> None:
        self._settings.sync()

    def _get(self, key: str) -> str | int | bool:
        default = DEFAULTS[key]
        raw = self._settings.value(key, default)
        if isinstance(default, bool):
            return _coerce_bool(raw, default)
        if isinstance(default, int):
            return _coerce_int(raw, default)
        return str(raw)

    def _set(self, key: str, value: str | int | bool, *, sync: bool = True) -> None:
        default = DEFAULTS[key]
        if isinstance(default, bool):
            self.set_boolean(key, cast(bool, value), sync=sync)
        elif isinstance(default, int):
            self.set_int(key, cast(int, value), sync=sync)
        else:
            self.set_string(key, cast(str, value), sync=sync)

    def knob(self, key: str) -> int | bool:
        """Read a per-format setting by its table-defined key, clamped."""
        value = self._get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            lower, upper = FORMAT_KNOB_BOUNDS.get(key, (value, value))
            return max(lower, min(upper, value))
        return cast("int | bool", value)

    @property
    def target_format(self) -> Format:
        try:
            return Format(str(self._get("target-format")))
        except ValueError:
            # A hand-edited or renamed value must not stop the app from starting.
            return Format.KEEP

    @target_format.setter
    def target_format(self, value: Format) -> None:
        self._set("target-format", value.value)

    @property
    def compression_timeout(self) -> int:
        value = int(self._get("compression-timeout"))
        return max(COMPRESSION_TIMEOUT_MIN, min(COMPRESSION_TIMEOUT_MAX, value))

    @compression_timeout.setter
    def compression_timeout(self, value: int) -> None:
        self._set("compression-timeout", value)

    @property
    def window_geometry(self) -> bytes:
        return self._byte_setting("window-geometry")

    @window_geometry.setter
    def window_geometry(self, value: bytes) -> None:
        self._settings.setValue("window-geometry", QByteArray(value))

    @property
    def layout_state(self) -> bytes:
        return self._byte_setting("layout-state")

    @layout_state.setter
    def layout_state(self, value: bytes) -> None:
        self._settings.setValue("layout-state", QByteArray(value))

    @property
    def completion_geometry(self) -> bytes:
        return self._byte_setting("completion-geometry")

    @completion_geometry.setter
    def completion_geometry(self, value: bytes) -> None:
        self._settings.setValue("completion-geometry", QByteArray(value))

    def _byte_setting(self, key: str) -> bytes:
        raw = self._settings.value(key, b"")
        if isinstance(raw, QByteArray):
            return bytes(raw.data())
        if isinstance(raw, (bytes, bytearray)):
            return bytes(raw)
        return b""

    save_method = _setting("save-method", int)
    output_folder = _setting("output-folder", str)
    start_location = _setting("start-location", int)
    default_open_dialog_directory = _setting("default-open-dialog-directory", str)
    last_open_dialog_directory = _setting("last-open-dialog-directory", str)
    lossy = _setting("lossy", bool)
    recursive = _setting("recursive", bool)
    metadata = _setting("metadata", bool)
    file_attributes = _setting("file-attributes", bool)
    skip_if_larger = _setting("skip-if-larger", bool)
    timestamp_dir = _setting("timestamp-dir", bool)
    view_mode = _setting("view-mode", str, sync=False)
    thumbnail_size = _setting("thumbnail-size", int, sync=False)
    log_level = _setting("log-level", str)
    log_max_size = _setting("log-max-size", int)
    log_backups = _setting("log-backups", int)
