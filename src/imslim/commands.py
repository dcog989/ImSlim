from collections.abc import Callable
from string.templatelib import Interpolation, Template
from typing import NamedTuple, cast


class Command(NamedTuple):
    """One pipeline step: an external tool argv or an in-process action.

    Every step declares the temporary files it creates in `temp_files`, so the
    pipeline derives cleanup from the commands instead of each compressor
    mirroring `build_command` in a separate method.
    """

    argv: list[str] | None = None
    action: Callable[[], None] | None = None
    stdout_path: str | None = None
    ignore_errors: bool = False
    temp_files: tuple[str, ...] = ()


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
