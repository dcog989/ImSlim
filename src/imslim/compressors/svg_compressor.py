import json
import os
from typing import override

from ..binary_resolver import resolve_tool
from ..compressor import Command, Compressor, tokens
from ..result_item import ResultItem
from ..settings_manager import SettingsManager

_SVGO_CONFIG_HEADER = "module.exports = "
_SVGO_CONFIG_FILENAME = ".imslim.svgo.config.cjs"
# csso (svgo's style minifier) crashes on malformed CSS declarations (e.g.
# the broken `enable-;` seen in some generated SVGs), so minifyStyles is
# always disabled; the rest of preset-default still runs.
_SVGO_CONFIG = {
    "plugins": [
        {
            "name": "preset-default",
            "params": {"overrides": {"minifyStyles": False}},
        },
    ]
}
_SVGO_CONFIG_MAXIMUM = {
    "plugins": [
        {
            "name": "preset-default",
            "params": {"overrides": {"minifyStyles": False}},
        },
        {"name": "removeDimensions"},
    ]
}


class SVGCompressor(Compressor):
    def __init__(self, settings: SettingsManager) -> None:
        super().__init__(settings)
        self._shared_config_path: str | None = None

    @override
    @classmethod
    def get_file_type(cls) -> str:
        return "svg"

    @override
    def prepare_batch(self, result_items: list[ResultItem]) -> None:
        """Write the svgo config once per batch instead of once per file."""
        for result_item in result_items:
            if result_item.mime_type != "image/svg+xml":
                continue
            shared_path = os.path.join(
                os.path.dirname(result_item.tmp_filename), _SVGO_CONFIG_FILENAME
            )
            self._write_config(shared_path)
            self._shared_config_path = shared_path
            return

    @override
    def finish_batch(self) -> None:
        if self._shared_config_path is not None:
            self._remove_quietly(self._shared_config_path)
            self._shared_config_path = None

    def _write_config(self, path: str) -> None:
        with open(path, "w") as fp:
            # svgo configs must be CommonJS regardless of the project
            # package.json type, so inline the JSON as module.exports.
            config = _SVGO_CONFIG_MAXIMUM if self.settings.svg_maximum_level else _SVGO_CONFIG
            _res = fp.write(_SVGO_CONFIG_HEADER + json.dumps(config))

    def _config_path(self, result_item: ResultItem) -> str:
        return result_item.tmp_filename + ".config.cjs"

    @override
    def build_command(self, result_item: ResultItem) -> list[Command]:
        svgo = [resolve_tool("svgo")]
        svgo += tokens(t"--config {self._config_path_for(result_item)}")
        svgo += tokens(t"-i {result_item.filename} -o {result_item.tmp_filename}")

        return [Command(svgo)]

    def _config_path_for(self, result_item: ResultItem) -> str:
        # Normal path: the shared per-batch config written in prepare_batch().
        if self._shared_config_path is not None:
            return self._shared_config_path
        # Fallback (batch preparation failed): write a per-file config so
        # individual items can still be compressed.
        path = self._config_path(result_item)
        self._write_config(path)
        return path

    @override
    def get_intermediate_files(self, result_item: ResultItem) -> list[str]:
        # Per-file configs from the fallback need per-item cleanup; the shared
        # per-batch config is removed by finish_batch().
        if self._shared_config_path is None:
            return [self._config_path(result_item)]
        return []
