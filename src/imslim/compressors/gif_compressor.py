from PySide6.QtGui import QImageReader

from ..binary_resolver import resolve_tool
from ..compressor import Command, Compressor
from ..result_item import ResultItem


class GIFCompressor(Compressor):
    @classmethod
    def get_file_type(cls) -> str:
        return "gif"

    def _is_animated(self, result_item: ResultItem) -> bool:
        reader = QImageReader(result_item.filename)
        frame_count = reader.imageCount()
        # imageCount() is -1 when Qt can't determine the count (e.g. static
        # GIFs written by Qt); treat unknown counts as animated to stay lossless
        return frame_count != 1

    def build_command(self, result_item: ResultItem) -> list[Command]:
        is_animated = self._is_animated(result_item)

        gifsicle = [
            resolve_tool("gifsicle"),
            f"--optimize={self.settings.gif_lossless_level}",
        ]

        # gifsicle --lossy can visibly flicker/posterize complex animation,
        # so animated GIFs are always compressed losslessly
        if self.settings.lossy and not is_animated:
            gifsicle += [f"--lossy={self.settings.gif_lossy_level}"]

        if not self.settings.metadata:
            # --no-extensions would also strip the animation loop and frame
            # control, so it is limited to static GIFs
            if not is_animated:
                gifsicle += ["--no-extensions"]
            gifsicle += ["--no-comments", "--no-names"]

        gifsicle += ["-o", result_item.tmp_filename, result_item.filename]

        return [Command(gifsicle)]
