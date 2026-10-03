from typing import override

from ..batch_options import BatchOptions
from ..binary_resolver import resolve_tool
from ..commands import Command, tokens
from ..compressor import Compressor
from ..formats import CompressorType
from ..image_utils import is_animated_image
from ..result_item import ResultItem


class GIFCompressor(Compressor):
    @override
    @classmethod
    def get_file_type(cls) -> CompressorType:
        return CompressorType.GIF

    def _is_animated(self, result_item: ResultItem) -> bool:
        return is_animated_image(result_item.filename, "image/gif")

    @override
    def build_command(
        self, result_item: ResultItem, options: BatchOptions, input_path: str
    ) -> list[Command]:
        is_animated = self._is_animated(result_item)

        gifsicle = [
            resolve_tool("gifsicle"),
            f"--optimize={options.level('gif-lossless-level')}",
        ]

        # gifsicle --lossy can visibly flicker/posterize complex animation,
        # so animated GIFs are always compressed losslessly
        if options.lossy and not is_animated:
            gifsicle += [f"--lossy={options.level('gif-lossy-level')}"]

        if not options.metadata:
            # --no-extensions would also strip the animation loop and frame
            # control, so it is limited to static GIFs
            if not is_animated:
                gifsicle += ["--no-extensions"]
            gifsicle += ["--no-comments", "--no-names"]

        gifsicle += tokens(t"-o {result_item.tmp_filename} {input_path}")

        return [Command(gifsicle, temp_files=(result_item.tmp_filename,))]
