from typing import cast

from PySide6.QtCore import QSettings

SAVE_NEW_FILE = 0
SAVE_BACKUP_OVERWRITE = 1

DEFAULTS: dict[str, str | int | bool] = {
    "save-method": SAVE_NEW_FILE,
    "output-folder": "",
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
    "compression-timeout": 30,
}


class SettingsManager:
    def __init__(self) -> None:
        self._settings = QSettings("ImSlim", "ImSlim")

    def set_boolean(self, key: str, value: bool) -> None:
        self._settings.setValue(key, bool(value))

    def set_int(self, key: str, value: int) -> None:
        self._settings.setValue(key, int(value))

    def set_string(self, key: str, value: str) -> None:
        self._settings.setValue(key, str(value))

    def _get(self, key: str) -> str | int | bool:
        default = DEFAULTS[key]
        if isinstance(default, bool):
            return bool(self._settings.value(key, default, type=bool))
        if isinstance(default, int):
            value = self._settings.value(key, default)
            if isinstance(value, int) and not isinstance(value, bool):
                return value
            return default
        return str(self._settings.value(key, default, type=str))

    def _set(self, key: str, value: str | int | bool) -> None:
        default = DEFAULTS[key]
        if isinstance(default, bool):
            self.set_boolean(key, cast(bool, value))
        elif isinstance(default, int):
            self.set_int(key, cast(int, value))
        else:
            self.set_string(key, cast(str, value))

    @property
    def save_method(self) -> int:
        return cast(int, self._get("save-method"))

    @save_method.setter
    def save_method(self, value: int) -> None:
        self._set("save-method", value)

    @property
    def output_folder(self) -> str:
        return cast(str, self._get("output-folder"))

    @output_folder.setter
    def output_folder(self, value: str) -> None:
        self._set("output-folder", value)

    @property
    def lossy(self) -> bool:
        return cast(bool, self._get("lossy"))

    @lossy.setter
    def lossy(self, value: bool) -> None:
        self._set("lossy", value)

    @property
    def recursive(self) -> bool:
        return cast(bool, self._get("recursive"))

    @recursive.setter
    def recursive(self, value: bool) -> None:
        self._set("recursive", value)


# The remaining properties are generated from DEFAULTS in one place; the four
# settings declared explicitly above are skipped here.
for _key in DEFAULTS:
    if _key in {"save-method", "output-folder", "lossy", "recursive"}:
        continue
    setattr(
        SettingsManager,
        _key.replace("-", "_"),
        property(
            lambda self, key=_key: self._get(key),
            lambda self, value, key=_key: self._set(key, value),
        ),
    )
