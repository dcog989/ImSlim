"""Replace a file's contents through a sibling temp file."""

import os
from collections.abc import Callable
from pathlib import Path
from typing import IO


def rewrite_file(target: str, writer: Callable[[IO[bytes]], None]) -> None:
    """Write `target` via `writer`, replacing it only when the write succeeds.

    The writer gets a sibling temp file, so a full disk or an I/O error leaves
    the original bytes untouched. Raises whatever the writer raises.
    """
    temp = target + ".rewrite"
    try:
        with open(temp, "wb") as output:
            writer(output)
        os.replace(temp, target)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise
