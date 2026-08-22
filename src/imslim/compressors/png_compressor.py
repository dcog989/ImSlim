from typing import override

from ..binary_resolver import resolve_tool
from ..compressor import Command, Compressor, tokens
from ..result_item import ResultItem


class PNGCompressor(Compressor):
    @override
    @classmethod
    def get_file_type(cls) -> str:
        return "png"

    @override
    def build_command(self, result_item: ResultItem) -> list[Command]:
        commands: list[Command] = []

        if self.settings.lossy:  # lossy compression
            quality_flag = f"--quality=0-{self.settings.png_lossy_level}"
            pngquant = tokens(t"{resolve_tool('pngquant')} {quality_flag} -f")
            if not self.settings.metadata:
                pngquant.append("--strip")
            pngquant += [result_item.filename, "--output", result_item.tmp_filename]
            commands.append(Command(pngquant))

        oxipng = tokens(t"{resolve_tool('oxipng')} -o {self.settings.png_lossless_level} -i 1")
        if not self.settings.metadata:
            oxipng += ["--strip", "safe"]
        if self.settings.file_attributes:
            oxipng.append("--preserve")

        if self.settings.lossy:
            oxipng += [result_item.tmp_filename, "--out", result_item.tmp_filename]
        else:  # lossless compression
            oxipng += [result_item.filename, "--out", result_item.tmp_filename]

        commands.append(Command(oxipng))
        return commands
