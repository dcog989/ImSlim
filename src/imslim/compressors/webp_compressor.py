from typing import override

from ..binary_resolver import resolve_tool
from ..compressor import Command, Compressor, tokens
from ..image_convert import to_png
from ..result_item import ResultItem

_CONVERTED_MIME_TYPES = ("image/bmp", "image/tiff")


class WEBPCompressor(Compressor):
    @override
    @classmethod
    def get_file_type(cls) -> str:
        return "webp"

    def _intermediate_path(self, result_item: ResultItem) -> str:
        return result_item.tmp_filename + ".src.png"

    def _needs_conversion(self, result_item: ResultItem) -> bool:
        return result_item.mime_type in _CONVERTED_MIME_TYPES

    @override
    def build_command(self, result_item: ResultItem) -> list[Command]:
        commands: list[Command] = []
        input_path = result_item.filename

        # cwebp can't read BMP and this build has no TIFF support, so decode
        # either to a temporary PNG with Qt before feeding it to cwebp.
        if self._needs_conversion(result_item):
            intermediate = self._intermediate_path(result_item)
            to_png(result_item.filename, intermediate)
            input_path = intermediate

        cwebp = [resolve_tool("cwebp")]

        # cwebp drops all metadata by default. When preserving metadata copy
        # everything; otherwise keep the ICC color profile so colors still
        # render correctly while the rest is stripped.
        if self.settings.metadata:
            cwebp += ["-metadata", "all"]
        else:
            cwebp += ["-metadata", "icc"]

        if self.settings.lossy:
            quality = self.settings.webp_lossy_level
        else:
            cwebp.append("-lossless")
            quality = 100  # maximum cpu power for lossless

        # multithreaded, (lossless) compression mode, quality, output
        cwebp += tokens(
            t"-mt -m {self.settings.webp_lossless_level} -q {quality} "
            t"-o {result_item.tmp_filename} {input_path}"
        )

        commands.append(Command(cwebp))
        return commands

    @override
    def get_intermediate_files(self, result_item: ResultItem) -> list[str]:
        if self._needs_conversion(result_item):
            return [self._intermediate_path(result_item)]
        return []
