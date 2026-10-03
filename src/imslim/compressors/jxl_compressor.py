import os
from typing import override

from ..batch_options import BatchOptions
from ..binary_resolver import resolve_tool
from ..commands import Command, tokens
from ..compressor import Compressor
from ..conversion import decode_commands
from ..formats import CompressorType
from ..result_item import ResultItem

_JXL_METADATA = ("exif", "xmp", "jumbf")
# cjxl v0.12: -q 100 is lossless (the -q 100/--lossless flag was removed).
_LOSSLESS_QUALITY = "100"


class JXLCompressor(Compressor):
    @override
    @classmethod
    def get_file_type(cls) -> CompressorType:
        return CompressorType.JXL

    def _sidecar_path(self, result_item: ResultItem, kind: str) -> str:
        return result_item.tmp_filename + "." + kind

    @override
    def build_command(
        self, result_item: ResultItem, options: BatchOptions, input_path: str
    ) -> list[Command]:
        commands: list[Command] = []
        encode_input = input_path
        extracting_metadata = False

        # cjxl can't read JXL input, so decode to a temporary PNG first.
        # PNG input (native PNG or a conversion intermediate) feeds cjxl directly;
        # cross-format metadata sidecars can't be extracted, so they are skipped.
        if not self._input_is_png(result_item, input_path):
            intermediate = self._intermediate_path(result_item)
            commands += decode_commands(result_item.mime_type, input_path, intermediate)
            encode_input = intermediate
            extracting_metadata = options.metadata

        if extracting_metadata:
            # djxl won't embed EXIF/XMP into the PNG, so extract sidecars and
            # re-inject them via cjxl -x. These are non-fatal: if extraction
            # fails (e.g. metadata absent), the sidecar stays missing and the
            # matching -x argument is pruned in _prune_metadata_hints().
            for kind in _JXL_METADATA:
                sidecar = self._sidecar_path(result_item, kind)
                commands.append(
                    Command(
                        tokens(
                            t"{resolve_tool('djxl')} {input_path} - " + t"--output_format {kind}"
                        ),
                        stdout_path=sidecar,
                        ignore_errors=True,
                        temp_files=(sidecar,),
                    )
                )

        cjxl = [resolve_tool("cjxl")]

        if options.lossy:
            cjxl += tokens(t"-q {options.level('jxl-lossy-level')}")
        else:
            cjxl += ["-q", _LOSSLESS_QUALITY]

        # effort (1-10, default 7): higher -> slower but better compression
        cjxl += tokens(t"-e {options.level('jxl-effort')}")

        if extracting_metadata:
            for kind in _JXL_METADATA:
                cjxl += ["-x", f"{kind}={self._sidecar_path(result_item, kind)}"]

        cjxl += [encode_input, result_item.tmp_filename]
        commands.append(
            Command(
                cjxl,
                temp_files=(result_item.tmp_filename,),
                adapt=self._prune_metadata_hints,
            )
        )

        return commands

    def _prune_metadata_hints(self, argv: list[str]) -> list[str]:
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
