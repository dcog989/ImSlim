"""Base class for the settings tabs."""

from collections.abc import Callable

from PySide6.QtCore import Signal
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
