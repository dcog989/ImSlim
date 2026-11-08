"""Column 3: the original and the processed image, side by side (stacked)."""

import math
import time
from typing import override

from PySide6.QtCore import QEvent, QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QImage,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPalette,
    QResizeEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSplitter, QVBoxLayout, QWidget

from ._i18n import _
from .format import sizeof_fmt
from .preview import load_preview
from .theme import apply_muted_palette, muted_color, splitter_stylesheet
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
    zoom_changed: Signal = Signal(float)
    pan_changed: Signal = Signal(QPointF)

    def __init__(self, placeholder: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._image: QImage | None = None
        self._placeholder: str = placeholder
        self._zoom: float = _MIN_ZOOM
        self._pan: QPointF = QPointF()
        self._last_pos: QPointF = QPointF()
        self.setMinimumHeight(120)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

    def set_image(self, image: QImage | None, placeholder: str | None = None) -> None:
        previous = self._zoom
        self._image = image
        if placeholder is not None:
            self._placeholder = placeholder
        self._zoom = _MIN_ZOOM
        self._pan = QPointF()
        self.update()
        if previous != self._zoom:
            self.zoom_changed.emit(self._zoom)
        self.pan_changed.emit(self._pan)

    def set_placeholder(self, text: str) -> None:
        self.set_image(None, text)

    def has_image(self) -> bool:
        return self._image is not None

    # ------------------------------------------------------------------ zoom
    @property
    def zoom(self) -> float:
        return self._zoom

    def set_zoom(self, zoom: float) -> None:
        self._apply_zoom(zoom)

    def max_zoom(self) -> float:
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

    def _apply_zoom(self, zoom: float) -> None:
        if self._image is None:
            return
        previous = self._zoom
        self._zoom = max(_MIN_ZOOM, min(self.max_zoom(), zoom))
        self._clamp_pan()
        self.update()
        if self._zoom != previous:
            self.zoom_changed.emit(self._zoom)

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
            palette = self.palette()
            # Derived per paint, not stored on the widget: mutating the palette
            # here compounds on every repaint until the text fades into the
            # background.
            muted = muted_color(
                palette.color(QPalette.ColorRole.Text),
                palette.color(QPalette.ColorRole.Base),
            )
            painter.setPen(muted)
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

    def set_pan(self, pan: QPointF) -> None:
        self._pan = QPointF(pan)
        self._clamp_pan()
        self.update()

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
            self.pan_changed.emit(self._pan)
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
        self.pan_changed.emit(self._pan)
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
        self.zoom_label: QLabel = QLabel()
        self.size_label: QLabel = QLabel()
        self.time_label: QLabel = QLabel()
        for label in (self.zoom_label, self.size_label, self.time_label):
            apply_muted_palette(label)
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 6, 12, 6)
        header_layout.setSpacing(12)
        header_layout.addWidget(self.path_label, 1)
        header_layout.addWidget(self.zoom_label)
        header_layout.addWidget(self.size_label)
        header_layout.addWidget(self.time_label)

        self.processed_path: ElidedLabel = ElidedLabel()
        self.processed_size: QLabel = QLabel()
        self.processed_savings: QLabel = QLabel()
        for label in (self.processed_size, self.processed_savings):
            apply_muted_palette(label)
        processed_header = QWidget()
        processed_header_layout = QHBoxLayout(processed_header)
        processed_header_layout.setContentsMargins(12, 6, 12, 6)
        processed_header_layout.setSpacing(12)
        processed_header_layout.addWidget(self.processed_path, 1)
        processed_header_layout.addWidget(self.processed_size)
        processed_header_layout.addWidget(self.processed_savings)
        processed_container = QWidget()
        processed_layout = QVBoxLayout(processed_container)
        processed_layout.setContentsMargins(0, 0, 0, 0)
        processed_layout.setSpacing(0)
        processed_layout.addWidget(processed_header)
        processed_layout.addWidget(self._processed, 1)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(4)
        splitter.setStyleSheet(splitter_stylesheet())
        _res = splitter.addWidget(self._original)
        _res = splitter.addWidget(processed_container)
        splitter.setChildrenCollapsible(False)
        _res = splitter.setSizes([1, 1])
        self._splitter: QSplitter = splitter
        _res = splitter.handle(1).installEventFilter(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header)
        layout.addWidget(splitter, 1)
        self.setMinimumWidth(320)

        _res = self._original.zoom_requested.connect(self._on_zoom_requested)
        _res = self._processed.zoom_requested.connect(self._on_zoom_requested)
        # Both panes show the same picture region: zoom and pan stay locked.
        for pane, other in (
            (self._original, self._processed),
            (self._processed, self._original),
        ):
            _res = pane.zoom_changed.connect(other.set_zoom)
            _res = pane.zoom_changed.connect(self._on_zoom_changed)
            _res = pane.pan_changed.connect(other.set_pan)
        self._on_zoom_changed(self._original.zoom)

    # ------------------------------------------------------------------ images
    @override
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.MouseButtonDblClick:
            self._splitter.setSizes([1, 1])
            return True
        return super().eventFilter(watched, event)

    def show_original(self, path: str, size: int = 0, mtime: float = 0.0) -> None:
        """Show `path` on top and its name, size and timestamp in the header."""
        self.path_label.setText(path)
        self.path_label.setToolTip(path)
        self.size_label.setText(sizeof_fmt(size) if size else "")
        self.time_label.setText(
            time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime)) if mtime else ""
        )
        self._load(self._original, path, _("Loading…"))

    def show_processed(
        self,
        path: str | None,
        size: int = 0,
        savings: int = 0,
        *,
        destination: str | None = None,
    ) -> None:
        """Show `path` and label it with `destination` when they differ."""
        if path is None:
            self.clear_processed()
            return
        shown = destination or path
        self.processed_path.setText(shown)
        self.processed_path.setToolTip(shown)
        self.processed_size.setText(sizeof_fmt(size) if size else "")
        self.processed_savings.setText(f"{savings}%" if size else "")
        self._load(self._processed, path, _("Loading…"))

    def clear_processed(self, placeholder: str | None = None) -> None:
        self._tokens[self._processed] = -1
        self.processed_path.setText("")
        self.processed_size.setText("")
        self.processed_savings.setText("")
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
        # Keep the pane's current placeholder when it is already empty; swapping
        # text in before the image lands is a second flash.
        if pane.has_image():
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

    def _on_zoom_changed(self, zoom: float) -> None:
        self.zoom_label.setText(f"{round(zoom * 100)}%")

    def _set_zoom(self, zoom: float) -> None:
        """Apply one zoom to both panes so they never drift apart."""
        cap = min(self._original.max_zoom(), self._processed.max_zoom())
        target = max(_MIN_ZOOM, min(cap, zoom))
        self._original.set_zoom(target)
        self._processed.set_zoom(target)

    def _on_zoom_requested(self, steps: float) -> None:
        self._set_zoom(self._original.zoom * math.pow(_ZOOM_STEP, float(steps)))

    def zoom_in(self) -> None:
        self._set_zoom(self._original.zoom * _ZOOM_STEP)

    def zoom_out(self) -> None:
        self._set_zoom(self._original.zoom / _ZOOM_STEP)

    def fit(self) -> None:
        self._set_zoom(_MIN_ZOOM)
