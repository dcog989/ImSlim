import sys

from ..binary_resolver import resolve_tool
from ..compressor import Command, Compressor
from ..result_item import ResultItem

_CONVERTED_MIME_TYPES = ("image/bmp", "image/tiff")


class WEBPCompressor(Compressor):
    @classmethod
    def get_file_type(cls) -> str:
        return "webp"

    def _intermediate_path(self, result_item: ResultItem) -> str:
        return result_item.tmp_filename + ".src.png"

    def _needs_conversion(self, result_item: ResultItem) -> bool:
        return result_item.mime_type in _CONVERTED_MIME_TYPES

    def build_command(self, result_item: ResultItem) -> list[Command]:
        commands: list[Command] = []
        input_path = result_item.filename

        # cwebp can't read BMP and this build has no TIFF support, so decode
        # either to a temporary PNG with Qt before feeding it to cwebp.
        if self._needs_conversion(result_item):
            intermediate = self._intermediate_path(result_item)
            commands.append(
                Command(
                    [
                        sys.executable,
                        "-m",
                        "imslim.image_convert",
                        result_item.filename,
                        intermediate,
                    ]
                )
            )
            input_path = intermediate

        cwebp = [resolve_tool("cwebp")]

        # cwebp doesn't preserve any metadata by default
        if self.settings.metadata:
            cwebp += ["-metadata", "all"]

        if self.settings.lossy:
            quality = self.settings.webp_lossy_level
        else:
            cwebp.append("-lossless")
            quality = 100  # maximum cpu power for lossless

        # multithreaded, (lossless) compression mode, quality, output
        cwebp += [
            "-mt",
            "-m",
            str(self.settings.webp_lossless_level),
            "-q",
            str(quality),
            "-o",
            result_item.tmp_filename,
            input_path,
        ]

        commands.append(Command(cwebp))
        return commands

    def get_intermediate_files(self, result_item: ResultItem) -> list[str]:
        if self._needs_conversion(result_item):
            return [self._intermediate_path(result_item)]
        return []
