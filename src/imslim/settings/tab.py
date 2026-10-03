"""Shared helpers for the settings tabs."""

from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager

from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import QWidget

from ..settings_manager import SettingsManager


@contextmanager
def suspend_signals(widget: QWidget) -> Iterator[None]:
    """Run a block with every child widget's signals blocked.

    Signals are connected while the widgets are built, so populating them
    from stored settings would otherwise fire the change handlers and write
    every value straight back (and report a change for each).
    """
    with ExitStack() as stack:
        for child in widget.findChildren(QWidget):
            stack.enter_context(QSignalBlocker(child))
        yield


def bool_handler(
    settings: SettingsManager, changed: Callable[[], None], key: str
) -> Callable[[bool], None]:
    def handler(checked: bool) -> None:
        settings.set_boolean(key, checked)
        changed()

    return handler


def int_handler(
    settings: SettingsManager, changed: Callable[[], None], key: str
) -> Callable[[int], None]:
    def handler(value: int) -> None:
        settings.set_int(key, value)
        changed()

    return handler
