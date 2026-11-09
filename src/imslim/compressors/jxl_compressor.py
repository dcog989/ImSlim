import os
import subprocess
from functools import partial
from typing import override

from ..batch_options import BatchOptions
from ..binary_resolver import resolve_tool
from ..commands import Command, tokens
from ..compressor import ENCODER_THREADS_PER_JOB, Compressor
from ..conversion import decode_commands
from ..formats import CompressorType
from ..jpeg_metadata import extract_metadata
from ..result_item import ResultItem

_JXL_METADATA = ("exif", "xmp", "jumbf")
# JPEG carries no JUMBF here; the other two are parsed out of its APP1 segments.
_JPEG_METADATA = ("exif", "xmp")
# cjxl v0.12: -q 100 is lossless (the -q 100/--lossless flag was removed).
_LOSSLESS_QUALITY = "100"
# jxlinfo reads the container header without decoding pixels, so one probe
# avoids spawning djxl three times for metadata that is not present.
_INFO_TIMEOUT_SECONDS = 10
_INFO_MARKERS = {"exif": "exif", "xmp": "xml", "jumbf": "jumbf"}


def metadata_kinds_from_info(text: str) -> frozenset[str]:
    """Kinds named in jxlinfo output (e.g. 'Brotli-compressed Exif metadata')."""
    lower = text.lower()
    return frozenset(kind for kind, marker in _INFO_MARKERS.items() if marker in lower)


def _sidecar_present(path: str) -> bool:
    try:
        return os.path.getsize(path) > 0
    except OSError:
        return False


def metadata_kinds(path: str) -> frozenset[str]:
    """Metadata kinds present in `path`, or all of them when the probe fails."""
    try:
        completed = subprocess.run(
            [resolve_tool("jxlinfo"), path],
            check=False,
            capture_output=True,
            text=True,
            timeout=_INFO_TIMEOUT_SECONDS,
        )
    except OSError, subprocess.SubprocessError:
        return frozenset(_JXL_METADATA)
    if completed.returncode != 0:
        return frozenset(_JXL_METADATA)
    return metadata_kinds_from_info(completed.stdout)


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
        png_input = self._input_is_png(result_item, input_path)

        # cjxl can't read JXL input, so decode to a temporary PNG first.
        # PNG input (native PNG or a conversion intermediate) feeds cjxl directly.
        if not png_input:
            intermediate = self._intermediate_path(result_item)
            commands += decode_commands(result_item.mime_type, input_path, intermediate)
            encode_input = intermediate

        # The decoders drop EXIF/XMP, so carry them over as sidecars cjxl
        # re-injects with -x. JXL sources use djxl; a JPEG is parsed directly.
        # Other cross-format sources cannot provide metadata.
        extracting_metadata = options.metadata and (
            result_item.mime_type == "image/jpeg" or not png_input
        )
        if extracting_metadata:
            if result_item.mime_type == "image/jpeg":
                commands += self._jpeg_sidecar_commands(result_item)
            else:
                commands += self._djxl_sidecar_commands(
                    result_item, input_path, metadata_kinds(input_path)
                )

        cjxl = [resolve_tool("cjxl")]

        if options.lossy:
            cjxl += tokens(t"-q {options.level('jxl-lossy-level')}")
        else:
            cjxl += ["-q", _LOSSLESS_QUALITY]

        # effort (1-10, default 7): higher -> slower but better compression
        cjxl += tokens(t"-e {options.level('jxl-effort')}")
        cjxl.append(f"--num_threads={ENCODER_THREADS_PER_JOB}")

        if extracting_metadata:
            for kind in _JXL_METADATA:
                cjxl += ["-x", f"{kind}={self._sidecar_path(result_item, kind)}"]
        elif not options.metadata:
            # cjxl reads metadata from its input; strip it explicitly so a
            # decoded JXL/PNG does not carry the source's EXIF/XMP into the output.
            for kind in _JXL_METADATA:
                cjxl += ["-x", f"strip={kind}"]

        cjxl += [encode_input, result_item.tmp_filename]
        commands.append(
            Command(
                cjxl,
                temp_files=(result_item.tmp_filename,),
                adapt=self._prune_metadata_hints,
            )
        )

        return commands

    def _djxl_sidecar_commands(
        self, result_item: ResultItem, source: str, kinds: frozenset[str]
    ) -> list[Command]:
        commands: list[Command] = []
        for kind in _JXL_METADATA:
            if kind not in kinds:
                continue
            sidecar = self._sidecar_path(result_item, kind)
            commands.append(
                Command(
                    tokens(t"{resolve_tool('djxl')} {source} - " + t"--output_format {kind}"),
                    stdout_path=sidecar,
                    ignore_errors=True,
                    temp_files=(sidecar,),
                )
            )
        return commands

    def _jpeg_sidecar_commands(self, result_item: ResultItem) -> list[Command]:
        commands: list[Command] = []
        for kind in _JPEG_METADATA:
            sidecar = self._sidecar_path(result_item, kind)
            commands.append(
                Command(
                    action=partial(extract_metadata, result_item.filename, sidecar, kind),
                    temp_files=(sidecar,),
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
                if has_value and key in _JXL_METADATA and path and not _sidecar_present(path):
                    i += 2
                    continue
            pruned.append(argv[i])
            i += 1
        return pruned
