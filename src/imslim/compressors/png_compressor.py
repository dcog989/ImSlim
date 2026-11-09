from functools import partial
from typing import override

from ..batch_options import BatchOptions
from ..binary_resolver import resolve_tool
from ..commands import Command, tokens
from ..compressor import ENCODER_THREADS_PER_JOB, Compressor
from ..formats import CompressorType
from ..png_metadata import transfer_png_metadata
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

        # pngquant flattens an APNG to one frame, so animated PNGs stay lossless.
        quantize = options.lossy and not result_item.is_animated
        if quantize:  # lossy compression
            quality_flag = f"--quality=0-{options.level('png-lossy-level')}"
            pngquant = tokens(t"{resolve_tool('pngquant')} {quality_flag} -f")
            if not options.metadata:
                pngquant.append("--strip")
            pngquant += [input_path, "--output", result_item.tmp_filename]
            commands.append(Command(pngquant, temp_files=(result_item.tmp_filename,)))

        # Deinterlace: Adam7 interlacing adds 25-50% to the file size, which is
        # the opposite of what a compressor wants.
        oxipng = tokens(
            t"{resolve_tool('oxipng')} -o {options.level('png-effort')} -i 0 "
            + t"-t {ENCODER_THREADS_PER_JOB}"
        )
        if not options.metadata:
            oxipng += ["--strip", "safe"]

        if quantize:
            oxipng += [result_item.tmp_filename, "--out", result_item.tmp_filename]
        else:  # lossless compression
            oxipng += [input_path, "--out", result_item.tmp_filename]

        commands.append(Command(oxipng, temp_files=(result_item.tmp_filename,)))

        # pngquant drops eXIf/text chunks; put the source's metadata back when
        # the user asked to keep it. Conversion sources have no PNG metadata.
        if quantize and options.metadata and result_item.mime_type == "image/png":
            commands.append(
                Command(
                    action=partial(
                        transfer_png_metadata,
                        result_item.filename,
                        result_item.tmp_filename,
                    )
                )
            )
        return commands
