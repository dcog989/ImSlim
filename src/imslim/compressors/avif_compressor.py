from typing import override

from ..batch_options import BatchOptions
from ..binary_resolver import resolve_tool
from ..commands import Command, tokens
from ..compressor import Compressor
from ..conversion import decode_commands
from ..formats import CompressorType, Format, native_inputs
from ..result_item import ResultItem

# tune=iq + 10-bit depth is the best quality/size operating point for libaom.
_ENCODE_BIT_DEPTH = 10
# avifenc --speed range is 0-10 (slowest/best to fastest/worst).
_MAX_SPEED = 10
# Source formats avifenc reads itself, derived from the AVIF target's native
# inputs minus AVIF itself, which avifenc cannot read.
_ENCODER_INPUTS = native_inputs(Format.AVIF) - {"image/avif"}


class AVIFCompressor(Compressor):
    @override
    @classmethod
    def get_file_type(cls) -> CompressorType:
        return CompressorType.AVIF

    def _reads_input(self, result_item: ResultItem, input_path: str) -> bool:
        """True when avifenc can read `input_path` itself.

        Either a source format avifenc reads, or the PNG the pipeline already
        pre-decoded for a format it cannot read. Passing a JPEG straight through
        keeps its EXIF/XMP, which a decode to PNG would drop.
        """
        if input_path != result_item.filename:
            return True
        return result_item.mime_type in _ENCODER_INPUTS

    @override
    def build_command(
        self, result_item: ResultItem, options: BatchOptions, input_path: str
    ) -> list[Command]:
        commands: list[Command] = []
        encode_input = input_path

        # avifenc can't read AVIF input, so decode to a temporary PNG first.
        if not self._reads_input(result_item, input_path):
            intermediate = self._intermediate_path(result_item)
            commands += decode_commands(result_item.mime_type, input_path, intermediate)
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
        avifenc += tokens(t"--speed {_MAX_SPEED - options.level('avif-effort')}")
        avifenc += [encode_input, result_item.tmp_filename]

        commands.append(Command(avifenc, temp_files=(result_item.tmp_filename,)))
        return commands
