import subprocess
import sys
import threading
from contextlib import nullcontext
from functools import partial

from .binary_resolver import resolve_tool
from .commands import Command
from .formats import DECODER_TOOLS
from .png_metadata import normalize_png_exif

# Decoding happens in the compression pool, sized for subprocesses. A full
# image is hundreds of MB for a large source, so only a couple may decode at once.
_DECODE_SLOTS = threading.Semaphore(2)
_NORMALIZE_SUFFIX = ".normalize.png"


def decode_commands(
    source_mime: str,
    source: str,
    destination: str,
    *,
    apply_orientation: bool = False,
) -> list[Command]:
    """Commands that decode `source` to a PNG at `destination`.

    Uses a bundled decoder when one exists; otherwise Qt decodes in a helper
    process, so a batch cancel or the per-tool timeout can stop a slow decode.
    `apply_orientation` forces the Qt decoder, which applies the EXIF
    orientation that djpegli ignores.
    """
    tool = DECODER_TOOLS.get(source_mime)
    if tool is not None and not (apply_orientation and source_mime == "image/jpeg"):
        commands = [
            Command(
                argv=[resolve_tool(tool), source, destination],
                temp_files=(destination,),
                limit=_DECODE_SLOTS,
            )
        ]
        if source_mime == "image/avif":
            # avifdec writes the JPEG-style Exif header into PNG's eXIf, which
            # avifenc and libpng reject; fix the chunk before the next step.
            temp = destination + _NORMALIZE_SUFFIX
            commands.append(
                Command(
                    action=partial(normalize_png_exif, destination, temp),
                    temp_files=(temp,),
                )
            )
        return commands
    return [_qt_decode_command(source, destination)]


def run_commands(commands: list[Command], timeout: float) -> None:
    """Run decode commands in order, honouring each command's concurrency limit."""
    for command in commands:
        with command.limit if command.limit is not None else nullcontext():
            if command.argv is not None:
                _res = subprocess.run(
                    command.argv,
                    check=True,
                    capture_output=True,
                    timeout=timeout,
                )
            elif command.action is not None:
                command.action()


def _qt_decode_command(source: str, destination: str) -> Command:
    if getattr(sys, "frozen", False):
        argv = [sys.executable, "--decode-png", source, destination]
    else:
        argv = [sys.executable, "-m", "imslim.image_convert", source, destination]
    return Command(argv=argv, temp_files=(destination,), limit=_DECODE_SLOTS)
