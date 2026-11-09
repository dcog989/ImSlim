from pathlib import Path
from typing import override

from ..batch_options import BatchOptions
from ..binary_resolver import resolve_tool
from ..commands import Command, tokens
from ..compressor import Compressor
from ..formats import CompressorType
from ..result_item import ResultItem

# svgo configs are constant, so they ship as assets instead of being written
# into the user's source folder (which clashed across instances and survived
# crashes). csso (svgo's style minifier) crashes on malformed CSS declarations
# (e.g. the broken `enable-;` seen in some generated SVGs), so minifyStyles is
# always disabled; the rest of preset-default still runs.
_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
_SVGO_CONFIG = str(_ASSETS_DIR / "svgo.config.cjs")
_SVGO_CONFIG_STRIP = str(_ASSETS_DIR / "svgo.strip.config.cjs")
_SVGO_CONFIG_MAXIMUM = str(_ASSETS_DIR / "svgo.maximum.config.cjs")
_SVGO_CONFIG_MAXIMUM_STRIP = str(_ASSETS_DIR / "svgo.maximum-strip.config.cjs")


class SVGCompressor(Compressor):
    @override
    @classmethod
    def get_file_type(cls) -> CompressorType:
        return CompressorType.SVG

    @override
    def build_command(
        self, result_item: ResultItem, options: BatchOptions, input_path: str
    ) -> list[Command]:
        maximum = options.flag("svg-maximum-level")
        if options.metadata:
            config = _SVGO_CONFIG_MAXIMUM if maximum else _SVGO_CONFIG
        else:
            config = _SVGO_CONFIG_MAXIMUM_STRIP if maximum else _SVGO_CONFIG_STRIP
        svgo = [resolve_tool("svgo")]
        svgo += tokens(t"--config {config}")
        svgo += tokens(t"-i {input_path} -o {result_item.tmp_filename}")

        return [Command(svgo, temp_files=(result_item.tmp_filename,))]
