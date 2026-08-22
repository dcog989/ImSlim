import os
from typing import override

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent, QPixmap, QResizeEvent
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget

from ._i18n import _


class ModeToggle(QWidget):
    """Lossless / Lossy rocker switch."""

    modeChanged: Signal = Signal(bool)  # True -> lossy

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMinimumSize(160, 32)
        self._lossy: bool = False
        self._track: QRectF = QRectF()
        self._thumb: QRectF = QRectF()
        self._update_geometry(self.width(), self.height())

    def _track_rect(self, w: float, h: float) -> QRectF:
        inset_x = 0
        inset_y = h * 0.08
        track_h = h - 2 * inset_y
        return QRectF(inset_x, inset_y, w, track_h)

    def _thumb_rect(self) -> QRectF:
        margin = 3
        half = (self._track.width() - 2 * margin) / 2
        left = self._track.left() + margin
        if self._lossy:
            left += half
        return QRectF(left, self._track.top() + margin, half, self._track.height() - 2 * margin)

    def _update_geometry(self, w: float, h: float) -> None:
        self._track = self._track_rect(w, h)
        self._refresh_thumb()

    @override
    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._update_geometry(self.width(), self.height())

    def _refresh_thumb(self):
        self._thumb = self._thumb_rect()
        self.update()

    def setLossy(self, lossy: bool) -> None:
        if self._lossy == lossy:
            return
        self._lossy = lossy
        self._refresh_thumb()

    def isLossy(self) -> bool:
        return self._lossy

    @override
    def sizeHint(self) -> QSize:
        return self.minimumSize()

    @override
    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        acc = self.palette().color(self.palette().ColorRole.Highlight)
        base = self.palette().color(self.palette().ColorRole.Mid)
        text = self.palette().color(self.palette().ColorRole.WindowText)
        on_text = self.palette().color(self.palette().ColorRole.HighlightedText)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(base))
        painter.drawRoundedRect(self._track, 7, 7)

        painter.setBrush(QColor(acc))
        painter.drawRoundedRect(self._thumb, 7, 7)

        font = painter.font()
        font.setBold(True)
        font.setPointSize(10)
        painter.setFont(font)

        half = (self._track.width() - 6) / 2
        inactive = QColor(text)
        inactive.setAlphaF(0.5)
        painter.setPen(QColor(on_text) if not self._lossy else QColor(inactive))
        _res = painter.drawText(
            QRectF(self._track.left(), self._track.top(), half, self._track.height()),
            Qt.AlignmentFlag.AlignCenter,
            _("Lossless"),
        )
        painter.setPen(QColor(inactive) if not self._lossy else QColor(on_text))
        _res = painter.drawText(
            QRectF(self._track.left() + half, self._track.top(), half, self._track.height()),
            Qt.AlignmentFlag.AlignCenter,
            _("Lossy"),
        )
        _res = painter.end()

    @override
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.setLossy(not self._lossy)
            self.modeChanged.emit(self._lossy)


def stylized_i_icon(size: int) -> QPixmap:
    """Render the ImSlim logo SVG onto a transparent pixmap of the given size."""
    svg_path = os.path.join(os.path.dirname(__file__), "assets", "imslim.svg")
    renderer = QSvgRenderer(svg_path)
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(p)
    _res = p.end()
    return pm
