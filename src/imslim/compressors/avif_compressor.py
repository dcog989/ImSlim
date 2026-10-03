from typing import override

from ..batch_options import BatchOptions
from ..binary_resolver import resolve_tool
from ..compressor import Command, Compressor, tokens
from ..conversion import decoder_argv
from ..formats import CompressorType
from ..result_item import ResultItem

# tune=iq + 10-bit depth is the best quality/size operating point for libaom.
_ENCODE_BIT_DEPTH = 10
# avifenc --speed range is 0-10 (slowest/best to fastest/worst).
_MAX_SPEED = 10


class AVIFCompressor(Compressor):
    @override
    @classmethod
    def get_file_type(cls) -> CompressorType:
        return CompressorType.AVIF

    @override
    def build_command(self, result_item: ResultItem, options: BatchOptions) -> list[Command]:
        commands: list[Command] = []
        encode_input = result_item.input_path

        # avifenc can't read AVIF input, so decode to a temporary PNG first.
        # PNG input (native PNG or a conversion intermediate) feeds avifenc directly.
        if not self._input_is_png(result_item):
            intermediate = self._intermediate_path(result_item)
            decode = decoder_argv(result_item.mime_type, result_item.filename, intermediate)
            if decode is None:
                raise RuntimeError("no bundled decoder for non-PNG AVIF source")
            commands.append(Command(decode))
            encode_input = intermediate

        avifenc = [resolve_tool("avifenc")]

        # avifenc preserves metadata by default. Strip only non-rendering
        # metadata (EXIF/XMP); keep the ICC color profile so colors still
        # render correctly (see issue: color profiles stripped with metadata off).
        if not options.metadata:
            avifenc += ["--ignore-exif", "--ignore-xmp"]

        if options.lossy:
            avifenc += tokens(
                t"-q {options.level('avif-lossy-level')} -a tune=iq -d {_ENCODE_BIT_DEPTH}"
            )
        else:
            avifenc.append("--lossless")

        # higher effort -> slower but better compression (speed 0-10, default 6)
        avifenc += tokens(t"--speed {_MAX_SPEED - options.level('avif-lossless-level')}")
        avifenc += [encode_input, result_item.tmp_filename]

        commands.append(Command(avifenc))
        return commands

    @override
    def get_intermediate_files(self, result_item: ResultItem, _options: BatchOptions) -> list[str]:
        return [self._intermediate_path(result_item)]
