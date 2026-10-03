from abc import ABC, abstractmethod
from string.templatelib import Interpolation, Template
from typing import NamedTuple, cast

from .batch_options import BatchOptions
from .conversion import decode_to_png, is_converting, native_inputs
from .formats import CompressorType
from .result_item import ResultItem


class Command(NamedTuple):
    argv: list[str]
    stdout_path: str | None = None
    ignore_errors: bool = False


def tokens(template: Template) -> list[str]:
    """Flatten a t-string into argv tokens for a tool invocation.

    Static text is split on whitespace so flag/value boundaries fall out
    naturally, while each interpolation becomes a single token so values that
    contain spaces remain one argument.
    """
    result: list[str] = []
    for part in template:
        if isinstance(part, Interpolation):
            result.append(str(cast(object, part.value)))
        else:
            result.extend(part.split())
    return result


class Compressor(ABC):
    @classmethod
    @abstractmethod
    def get_file_type(cls) -> CompressorType: ...

    @abstractmethod
    def build_command(self, result_item: ResultItem, options: BatchOptions) -> list[Command]: ...

    def adapt_command(self, argv: list[str], _result_item: ResultItem) -> list[str]:
        return argv

    def get_intermediate_files(self, _result_item: ResultItem, _options: BatchOptions) -> list[str]:
        return []

    def _intermediate_path(self, result_item: ResultItem) -> str:
        return result_item.tmp_filename + ".png"

    def _conversion_intermediate_path(self, result_item: ResultItem) -> str:
        return result_item.tmp_filename + ".convert.png"

    def _input_is_png(self, result_item: ResultItem) -> bool:
        """True when the compressor will read a PNG (native source or a
        pre-decoded conversion intermediate)."""
        return (
            result_item.input_path != result_item.filename or result_item.mime_type == "image/png"
        )

    def conversion_commands(self, result_item: ResultItem, options: BatchOptions) -> list[Command]:
        """Pre-decode a non-native source to PNG when converting to another
        format. Leaves `input_path` pointing at the source (or the file itself)
        when no pre-decode is needed."""
        target = options.target_format
        if not is_converting(target) or result_item.mime_type in native_inputs(target):
            result_item.input_path = result_item.filename
            return []
        intermediate = self._conversion_intermediate_path(result_item)
        result_item.input_path = intermediate
        argv_lists = decode_to_png(result_item.mime_type, result_item.filename, intermediate)
        return [Command(argv) for argv in argv_lists]
