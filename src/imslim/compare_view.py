"""Column 3: the original and the processed image, side by side (stacked)."""

import math
import time
from typing import override

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QImage,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QResizeEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSplitter, QVBoxLayout, QWidget

from ._i18n import _
from .format import sizeof_fmt
from .preview import load_preview
from .theme import apply_muted_palette, splitter_stylesheet
from .widgets import ElidedLabel
from .workers import Task, start_task

_MIN_ZOOM = 1.0
_MAX_ZOOM = 8.0
_ZOOM_STEP = 1.25
# Freed pixels beyond the fit are limited so a drag cannot lose the image.
_PANE_MARGIN = 8
# The decoded image is already capped in preview.py; this bounds the *display*
# zoom to roughly 2x the viewport area, as the design asks.
_VIEWPORT_AREA_BUDGET = 2.0


class _PreviewTask(Task):
    """Decode one image off the UI thread; emits (token, QImage | None)."""

    loaded: Signal = Signal(int, object)

    def __init__(self, token: int, path: str) -> None:
        super().__init__()
        self._token: int = token
        self._path: str = path

    @override
    def run(self) -> None:
        try:
            self.loaded.emit(self._token, load_preview(self._path))
        finally:
            self.finished.emit()


class ImagePane(QWidget):
    """One image fitted to the pane, with ctrl+wheel zoom and drag panning."""

    zoom_requested: Signal = Signal(float)

    def __init__(self, placeholder: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._image: QImage | None = None
        self._placeholder: str = placeholder
        self._zoom: float = _MIN_ZOOM
        self._pan: QPointF = QPointF()
        self._last_pos: QPointF = QPointF()
        self.setMinimumHeight(120)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def set_image(self, image: QImage | None, placeholder: str | None = None) -> None:
        self._image = image
        if placeholder is not None:
            self._placeholder = placeholder
        self._zoom = _MIN_ZOOM
        self._pan = QPointF()
        self.update()

    def set_placeholder(self, text: str) -> None:
        self.set_image(None, text)

    def has_image(self) -> bool:
        return self._image is not None

    # ------------------------------------------------------------------ zoom
    def zoom_in(self) -> None:
        self._apply_zoom(self._zoom * _ZOOM_STEP)

    def zoom_out(self) -> None:
        self._apply_zoom(self._zoom / _ZOOM_STEP)

    def scale_zoom(self, factor: float) -> None:
        self._apply_zoom(self._zoom * factor)

    def fit(self) -> None:
        self._apply_zoom(_MIN_ZOOM)

    def _apply_zoom(self, zoom: float) -> None:
        if self._image is None:
            return
        self._zoom = max(_MIN_ZOOM, min(self._max_zoom(), zoom))
        self._clamp_pan()
        self.update()

    def _max_zoom(self) -> float:
        image = self._image
        if image is None:
            return _MAX_ZOOM
        fit = self._fit_scale()
        fitted_area = (image.width() * fit) * (image.height() * fit)
        viewport = max(1.0, float(self.width() * self.height()))
        if fitted_area <= 0:
            return _MAX_ZOOM
        cap = math.sqrt(_VIEWPORT_AREA_BUDGET * viewport / fitted_area)
        return max(_MIN_ZOOM, min(_MAX_ZOOM, cap))

    def _fit_scale(self) -> float:
        image = self._image
        if image is None or image.width() <= 0 or image.height() <= 0:
            return 1.0
        available_w = max(1, self.width() - 2 * _PANE_MARGIN)
        available_h = max(1, self.height() - 2 * _PANE_MARGIN)
        return min(available_w / image.width(), available_h / image.height())

    # ----------------------------------------------------------------- paint
    @override
    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().color(self.palette().ColorRole.Base))
        image = self._image
        if image is None:
            apply_muted_palette(self)
            painter.setPen(self.palette().color(self.palette().ColorRole.WindowText))
            _res = painter.drawText(
                self.rect().adjusted(_PANE_MARGIN, _PANE_MARGIN, -_PANE_MARGIN, -_PANE_MARGIN),
                int(Qt.AlignmentFlag.AlignCenter) | int(Qt.TextFlag.TextWordWrap),
                self._placeholder,
            )
            _res = painter.end()
            return
        scale = self._fit_scale() * self._zoom
        width = image.width() * scale
        height = image.height() * scale
        target = QRectF(
            (self.width() - width) / 2 + self._pan.x(),
            (self.height() - height) / 2 + self._pan.y(),
            width,
            height,
        )
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawImage(target, image)
        _res = painter.end()

    # ------------------------------------------------------------- interaction
    @override
    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            steps = event.angleDelta().y() / 120.0
            if steps:
                self.zoom_requested.emit(steps)
                event.accept()
                return
        event.ignore()

    def _clamp_pan(self) -> None:
        image = self._image
        if image is None:
            self._pan = QPointF()
            return
        scale = self._fit_scale() * self._zoom
        overflow_x = max(0.0, (image.width() * scale - self.width()) / 2)
        overflow_y = max(0.0, (image.height() * scale - self.height()) / 2)
        self._pan = QPointF(
            max(-overflow_x, min(overflow_x, self._pan.x())),
            max(-overflow_y, min(overflow_y, self._pan.y())),
        )

    def _dragging(self) -> bool:
        return self._zoom > _MIN_ZOOM

    @override
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._dragging():
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self._last_pos = event.position()
            event.accept()
            return
        super().mousePressEvent(event)

    @override
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton and self._dragging():
            delta = event.position() - self._last_pos
            self._last_pos = event.position()
            self._pan += delta
            self._clamp_pan()
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    @override
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)

    @override
    def resizeEvent(self, event: QResizeEvent) -> None:
        self._clamp_pan()
        super().resizeEvent(event)


