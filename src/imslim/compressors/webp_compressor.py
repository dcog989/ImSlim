from typing import override

from ..batch_options import BatchOptions
from ..binary_resolver import resolve_tool
from ..commands import Command, tokens
from ..compressor import Compressor
from ..conversion import decode_commands
from ..formats import OUTPUT_EXTENSIONS, TARGET_EXTENSIONS, CompressorType, Format
from ..result_item import ResultItem

# Sources that re-encode to WebP; cwebp cannot read them, so decode first.
_CONVERTED_MIME_TYPES = frozenset(
    mime
    for mime, extension in OUTPUT_EXTENSIONS.items()
    if extension == TARGET_EXTENSIONS[Format.WEBP]
)
# maximum cpu power for lossless
_LOSSLESS_QUALITY = 100


class WEBPCompressor(Compressor):
    @override
    @classmethod
    def get_file_type(cls) -> CompressorType:
        return CompressorType.WEBP

    def _needs_conversion(
        self, result_item: ResultItem, input_path: str, options: BatchOptions
    ) -> bool:
        if self._input_is_png(result_item, input_path):
            return False
        if result_item.mime_type in _CONVERTED_MIME_TYPES:
            return True
        # cwebp cannot read animated WebP, and stripping metadata loses the
        # orientation, so decode those to a still PNG with Qt first.
        return (result_item.mime_type == "image/webp" and result_item.is_animated) or (
            result_item.mime_type == "image/jpeg" and not options.metadata
        )

    @override
    def build_command(
        self, result_item: ResultItem, options: BatchOptions, input_path: str
    ) -> list[Command]:
        commands: list[Command] = []

        # cwebp can't read BMP, animated WebP, or this build's TIFF, and JPEG
        # needs an orientation-aware decode when metadata is stripped.
        if self._needs_conversion(result_item, input_path, options):
            intermediate = self._intermediate_path(result_item)
            commands += decode_commands(
                result_item.mime_type,
                input_path,
                intermediate,
                apply_orientation=not options.metadata,
            )
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

        # cwebp has no thread-count flag; the pool parallelizes files instead.
        cwebp += tokens(
            t"-m {options.level('webp-effort')} -q {quality} "
            + t"-o {result_item.tmp_filename} {input_path}"
        )

        commands.append(Command(cwebp, temp_files=(result_item.tmp_filename,)))
        return commands
