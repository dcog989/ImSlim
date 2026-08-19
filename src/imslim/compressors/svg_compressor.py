import json

from ..binary_resolver import resolve_tool
from ..compressor import Command, Compressor
from ..result_item import ResultItem

_SVGO_CONFIG_HEADER = "module.exports = "
_SVGO_CONFIG = {
    "plugins": [
        {"name": "preset-default"},
        {"name": "removeDimensions"},
    ]
}


class SVGCompressor(Compressor):
    @classmethod
    def get_file_type(cls) -> str:
        return "svg"

    def _config_path(self, result_item: ResultItem) -> str:
        return result_item.tmp_filename + ".config.cjs"

    def build_command(self, result_item: ResultItem) -> list[Command]:
        config_path = self._config_path(result_item)

        svgo = [resolve_tool("svgo")]
        if self.settings.svg_maximum_level:
            # svgo 3 dropped --enable; extra plugins are enabled via a config
            # file. sortAttrs already runs in preset-default, so only
            # removeDimensions is added here.
            svgo += ["--config", config_path]
        svgo += ["-i", result_item.filename, "-o", result_item.tmp_filename]

        return [Command(svgo)]

    def adapt_command(self, argv: list[str], result_item: ResultItem) -> list[str]:
        if "--config" in argv:
            with open(self._config_path(result_item), "w") as fp:
                # svgo configs must be CommonJS regardless of the project
                # package.json type, so inline the JSON as module.exports.
                fp.write(_SVGO_CONFIG_HEADER + json.dumps(_SVGO_CONFIG))
        return argv

    def get_intermediate_files(self, result_item: ResultItem) -> list[str]:
        return [self._config_path(result_item)] if self.settings.svg_maximum_level else []
