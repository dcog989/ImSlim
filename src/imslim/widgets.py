import math
import os
from collections.abc import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF

IMSLIM_ICON_PATH = os.path.join(os.path.dirname(__file__), "assets", "imslim.svg")


def imslim_icon() -> QIcon:
    """The application icon, loaded from the bundled SVG asset.

    Wrapped in a concrete high-resolution raster so window managers (e.g. KDE's
    alt-tab switcher) receive a crisp icon instead of upscaling a small one.
    """
    return QIcon(QIcon(IMSLIM_ICON_PATH).pixmap(1024))


def _painted_icon(size: int, draw: Callable[[QPainter, float], None]) -> QIcon:
    """Render a monochrome icon with QPainter on a transparent, HiDPI-safe pixmap."""
    scale = 2.0
    pixmap = QPixmap(int(size * scale), int(size * scale))
    pixmap.setDevicePixelRatio(scale)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    draw(painter, float(size))
    _res = painter.end()
    return QIcon(pixmap)


def info_icon(color: QColor, size: int = 20) -> QIcon:
    """An 'i' inside a circle, sharing gear_icon()'s stroke weight."""

    def draw(painter: QPainter, s: float) -> None:
        pen = max(1.8, s * 0.09)
        cx, cy = s / 2, s / 2
        inset = pen
        rect = QRectF(inset, inset, s - 2 * inset, s - 2 * inset)
        painter.setPen(QPen(color, pen, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(rect)
        r = (s - 2 * inset) / 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(QPointF(cx, cy - r * 0.48), pen * 0.8, pen * 0.8)
        painter.setPen(QPen(color, pen, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(QPointF(cx, cy - r * 0.18), QPointF(cx, cy + r * 0.45))

    return _painted_icon(size, draw)


def close_icon(color: QColor, size: int = 20) -> QIcon:
    """A circle with an X, matching info_icon()'s stroke weight."""

    def draw(painter: QPainter, s: float) -> None:
        pen = max(1.8, s * 0.09)
        inset = pen
        rect = QRectF(inset, inset, s - 2 * inset, s - 2 * inset)
        painter.setPen(QPen(color, pen, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(rect)
        pad = s * 0.30
        painter.drawLine(QPointF(pad, pad), QPointF(s - pad, s - pad))
        painter.drawLine(QPointF(s - pad, pad), QPointF(pad, s - pad))

    return _painted_icon(size, draw)


def gear_icon(color: QColor, size: int = 20) -> QIcon:
    """A simple gear: an outlined ring with eight teeth, matching info_icon()'s
    stroke weight so the header icons look consistent."""

    def draw(painter: QPainter, s: float) -> None:
        pen = max(1.8, s * 0.09)
        cx, cy = s / 2, s / 2
        tip_r = s * 0.47
        root_r = s * 0.36
        hub_r = s * 0.15
        teeth = 8
        points = []
        for i in range(2 * teeth):
            angle = math.pi * i / teeth
            radius = tip_r if i % 2 == 0 else root_r
            points.append(QPointF(cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
        painter.setPen(
            QPen(
                color,
                pen,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPolygon(QPolygonF(points))
        painter.drawEllipse(QPointF(cx, cy), hub_r, hub_r)

    return _painted_icon(size, draw)
