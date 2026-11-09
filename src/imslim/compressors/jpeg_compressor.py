from functools import partial
from typing import override

from ..batch_options import BatchOptions
from ..binary_resolver import resolve_tool
from ..commands import Command, tokens
from ..compressor import Compressor
from ..conversion import decode_commands
from ..exif import jpeg_orientation
from ..formats import CompressorType
from ..jpeg_metadata import strip_metadata, transfer_metadata
from ..result_item import ResultItem

# cjpegli cannot encode losslessly; quality 100 is the closest it gets, so a
# lossless request must not fall back to the lossy knob's default of 90.
_LOSSLESS_QUALITY = 100

# EXIF Orientation -> the matching lossless jpegtran transform.
_ORIENTATION_TRANSFORMS: dict[int, list[str]] = {
    2: ["-flip", "horizontal"],
    3: ["-rotate", "180"],
    4: ["-flip", "vertical"],
    5: ["-transpose"],
    6: ["-rotate", "90"],
    7: ["-transverse"],
    8: ["-rotate", "270"],
}


class JPEGCompressor(Compressor):
    @override
    @classmethod
    def get_file_type(cls) -> CompressorType:
        return CompressorType.JPEG

    @override
    def build_command(
        self, result_item: ResultItem, options: BatchOptions, input_path: str
    ) -> list[Command]:
        # jpegtran only re-encodes JPEG losslessly; any other source (or a
        # pre-decoded conversion intermediate) must take the lossy cjpegli path.
        if options.lossy or self._input_is_png(result_item, input_path):
            return self._build_lossy_command(result_item, options, input_path)
        return self._build_lossless_command(result_item, options, input_path)

    def _build_lossless_command(
        self, result_item: ResultItem, options: BatchOptions, input_path: str
    ) -> list[Command]:
        jpegtran = tokens(t"{resolve_tool('jpegtran')} -optimize")

        if options.flag("jpg-progressive"):
            jpegtran.append("-progressive")

        if not options.metadata:
            # Stripping the EXIF tag would leave the pixels unrotated, so apply
            # the orientation losslessly first.
            jpegtran += _ORIENTATION_TRANSFORMS.get(jpeg_orientation(input_path), [])

        # Keep the ICC profile when stripping metadata so colors still render correctly.
        jpegtran += ["-copy", "all" if options.metadata else "icc"]

        jpegtran += ["-outfile", result_item.tmp_filename, input_path]

        commands = [Command(jpegtran, temp_files=(result_item.tmp_filename,))]
        if not options.metadata:
            # mozjpeg may write the original file instead of a smaller
            # re-encode, so strip in-process as well.
            commands.append(Command(action=partial(strip_metadata, result_item.tmp_filename)))
        return commands

    def _build_lossy_command(
        self, result_item: ResultItem, options: BatchOptions, input_path: str
    ) -> list[Command]:
        commands: list[Command] = []
        encode_input = input_path

        # jpegli can't read JPEG input, so decode to a temporary PNG first.
        # PNG inputs (native PNG or a conversion intermediate) feed cjpegli directly.
        # Stripping metadata decodes with Qt so the EXIF orientation is applied
        # before the tag disappears.
        if result_item.mime_type == "image/jpeg" and not self._input_is_png(
            result_item, input_path
        ):
            intermediate = self._intermediate_path(result_item)
            commands += decode_commands(
                result_item.mime_type,
                input_path,
                intermediate,
                apply_orientation=not options.metadata,
            )
            encode_input = intermediate

        quality = options.level("jpg-lossy-level") if options.lossy else _LOSSLESS_QUALITY
        cjpegli = tokens(
            t"{resolve_tool('cjpegli')} {encode_input} {result_item.tmp_filename} "
            + t"--quality {quality}"
        )
        cjpegli.append(
            "--progressive_level=2" if options.flag("jpg-progressive") else "--progressive_level=0"
        )
        commands.append(Command(cjpegli, temp_files=(result_item.tmp_filename,)))

        if options.metadata:
            if result_item.mime_type == "image/jpeg":
                # Metadata is kept, but the encoder was fed a PNG decoded from the
                # original and that PNG carries no EXIF/XMP, so copy it back over.
                commands.append(self._metadata_command(result_item))
        else:
            commands.append(Command(action=partial(strip_metadata, result_item.tmp_filename)))

        return commands

    @staticmethod
    def _metadata_command(result_item: ResultItem) -> Command:
        return Command(
            action=partial(transfer_metadata, result_item.filename, result_item.tmp_filename)
        )
