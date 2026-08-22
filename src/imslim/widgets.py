import math
import os
from collections.abc import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF

IMSLIM_ICON_PATH = os.path.join(os.path.dirname(__file__), "assets", "imslim.svg")


def muted_color(fg: QColor, bg: QColor, factor: float = 0.5) -> QColor:
    """Blend the foreground color `factor` toward `bg`.

    Used for muted but readable text on both light and dark themes instead of
    a hardcoded gray. `factor` is the weight given to `bg`; 0.0 keeps `fg`
    unchanged, 1.0 yields `bg` exactly.
    """
    return QColor(
        round(fg.red() * (1.0 - factor) + bg.red() * factor),
        round(fg.green() * (1.0 - factor) + bg.green() * factor),
        round(fg.blue() * (1.0 - factor) + bg.blue() * factor),
    )


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


def circle_off_icon(color: QColor, size: int = 20) -> QIcon:
    """A circle with a diagonal slash, matching info_icon()'s stroke weight."""

    def draw(painter: QPainter, s: float) -> None:
        pen = max(1.8, s * 0.09)
        inset = pen
        rect = QRectF(inset, inset, s - 2 * inset, s - 2 * inset)
        painter.setPen(QPen(color, pen, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(rect)
        painter.drawLine(QPointF(s * 0.24, s * 0.76), QPointF(s * 0.76, s * 0.24))

    return _painted_icon(size, draw)


def shield_alert_icon(color: QColor, size: int = 20) -> QIcon:
    """A shield with an exclamation mark, matching info_icon()'s stroke weight."""

    def draw(painter: QPainter, s: float) -> None:
        pen = max(1.8, s * 0.09)
        painter.setPen(QPen(color, pen, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath()
        path.moveTo(s * 0.5, s * 0.06)
        path.lineTo(s * 0.16, s * 0.2)
        path.lineTo(s * 0.2, s * 0.58)
        path.quadTo(s * 0.28, s * 0.84, s * 0.5, s * 0.94)
        path.quadTo(s * 0.72, s * 0.84, s * 0.8, s * 0.58)
        path.lineTo(s * 0.84, s * 0.2)
        path.closeSubpath()
        painter.drawPath(path)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(QPointF(s * 0.5, s * 0.72), pen * 0.8, pen * 0.8)
        painter.setPen(QPen(color, pen, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(QPointF(s * 0.5, s * 0.28), QPointF(s * 0.5, s * 0.58))

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
