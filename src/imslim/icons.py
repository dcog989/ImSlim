import math
import os
from collections.abc import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)

IMSLIM_ICON_PATH = os.path.join(os.path.dirname(__file__), "assets", "imslim.svg")


def imslim_icon() -> QIcon:
    """The application icon, loaded from the bundled SVG asset.

    Wrapped in a concrete high-resolution raster so window managers (e.g. KDE's
    alt-tab switcher) receive a crisp icon instead of upscaling a small one.
    """
    return QIcon(QIcon(IMSLIM_ICON_PATH).pixmap(1024))


def _apply_icon_stroke(painter: QPainter, color: QColor, size: float) -> float:
    """Apply the shared icon stroke (round caps/joins, size-scaled width with a
    legibility floor) to `painter`, returning the width for detail sizing."""
    width = max(1.8, size * 0.09)
    painter.setPen(
        QPen(
            color,
            width,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
    )
    painter.setBrush(Qt.BrushStyle.NoBrush)
    return width


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


def download_icon(color: QColor, size: int = 20) -> QIcon:
    """A down arrow into a tray (Lucide 'import'), matching the other icons' stroke."""

    def draw(painter: QPainter, s: float) -> None:
        _res = _apply_icon_stroke(painter, color, s)
        cx = s / 2
        # M12 3v12 / m8 11 4 4 4-4
        painter.drawLine(QPointF(cx, s * 0.125), QPointF(cx, s * 0.625))
        painter.drawLine(QPointF(s * 0.3333, s * 0.4583), QPointF(cx, s * 0.625))
        painter.drawLine(QPointF(s * 0.6667, s * 0.4583), QPointF(cx, s * 0.625))
        # M8 5H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-4
        tray = QPainterPath()
        tray.moveTo(s * 0.3333, s * 0.2083)
        tray.lineTo(s * 0.1667, s * 0.2083)
        tray.quadTo(s * 0.0833, s * 0.2083, s * 0.0833, s * 0.2917)
        tray.lineTo(s * 0.0833, s * 0.7083)
        tray.quadTo(s * 0.0833, s * 0.7917, s * 0.1667, s * 0.7917)
        tray.lineTo(s * 0.8333, s * 0.7917)
        tray.quadTo(s * 0.9167, s * 0.7917, s * 0.9167, s * 0.7083)
        tray.lineTo(s * 0.9167, s * 0.2917)
        tray.quadTo(s * 0.9167, s * 0.2083, s * 0.8333, s * 0.2083)
        tray.lineTo(s * 0.6667, s * 0.2083)
        painter.drawPath(tray)

    return _painted_icon(size, draw)


def chevron_left_icon(color: QColor, size: int = 20) -> QIcon:
    """A left-pointing chevron (Lucide 'chevron-left'), matching the other icons' stroke."""

    def draw(painter: QPainter, s: float) -> None:
        _res = _apply_icon_stroke(painter, color, s)
        # M15 18l-6-6 6-6
        painter.drawLine(QPointF(s * 0.625, s * 0.75), QPointF(s * 0.375, s * 0.5))
        painter.drawLine(QPointF(s * 0.375, s * 0.5), QPointF(s * 0.625, s * 0.25))

    return _painted_icon(size, draw)


def circle_off_icon(color: QColor, size: int = 20) -> QIcon:
    """A circle with a diagonal slash, matching the other icons' stroke weight."""

    def draw(painter: QPainter, s: float) -> None:
        pen = _apply_icon_stroke(painter, color, s)
        inset = pen
        rect = QRectF(inset, inset, s - 2 * inset, s - 2 * inset)
        painter.drawEllipse(rect)
        painter.drawLine(QPointF(s * 0.24, s * 0.76), QPointF(s * 0.76, s * 0.24))

    return _painted_icon(size, draw)


def shield_alert_icon(color: QColor, size: int = 20) -> QIcon:
    """A shield with an exclamation mark, matching the other icons' stroke weight."""

    def draw(painter: QPainter, s: float) -> None:
        pen = _apply_icon_stroke(painter, color, s)
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
        _res = _apply_icon_stroke(painter, color, s)
        painter.drawLine(QPointF(s * 0.5, s * 0.28), QPointF(s * 0.5, s * 0.58))

    return _painted_icon(size, draw)


def triangle_alert_icon(color: QColor, size: int = 20) -> QIcon:
    """An alert triangle with an exclamation mark (Lucide 'triangle-alert')."""

    def draw(painter: QPainter, s: float) -> None:
        pen = _apply_icon_stroke(painter, color, s)
        path = QPainterPath()
        path.moveTo(s * 0.5, s * 0.11)
        path.lineTo(s * 0.08, s * 0.83)
        path.lineTo(s * 0.92, s * 0.83)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawLine(QPointF(s * 0.5, s * 0.4), QPointF(s * 0.5, s * 0.62))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(QPointF(s * 0.5, s * 0.73), pen * 0.8, pen * 0.8)

    return _painted_icon(size, draw)


def gear_icon(color: QColor, size: int = 20) -> QIcon:
    """A simple gear: an outlined ring with eight teeth, matching the other
    icons' stroke weight so the header icons look consistent."""

    def draw(painter: QPainter, s: float) -> None:
        cx, cy = s / 2, s / 2
        tip_r = s * 0.47
        root_r = s * 0.36
        hub_r = s * 0.15
        teeth = 8
        points: list[QPointF] = []
        for i in range(2 * teeth):
            angle = math.pi * i / teeth
            radius = tip_r if i % 2 == 0 else root_r
            points.append(QPointF(cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
        _res = _apply_icon_stroke(painter, color, s)
        painter.drawPolygon(QPolygonF(points))
        painter.drawEllipse(QPointF(cx, cy), hub_r, hub_r)

    return _painted_icon(size, draw)
