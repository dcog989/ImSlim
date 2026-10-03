from typing import override

from ..batch_options import BatchOptions
from ..binary_resolver import resolve_tool
from ..commands import Command, tokens
from ..compressor import Compressor
from ..conversion import decode_commands
from ..formats import CompressorType
from ..result_item import ResultItem

_CONVERTED_MIME_TYPES = ("image/bmp", "image/tiff")
# maximum cpu power for lossless
_LOSSLESS_QUALITY = 100


class WEBPCompressor(Compressor):
    @override
    @classmethod
    def get_file_type(cls) -> CompressorType:
        return CompressorType.WEBP

    @override
    def _intermediate_path(self, result_item: ResultItem) -> str:
        return result_item.tmp_filename + ".src.png"

    def _needs_conversion(self, result_item: ResultItem, input_path: str) -> bool:
        return result_item.mime_type in _CONVERTED_MIME_TYPES and not self._input_is_png(
            result_item, input_path
        )

    @override
    def build_command(
        self, result_item: ResultItem, options: BatchOptions, input_path: str
    ) -> list[Command]:
        commands: list[Command] = []

        # cwebp can't read BMP and this build has no TIFF support, so decode
        # either to a temporary PNG with Qt before feeding it to cwebp.
        if self._needs_conversion(result_item, input_path):
            intermediate = self._intermediate_path(result_item)
            commands += decode_commands(result_item.mime_type, input_path, intermediate)
            input_path = intermediate

        cwebp = [resolve_tool("cwebp")]

        # cwebp drops all metadata by default. When preserving metadata copy
        # everything; otherwise keep the ICC color profile so colors still
        # render correctly while the rest is stripped.
        if options.metadata:
            cwebp += ["-metadata", "all"]
        else:
            cwebp += ["-metadata", "icc"]

        if options.lossy:
            quality = options.level("webp-lossy-level")
        else:
            cwebp.append("-lossless")
            quality = _LOSSLESS_QUALITY

        # multithreaded, method (effort), quality, output
        cwebp += tokens(
            t"-mt -m {options.level('webp-effort')} -q {quality} "
            + t"-o {result_item.tmp_filename} {input_path}"
        )

        commands.append(Command(cwebp, temp_files=(result_item.tmp_filename,)))
        return commands
