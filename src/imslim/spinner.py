from typing import override

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget


class Spinner(QWidget):
    """A rotating arc used as a busy indicator."""

    def __init__(self, size: int = 120, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._angle: int = 0
        self._timer: QTimer = QTimer(self)
        self._timer.setInterval(16)
        _res = self._timer.timeout.connect(self._advance)

    def start(self) -> None:
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def _advance(self) -> None:
        self._angle = (self._angle + 6) % 360
        self.update()

    @override
    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = self.palette().color(self.palette().ColorRole.Text)
        pen = QPen(
            color,
            6,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
        painter.setPen(pen)
        painter.drawArc(
            QRectF(6, 6, self.width() - 12, self.height() - 12),
            -self._angle * 16,
            100 * 16,
        )
        _res = painter.end()
