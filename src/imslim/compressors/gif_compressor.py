from typing import override

from ..batch_options import BatchOptions
from ..binary_resolver import resolve_tool
from ..compressor import Command, Compressor, tokens
from ..image_utils import is_animated_image
from ..result_item import ResultItem


class GIFCompressor(Compressor):
    @override
    @classmethod
    def get_file_type(cls) -> str:
        return "gif"

    def _is_animated(self, result_item: ResultItem) -> bool:
        return is_animated_image(result_item.filename, "image/gif")

    @override
    def build_command(self, result_item: ResultItem, options: BatchOptions) -> list[Command]:
        is_animated = self._is_animated(result_item)

        gifsicle = [
            resolve_tool("gifsicle"),
            f"--optimize={options.gif_lossless_level}",
        ]

        # gifsicle --lossy can visibly flicker/posterize complex animation,
        # so animated GIFs are always compressed losslessly
        if options.lossy and not is_animated:
            gifsicle += [f"--lossy={options.gif_lossy_level}"]

        if not options.metadata:
            # --no-extensions would also strip the animation loop and frame
            # control, so it is limited to static GIFs
            if not is_animated:
                gifsicle += ["--no-extensions"]
            gifsicle += ["--no-comments", "--no-names"]

        gifsicle += tokens(t"-o {result_item.tmp_filename} {result_item.filename}")

        return [Command(gifsicle)]
