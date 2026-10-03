from .binary_resolver import resolve_tool
from .commands import Command
from .formats import DECODER_TOOLS, is_converting, native_inputs
from .image_convert import to_png

__all__ = [
    "decode_commands",
    "is_converting",
    "native_inputs",
]


def decode_commands(source_mime: str, source: str, destination: str) -> list[Command]:
    """Commands that decode `source` to a PNG at `destination`.

    Uses a bundled decoder when one exists, otherwise Qt decodes in-process as
    an action command. Must run off the UI thread; QImage is thread-safe.
    """
    tool = DECODER_TOOLS.get(source_mime)
    if tool is not None:
        argv = [resolve_tool(tool), source, destination]
        return [Command(argv=argv, temp_files=(destination,))]
    return [Command(action=lambda: to_png(source, destination), temp_files=(destination,))]
