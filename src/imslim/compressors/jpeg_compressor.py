from typing import override

from ..batch_options import BatchOptions
from ..binary_resolver import resolve_tool
from ..commands import Command, tokens
from ..compressor import Compressor
from ..conversion import decode_commands
from ..formats import CompressorType
from ..result_item import ResultItem


class JPEGCompressor(Compressor):
    @override
    @classmethod
    def get_file_type(cls) -> CompressorType:
        return CompressorType.JPEG

    def _encoded_path(self, result_item: ResultItem) -> str:
        return result_item.tmp_filename + ".enc.jpg"

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

        # Keep the ICC profile when stripping metadata so colors still render correctly.
        jpegtran += ["-copy", "all" if options.metadata else "icc"]

        jpegtran += ["-outfile", result_item.tmp_filename, input_path]

        return [Command(jpegtran, temp_files=(result_item.tmp_filename,))]

    def _build_lossy_command(
        self, result_item: ResultItem, options: BatchOptions, input_path: str
    ) -> list[Command]:
        commands: list[Command] = []
        encode_input = input_path

        # jpegli can't read JPEG input, so decode to a temporary PNG first.
        # PNG/YUV inputs (native PNG or a conversion intermediate) feed cjpegli directly.
        if result_item.mime_type == "image/jpeg" and not self._input_is_png(
            result_item, input_path
        ):
            intermediate = self._intermediate_path(result_item)
            commands += decode_commands(result_item.mime_type, input_path, intermediate)
            encode_input = intermediate

        encoded_path: str | None = None
        output = result_item.tmp_filename
        if not options.metadata:
            encoded_path = self._encoded_path(result_item)
            output = encoded_path

        cjpegli = tokens(
            t"{resolve_tool('cjpegli')} {encode_input} {output} "
            + t"--quality {options.level('jpg-lossy-level')}"
        )
        cjpegli.append(
            "--progressive_level=2" if options.flag("jpg-progressive") else "--progressive_level=0"
        )

        commands.append(Command(cjpegli, temp_files=(output,)))

        if encoded_path is not None:
            # jpegli carries ICC/EXIF/XMP from the PNG; strip all but the ICC profile
            jpegtran = tokens(
                t"{resolve_tool('jpegtran')} -copy icc -outfile {result_item.tmp_filename} "
                + t"{encoded_path}"
            )
            commands.append(Command(jpegtran, temp_files=(result_item.tmp_filename,)))

        return commands
