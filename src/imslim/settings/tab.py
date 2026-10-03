"""Base class for the settings tabs."""

from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import QWidget

from ..settings_manager import SettingsManager


class SettingsTab(QWidget):
    """Base for a settings tab.

    Settings are written live as the user edits, so tabs only report that
    something changed; the dialog re-emits this to its owner.
    """

    settings_changed: Signal = Signal()

    def __init__(self, settings: SettingsManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings: SettingsManager = settings

    @contextmanager
    def _suspend_signals(self) -> Iterator[None]:
        """Run a block with every child widget's signals blocked.

        Signals are connected while the widgets are built, so populating them
        from stored settings would otherwise fire the change handlers and write
        every value straight back (and report a change for each).
        """
        with ExitStack() as stack:
            for child in self.findChildren(QWidget):
                stack.enter_context(QSignalBlocker(child))
            yield

    def _bool_handler(self, key: str) -> Callable[[bool], None]:
        def handler(checked: bool) -> None:
            self.settings.set_boolean(key, checked)
            self.settings_changed.emit()

        return handler

    def _int_handler(self, key: str) -> Callable[[int], None]:
        def handler(value: int) -> None:
            self.settings.set_int(key, value)
            self.settings_changed.emit()

        return handler
