from abc import ABC, abstractmethod

from .batch_options import BatchOptions
from .commands import Command
from .conversion import decode_commands
from .formats import CompressorType, is_converting, native_inputs
from .result_item import ResultItem


class Compressor(ABC):
    @classmethod
    @abstractmethod
    def get_file_type(cls) -> CompressorType: ...

    def commands(self, result_item: ResultItem, options: BatchOptions) -> list[Command]:
        """Full pipeline: generic conversion pre-decode plus the format build.

        Pure: produces commands only and never mutates the result item.
        """
        decode, input_path = self._conversion_commands(result_item, options)
        return decode + self.build_command(result_item, options, input_path)

    @abstractmethod
    def build_command(
        self, result_item: ResultItem, options: BatchOptions, input_path: str
    ) -> list[Command]: ...

    def adapt_command(self, argv: list[str], _result_item: ResultItem) -> list[str]:
        return argv

    def _intermediate_path(self, result_item: ResultItem) -> str:
        return result_item.tmp_filename + ".png"

    def _conversion_intermediate_path(self, result_item: ResultItem) -> str:
        return result_item.tmp_filename + ".convert.png"

    def _input_is_png(self, result_item: ResultItem, input_path: str) -> bool:
        """True when the compressor will read a PNG (native source or a
        pre-decoded conversion intermediate)."""
        return input_path != result_item.filename or result_item.mime_type == "image/png"

    def _conversion_commands(
        self, result_item: ResultItem, options: BatchOptions
    ) -> tuple[list[Command], str]:
        """Pre-decode a non-native source to PNG when converting to another
        format. Returns the decode commands and the path the encoder reads."""
        target = options.target_format
        if not is_converting(target) or result_item.mime_type in native_inputs(target):
            return [], result_item.filename
        intermediate = self._conversion_intermediate_path(result_item)
        commands = decode_commands(result_item.mime_type, result_item.filename, intermediate)
        return commands, intermediate
