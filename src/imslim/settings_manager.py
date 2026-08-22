from typing import cast

from PySide6.QtCore import QSettings


def _coerce_bool(raw: object) -> bool:
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in ("true", "1", "yes", "on")


def _coerce_int(raw: object, default: int) -> int:
    if isinstance(raw, int) and not isinstance(raw, bool):
        return raw
    try:
        return int(str(raw))
    except ValueError, TypeError:
        return default


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

    @property
    def metadata(self) -> bool:
        return cast(bool, self._get("metadata"))

    @metadata.setter
    def metadata(self, value: bool) -> None:
        self._set("metadata", value)

    @property
    def file_attributes(self) -> bool:
        return cast(bool, self._get("file-attributes"))

    @file_attributes.setter
    def file_attributes(self, value: bool) -> None:
        self._set("file-attributes", value)

    @property
    def png_lossy_level(self) -> int:
        return cast(int, self._get("png-lossy-level"))

    @png_lossy_level.setter
    def png_lossy_level(self, value: int) -> None:
        self._set("png-lossy-level", value)

    @property
    def png_lossless_level(self) -> int:
        return cast(int, self._get("png-lossless-level"))

    @png_lossless_level.setter
    def png_lossless_level(self, value: int) -> None:
        self._set("png-lossless-level", value)

    @property
    def jpg_lossy_level(self) -> int:
        return cast(int, self._get("jpg-lossy-level"))

    @jpg_lossy_level.setter
    def jpg_lossy_level(self, value: int) -> None:
        self._set("jpg-lossy-level", value)

    @property
    def jpg_progressive(self) -> bool:
        return cast(bool, self._get("jpg-progressive"))

    @jpg_progressive.setter
    def jpg_progressive(self, value: bool) -> None:
        self._set("jpg-progressive", value)

    @property
    def webp_lossy_level(self) -> int:
        return cast(int, self._get("webp-lossy-level"))

    @webp_lossy_level.setter
    def webp_lossy_level(self, value: int) -> None:
        self._set("webp-lossy-level", value)

    @property
    def webp_lossless_level(self) -> int:
        return cast(int, self._get("webp-lossless-level"))

    @webp_lossless_level.setter
    def webp_lossless_level(self, value: int) -> None:
        self._set("webp-lossless-level", value)

    @property
    def avif_lossy_level(self) -> int:
        return cast(int, self._get("avif-lossy-level"))

    @avif_lossy_level.setter
    def avif_lossy_level(self, value: int) -> None:
        self._set("avif-lossy-level", value)

    @property
    def avif_lossless_level(self) -> int:
        return cast(int, self._get("avif-lossless-level"))

    @avif_lossless_level.setter
    def avif_lossless_level(self, value: int) -> None:
        self._set("avif-lossless-level", value)

    @property
    def jxl_lossy_level(self) -> int:
        return cast(int, self._get("jxl-lossy-level"))

    @jxl_lossy_level.setter
    def jxl_lossy_level(self, value: int) -> None:
        self._set("jxl-lossy-level", value)

    @property
    def jxl_lossless_level(self) -> int:
        return cast(int, self._get("jxl-lossless-level"))

    @jxl_lossless_level.setter
    def jxl_lossless_level(self, value: int) -> None:
        self._set("jxl-lossless-level", value)

    @property
    def gif_lossy_level(self) -> int:
        return cast(int, self._get("gif-lossy-level"))

    @gif_lossy_level.setter
    def gif_lossy_level(self, value: int) -> None:
        self._set("gif-lossy-level", value)

    @property
    def gif_lossless_level(self) -> int:
        return cast(int, self._get("gif-lossless-level"))

    @gif_lossless_level.setter
    def gif_lossless_level(self, value: int) -> None:
        self._set("gif-lossless-level", value)

    @property
    def svg_maximum_level(self) -> bool:
        return cast(bool, self._get("svg-maximum-level"))

    @svg_maximum_level.setter
    def svg_maximum_level(self, value: bool) -> None:
        self._set("svg-maximum-level", value)

    @property
    def compression_timeout(self) -> int:
        return cast(int, self._get("compression-timeout"))

    @compression_timeout.setter
    def compression_timeout(self, value: int) -> None:
        self._set("compression-timeout", value)
