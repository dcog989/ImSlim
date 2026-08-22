import os
from typing import override

from ..binary_resolver import resolve_tool
from ..compressor import Command, Compressor
from ..result_item import ResultItem

_JXL_METADATA = ("exif", "xmp", "jumbf")


class JXLCompressor(Compressor):
    @override
    @classmethod
    def get_file_type(cls) -> str:
        return "jxl"

    def _intermediate_path(self, result_item: ResultItem) -> str:
        return self._png_intermediate_path(result_item)

    def _sidecar_path(self, result_item: ResultItem, kind: str) -> str:
        return result_item.tmp_filename + "." + kind

    @override
    def build_command(self, result_item: ResultItem) -> list[Command]:
        intermediate = self._intermediate_path(result_item)

        # cjxl can't read JXL input, so decode to a temporary PNG first
        commands: list[Command] = [
            Command([resolve_tool("djxl"), result_item.filename, intermediate])
        ]

        if self.settings.metadata:
            # djxl won't embed EXIF/XMP into the PNG, so extract sidecars and
            # re-inject them via cjxl -x. These are non-fatal: if extraction
            # fails (e.g. metadata absent), the sidecar stays missing and the
            # matching -x argument is pruned in adapt_command().
            for kind in _JXL_METADATA:
                commands.append(
                    Command(
                        [resolve_tool("djxl"), result_item.filename, "-", "--output_format", kind],
                        stdout_path=self._sidecar_path(result_item, kind),
                        ignore_errors=True,
                    )
                )

        cjxl = [resolve_tool("cjxl")]

        # cjxl v0.12: -q 100 is lossless (the -q 100/--lossless flag was removed).
        if self.settings.lossy:
            cjxl += ["-q", str(self.settings.jxl_lossy_level)]
        else:
            cjxl += ["-q", "100"]

        # effort (1-10, default 7): higher -> slower but better compression
        cjxl += ["-e", str(self.settings.jxl_lossless_level)]

        if self.settings.metadata:
            for kind in _JXL_METADATA:
                cjxl += ["-x", f"{kind}={self._sidecar_path(result_item, kind)}"]

        cjxl += [intermediate, result_item.tmp_filename]
        commands.append(Command(cjxl))

        return commands

    @override
    def adapt_command(self, argv: list[str], result_item: ResultItem) -> list[str]:
        if not argv or argv[0] != resolve_tool("cjxl"):
            return argv

        # Prune -x hint args whose sidecar wasn't produced so a missing file
        # can't turn into a hard error.
        pruned: list[str] = []
        i = 0
        while i < len(argv):
            if argv[i] == "-x" and i + 1 < len(argv):
                key, has_value, path = argv[i + 1].partition("=")
                if has_value and key in _JXL_METADATA and path and not os.path.exists(path):
                    i += 2
                    continue
            pruned.append(argv[i])
            i += 1
        return pruned

    @override
    def get_intermediate_files(self, result_item: ResultItem) -> list[str]:
        paths = [self._intermediate_path(result_item)]
        if self.settings.metadata:
            paths += [self._sidecar_path(result_item, kind) for kind in _JXL_METADATA]
        return paths
