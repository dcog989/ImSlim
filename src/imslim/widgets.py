"""Small widgets shared by more than one column."""

import html
from typing import override

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QLabel, QWidget


def plain_tooltip(text: str) -> str:
    """Tooltip text shown literally; Qt would otherwise read a path as HTML."""
    return "<qt>" + html.escape(text).replace("\n", "<br>") + "</qt>"


class ElidedLabel(QLabel):
    """A single-line label that elides in the middle instead of clipping."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full_text: str = text
        # Filenames are data, not markup: a name like <b>x.png</b> must not be
        # parsed as rich text.
        self.setTextFormat(Qt.TextFormat.PlainText)
        super().setText(text)

    @override
    def setText(self, text: str) -> None:
        self._full_text = text
        self._apply_elide()

    @override
    def sizeHint(self) -> QSize:
        # The displayed text is the elided copy, so its own hint keeps the label
        # at the old, shorter width when the real text grows. Prefer the full
        # text here; the label still shrinks below it when space runs out.
        hint = super().sizeHint()
        width = self.fontMetrics().horizontalAdvance(self._full_text)
        return QSize(max(hint.width(), width), hint.height())

    @override
    def minimumSizeHint(self) -> QSize:
        # QLabel reports the full text width as its minimum, so a row would never
        # shrink below the longest error message. Only the height matters.
        return QSize(0, super().minimumSizeHint().height())

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
