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
            self.set_boolean(key, value)
        elif isinstance(default, int):
            self.set_int(key, value)
        else:
            self.set_string(key, value)


# One typed property per DEFAULTS entry, named after the key with dashes
# replaced by underscores (e.g. "png-lossy-level" -> settings.png_lossy_level).
# The type is derived from the default value, so a setting is defined in
# exactly one place instead of repeating a property/setter pair per key.
for _key in DEFAULTS:
    setattr(
        SettingsManager,
        _key.replace("-", "_"),
        property(
            lambda self, key=_key: self._get(key),
            lambda self, value, key=_key: self._set(key, value),
        ),
    )
