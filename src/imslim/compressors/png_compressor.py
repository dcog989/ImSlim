from typing import override

from ..batch_options import BatchOptions
from ..binary_resolver import resolve_tool
from ..commands import Command, tokens
from ..compressor import Compressor
from ..formats import CompressorType
from ..result_item import ResultItem


class PNGCompressor(Compressor):
    @override
    @classmethod
    def get_file_type(cls) -> CompressorType:
        return CompressorType.PNG

    @override
    def build_command(
        self, result_item: ResultItem, options: BatchOptions, input_path: str
    ) -> list[Command]:
        commands: list[Command] = []

        if options.lossy:  # lossy compression
            quality_flag = f"--quality=0-{options.level('png-lossy-level')}"
            pngquant = tokens(t"{resolve_tool('pngquant')} {quality_flag} -f")
            if not options.metadata:
                pngquant.append("--strip")
            pngquant += [input_path, "--output", result_item.tmp_filename]
            commands.append(Command(pngquant, temp_files=(result_item.tmp_filename,)))

        # Deinterlace: Adam7 interlacing adds 25-50% to the file size, which is
        # the opposite of what a compressor wants.
        oxipng = tokens(t"{resolve_tool('oxipng')} -o {options.level('png-lossless-level')} -i 0")
        if not options.metadata:
            oxipng += ["--strip", "safe"]
        if options.file_attributes:
            oxipng.append("--preserve")

        if options.lossy:
            oxipng += [result_item.tmp_filename, "--out", result_item.tmp_filename]
        else:  # lossless compression
            oxipng += [input_path, "--out", result_item.tmp_filename]

        commands.append(Command(oxipng, temp_files=(result_item.tmp_filename,)))
        return commands
