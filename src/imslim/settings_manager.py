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
    "last-version": "",
}


class SettingsManager:
    def __init__(self) -> None:
        self._settings = QSettings("ImSlim", "ImSlim")

    # Generic setters
    def reset(self, key: str) -> None:
        default = DEFAULTS.get(key)
        if default is None:
            self._settings.remove(key)
        elif isinstance(default, bool):
            self.set_boolean(key, default)
        elif isinstance(default, int):
            self.set_int(key, default)
        else:
            self.set_string(key, default)

    def set_boolean(self, key: str, value: bool) -> None:
        self._settings.setValue(key, bool(value))

    def set_int(self, key: str, value: int) -> None:
        self._settings.setValue(key, int(value))

    def set_string(self, key: str, value: str) -> None:
        self._settings.setValue(key, str(value))

    def _bool(self, key: str) -> bool:
        return bool(self._settings.value(key, DEFAULTS[key], type=bool))

    def _int(self, key: str) -> int:
        return int(self._settings.value(key, DEFAULTS[key], type=int))

    def _str(self, key: str) -> str:
        return str(self._settings.value(key, DEFAULTS[key], type=str))

    # Options
    @property
    def save_method(self) -> int:
        return self._int("save-method")

    @save_method.setter
    def save_method(self, value: int) -> None:
        self.set_int("save-method", value)

    @property
    def output_folder(self) -> str:
        return self._str("output-folder")

    @output_folder.setter
    def output_folder(self, value: str) -> None:
        self.set_string("output-folder", value)

    @property
    def recursive(self) -> bool:
        return self._bool("recursive")

    @recursive.setter
    def recursive(self, value: bool) -> None:
        self.set_boolean("recursive", value)

    @property
    def compression_timeout(self) -> int:
        return self._int("compression-timeout")

    @compression_timeout.setter
    def compression_timeout(self, value: int) -> None:
        self.set_int("compression-timeout", value)

    @property
    def lossy(self) -> bool:
        return self._bool("lossy")

    @lossy.setter
    def lossy(self, value: bool) -> None:
        self.set_boolean("lossy", value)

    @property
    def metadata(self) -> bool:
        return self._bool("metadata")

    @metadata.setter
    def metadata(self, value: bool) -> None:
        self.set_boolean("metadata", value)

    @property
    def file_attributes(self) -> bool:
        return self._bool("file-attributes")

    @file_attributes.setter
    def file_attributes(self, value: bool) -> None:
        self.set_boolean("file-attributes", value)

    # PNG options
    @property
    def png_lossy_level(self) -> int:
        return self._int("png-lossy-level")

    @png_lossy_level.setter
    def png_lossy_level(self, value: int) -> None:
        self.set_int("png-lossy-level", value)

    @property
    def png_lossless_level(self) -> int:
        return self._int("png-lossless-level")

    @png_lossless_level.setter
    def png_lossless_level(self, value: int) -> None:
        self.set_int("png-lossless-level", value)

    # JPG options
    @property
    def jpg_lossy_level(self) -> int:
        return self._int("jpg-lossy-level")

    @jpg_lossy_level.setter
    def jpg_lossy_level(self, value: int) -> None:
        self.set_int("jpg-lossy-level", value)

    @property
    def jpg_progressive(self) -> bool:
        return self._bool("jpg-progressive")

    @jpg_progressive.setter
    def jpg_progressive(self, value: bool) -> None:
        self.set_boolean("jpg-progressive", value)

    # WebP options
    @property
    def webp_lossless_level(self) -> int:
        return self._int("webp-lossless-level")

    @webp_lossless_level.setter
    def webp_lossless_level(self, value: int) -> None:
        self.set_int("webp-lossless-level", value)

    @property
    def webp_lossy_level(self) -> int:
        return self._int("webp-lossy-level")

    @webp_lossy_level.setter
    def webp_lossy_level(self, value: int) -> None:
        self.set_int("webp-lossy-level", value)

    # AVIF options
    @property
    def avif_lossy_level(self) -> int:
        return self._int("avif-lossy-level")

    @avif_lossy_level.setter
    def avif_lossy_level(self, value: int) -> None:
        self.set_int("avif-lossy-level", value)

    @property
    def avif_lossless_level(self) -> int:
        return self._int("avif-lossless-level")

    @avif_lossless_level.setter
    def avif_lossless_level(self, value: int) -> None:
        self.set_int("avif-lossless-level", value)

    # JXL options
    @property
    def jxl_lossy_level(self) -> int:
        return self._int("jxl-lossy-level")

    @jxl_lossy_level.setter
    def jxl_lossy_level(self, value: int) -> None:
        self.set_int("jxl-lossy-level", value)

    @property
    def jxl_lossless_level(self) -> int:
        return self._int("jxl-lossless-level")

    @jxl_lossless_level.setter
    def jxl_lossless_level(self, value: int) -> None:
        self.set_int("jxl-lossless-level", value)

    # GIF options
    @property
    def gif_lossy_level(self) -> int:
        return self._int("gif-lossy-level")

    @gif_lossy_level.setter
    def gif_lossy_level(self, value: int) -> None:
        self.set_int("gif-lossy-level", value)

    @property
    def gif_lossless_level(self) -> int:
        return self._int("gif-lossless-level")

    @gif_lossless_level.setter
    def gif_lossless_level(self, value: int) -> None:
        self.set_int("gif-lossless-level", value)

    # SVG options
    @property
    def svg_maximum_level(self) -> bool:
        return self._bool("svg-maximum-level")

    @svg_maximum_level.setter
    def svg_maximum_level(self, value: bool) -> None:
        self.set_boolean("svg-maximum-level", value)

    # Others
    @property
    def last_version(self) -> str:
        return self._str("last-version")

    @last_version.setter
    def last_version(self, value: str) -> None:
        self.set_string("last-version", value)
