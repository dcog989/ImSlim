import sys
import threading

from .binary_resolver import resolve_tool
from .commands import Command
from .formats import DECODER_TOOLS

# Decoding happens in the compression pool, sized for subprocesses. A full
# image is hundreds of MB for a large source, so only a couple may decode at once.
_DECODE_SLOTS = threading.Semaphore(2)


def decode_commands(source_mime: str, source: str, destination: str) -> list[Command]:
    """Commands that decode `source` to a PNG at `destination`.

    Uses a bundled decoder when one exists; otherwise Qt decodes in a helper
    process, so a batch cancel or the per-tool timeout can stop a slow decode.
    """
    tool = DECODER_TOOLS.get(source_mime)
    if tool is not None:
        return [
            Command(
                argv=[resolve_tool(tool), source, destination],
                temp_files=(destination,),
            )
        ]
    return [_qt_decode_command(source, destination)]


def _qt_decode_command(source: str, destination: str) -> Command:
    if getattr(sys, "frozen", False):
        argv = [sys.executable, "--decode-png", source, destination]
    else:
        argv = [sys.executable, "-m", "imslim.image_convert", source, destination]
    return Command(argv=argv, temp_files=(destination,), limit=_DECODE_SLOTS)
