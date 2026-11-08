"""Small widgets shared by more than one column."""

from typing import override

from PySide6.QtCore import Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QLabel, QWidget


class ElidedLabel(QLabel):
    """A single-line label that elides in the middle instead of clipping."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full_text: str = text
        # Without an explicit minimum a QLabel refuses to shrink below its full
        # text width, starving the labels next to it.
        self.setMinimumWidth(0)
        super().setText(text)

    @override
    def setText(self, text: str) -> None:
        self._full_text = text
        self._apply_elide()

    def _apply_elide(self) -> None:
        width = self.width()
        if width <= 0:
            super().setText(self._full_text)
            return
        super().setText(
            self.fontMetrics().elidedText(self._full_text, Qt.TextElideMode.ElideMiddle, width)
        )

    @override
    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._apply_elide()
