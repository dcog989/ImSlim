from ..binary_resolver import resolve_tool
from ..compressor import Compressor


class SVGCompressor(Compressor):
    @classmethod
    def get_file_type(cls) -> str:
        return "svg"

    def build_command(self, result_item) -> list[tuple[list[str], str | None]]:
        svgo = [resolve_tool("svgo"), "--output", result_item.tmp_filename]

        if self.settings.svg_maximum_level:
            svgo += [
                "--multipass",
                "--enable",
                "removeDimensions",
                "sortAttrs",
            ]

        svgo.append(result_item.filename)

        return [(svgo, None)]
