from typing import override

from ..binary_resolver import resolve_tool
from ..compressor import Command, Compressor, tokens
from ..result_item import ResultItem


class AVIFCompressor(Compressor):
    @override
    @classmethod
    def get_file_type(cls) -> str:
        return "avif"

    @override
    def build_command(self, result_item: ResultItem) -> list[Command]:
        commands: list[Command] = []
        encode_input = result_item.input_path

        # avifenc can't read AVIF input, so decode to a temporary PNG first.
        # PNG input (native PNG or a conversion intermediate) feeds avifenc directly.
        if not self._input_is_png(result_item):
            intermediate = self._intermediate_path(result_item)
            commands.append(
                Command(tokens(t"{resolve_tool('avifdec')} {result_item.filename} {intermediate}"))
            )
            encode_input = intermediate

        avifenc = [resolve_tool("avifenc")]

        # avifenc preserves metadata by default. Strip only non-rendering
        # metadata (EXIF/XMP); keep the ICC color profile so colors still
        # render correctly (see issue: color profiles stripped with metadata off).
        if not self.settings.metadata:
            avifenc += ["--ignore-exif", "--ignore-xmp"]

        if self.settings.lossy:
            # tune=iq + 10-bit depth is the best quality/size operating point for libaom
            avifenc += tokens(t"-q {self.settings.avif_lossy_level} -a tune=iq -d 10")
        else:
            avifenc.append("--lossless")

        # higher effort -> slower but better compression (speed 0-10, default 6)
        avifenc += tokens(t"--speed {10 - self.settings.avif_lossless_level}")
        avifenc += [encode_input, result_item.tmp_filename]

        commands.append(Command(avifenc))
        return commands

    @override
    def get_intermediate_files(self, result_item: ResultItem) -> list[str]:
        return [self._intermediate_path(result_item)]