class CompareView(QWidget):
    """Vertical comparison of the source and the processed output."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._request: int = 0
        self._tokens: dict[ImagePane, int] = {}
        self._pending: dict[int, ImagePane] = {}
        self._original: ImagePane = ImagePane(_("Select a file to preview it."))
        self._processed: ImagePane = ImagePane(_("The processed image appears here."))

        self.path_label: ElidedLabel = ElidedLabel()
        self.size_label: QLabel = QLabel()
        self.time_label: QLabel = QLabel()
        for label in (self.size_label, self.time_label):
            apply_muted_palette(label)
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 6, 12, 6)
        header_layout.setSpacing(12)
        header_layout.addWidget(self.path_label, 1)
        header_layout.addWidget(self.size_label)
        header_layout.addWidget(self.time_label)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(4)
        splitter.setStyleSheet(splitter_stylesheet())
        _res = splitter.addWidget(self._original)
        _res = splitter.addWidget(self._processed)
        splitter.setChildrenCollapsible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header)
        layout.addWidget(splitter, 1)
        self.setMinimumWidth(320)

        _res = self._original.zoom_requested.connect(self._on_zoom_requested)
        _res = self._processed.zoom_requested.connect(self._on_zoom_requested)

    # ------------------------------------------------------------------ images
    def show_original(self, path: str, size: int = 0, mtime: float = 0.0) -> None:
        """Show `path` on top and its name, size and timestamp in the header."""
        self.path_label.setText(path)
        self.path_label.setToolTip(path)
        self.size_label.setText(sizeof_fmt(size) if size else "")
        self.time_label.setText(
            time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime)) if mtime else ""
        )
        self._load(self._original, path, _("Loading…"))

    def show_processed(self, path: str | None) -> None:
        if path is None:
            self.clear_processed()
            return
        self._load(self._processed, path, _("Loading…"))

    def clear_processed(self, placeholder: str | None = None) -> None:
        self._tokens[self._processed] = -1
        self._processed.set_placeholder(placeholder or _("The processed image appears here."))

    def clear(self) -> None:
        self._tokens[self._original] = -1
        self.path_label.setText("")
        self.size_label.setText("")
        self.time_label.setText("")
        self._original.set_placeholder(_("Select a file to preview it."))
        self.clear_processed()

    def _load(self, pane: ImagePane, path: str, placeholder: str) -> None:
        self._request += 1
        token = self._request
        self._tokens[pane] = token
        self._pending[token] = pane
        pane.set_placeholder(placeholder)
        task = _PreviewTask(token, path)
        _res = task.loaded.connect(self._on_loaded)
        start_task(task)

    def _on_loaded(self, token: int, image: object) -> None:
        pane = self._pending.pop(token, None)
        if pane is None or self._tokens.get(pane) != token:
            # A newer selection won; a late decode must not replace it.
            return
        if isinstance(image, QImage):
            pane.set_image(image)
        else:
            pane.set_placeholder(_("Preview unavailable."))

    def _on_zoom_requested(self, steps: float) -> None:
        factor: float = math.pow(_ZOOM_STEP, float(steps))
        for pane in (self._original, self._processed):
            pane.scale_zoom(factor)

    def zoom_in(self) -> None:
        for pane in (self._original, self._processed):
            pane.zoom_in()

    def zoom_out(self) -> None:
        for pane in (self._original, self._processed):
            pane.zoom_out()

    def fit(self) -> None:
        for pane in (self._original, self._processed):
            pane.fit()
