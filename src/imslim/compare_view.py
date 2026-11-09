"""Column 3: the original and the processed image, side by side (stacked)."""

import logging
import math
import os
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
    QShowEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSplitter, QVBoxLayout, QWidget

from ._i18n import _
from .format import sizeof_fmt
from .preview import load_preview
from .theme import apply_muted_palette, muted_color, splitter_stylesheet
from .widgets import ElidedLabel, plain_tooltip
from .workers import Task, start_task

_MIN_ZOOM = 1.0
_MAX_ZOOM = 8.0
_ZOOM_STEP = 1.25
# Padding so a fitted image does not touch the pane frame.
_PANE_MARGIN = 8
# The decoded image is already capped in preview.py; this bounds the *display*
# zoom to roughly 2x the viewport area, as the design asks.
_VIEWPORT_AREA_BUDGET = 2.0

logger = logging.getLogger(__name__)


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
            try:
                image: QImage | None = load_preview(self._path)
            except Exception:
                # Never leave the pane on "Loading…": report a failed decode
                # the same way load_preview() reports an unreadable file.
                logger.exception("Preview decode failed unexpectedly for %s", self._path)
                image = None
            self.loaded.emit(self._token, image)
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

    def image(self) -> QImage | None:
        return self._image

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
            return
        scale = self._fit_scale() * self._zoom
        width = image.width() * scale
        height = image.height() * scale
        # Pan is stored in image pixels so both panes show the same region.
        target = QRectF(
            (self.width() - width) / 2 + self._pan.x() * scale,
            (self.height() - height) / 2 + self._pan.y() * scale,
            width,
            height,
        )
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawImage(target, image)

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
        half_width = max(0.0, (image.width() - self.width() / scale) / 2)
        half_height = max(0.0, (image.height() - self.height() / scale) / 2)
        self._pan = QPointF(
            max(-half_width, min(half_width, self._pan.x())),
            max(-half_height, min(half_height, self._pan.y())),
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
            # Widget pixels to image pixels: both panes must move the same region.
            self._pan += delta / (self._fit_scale() * self._zoom)
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


def _file_version(path: str) -> tuple[str, int, int]:
    """Identity of the file behind a path, so a rewritten file is decoded again."""
    try:
        stat = os.stat(path)
    except OSError:
        return (path, -1, -1)
    return (path, stat.st_mtime_ns, stat.st_size)


def _savings_text(size: int, savings: int) -> str:
    if not size:
        return ""
    if savings < 0:
        return _("{percent}% larger").format(percent=-savings)
    if savings == 0:
        return _("No change")
    return _("{percent}% saved").format(percent=savings)


class CompareView(QWidget):
    """Vertical comparison of the source and the processed output."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._request: int = 0
        self._tokens: dict[ImagePane, int] = {}
        self._pending: dict[int, ImagePane] = {}
        # One decode per pane at a time; the newest request replaces any queued.
        self._decoding: set[ImagePane] = set()
        self._queued: dict[ImagePane, tuple[int, str, str]] = {}
        self._split_done: bool = False
        # The source currently shown; repeated item updates must not decode it
        # again (that also resets the zoom and pan the user set).
        self._shown_original: str = ""
        self._original_version: tuple[str, int, int] | None = None
        self._shown_processed: str = ""
        self._processed_version: tuple[str, int, int] | None = None
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
        self._processed_header: QWidget = processed_header
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
            _res = pane.pan_changed.connect(other.set_pan)
        _res = self._original.zoom_changed.connect(self._on_zoom_changed)
        self._on_zoom_changed(self._original.zoom)

    # ------------------------------------------------------------------ images
    @override
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.MouseButtonDblClick:
            self._split_evenly()
            return True
        return super().eventFilter(watched, event)

    @override
    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if not self._split_done:
            self._split_evenly()

    def _split_evenly(self) -> None:
        """Give both images half the height; the after header sits on top."""
        header = self._processed_header.height() or self._processed_header.sizeHint().height()
        total = self._splitter.height() - self._splitter.handleWidth()
        half = (total - header) // 2
        if half <= 0:
            return
        self._splitter.setSizes([half, half + header])
        # The user's own split must survive later shows; a double-click resets it.
        self._split_done = True

    def refresh_theme(self) -> None:
        """Re-apply the splitter colors and muted header labels after a palette change."""
        self._splitter.setStyleSheet(splitter_stylesheet())
        for label in (
            self.zoom_label,
            self.size_label,
            self.time_label,
            self.processed_size,
            self.processed_savings,
        ):
            apply_muted_palette(label)

    def show_original(self, path: str, size: int = 0, mtime: float = 0.0) -> None:
        """Show `path` on top and its name, size and timestamp in the header."""
        self.path_label.setText(path)
        self.path_label.setToolTip(plain_tooltip(path))
        self.size_label.setText(sizeof_fmt(size) if size else "")
        self.time_label.setText(
            time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime)) if mtime > 0 else ""
        )
        if path != self._shown_original:
            self._shown_original = path
            self._original_version = _file_version(path)
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
        self.processed_path.setToolTip(plain_tooltip(shown))
        self.processed_size.setText(sizeof_fmt(size) if size else "")
        self.processed_savings.setText(_savings_text(size, savings))
        version = _file_version(path)
        if path == self._shown_processed and version == self._processed_version:
            return
        self._shown_processed = path
        self._processed_version = version
        if (
            path == self._shown_original
            and self._original.has_image()
            and version == self._original_version
        ):
            # Mid-batch the source is shown here; reuse the top pane's decode.
            self._tokens[self._processed] = -1
            _res = self._queued.pop(self._processed, None)
            self._processed.set_image(self._original.image())
            return
        self._load(self._processed, path, _("Loading…"))

    def clear_processed(self, placeholder: str | None = None) -> None:
        self._tokens[self._processed] = -1
        _res = self._queued.pop(self._processed, None)
        self._shown_processed = ""
        self._processed_version = None
        self.processed_path.setText("")
        self.processed_size.setText("")
        self.processed_savings.setText("")
        self._processed.set_placeholder(placeholder or _("The processed image appears here."))

    def clear(self) -> None:
        self._tokens[self._original] = -1
        _res = self._queued.pop(self._original, None)
        self._shown_original = ""
        self._original_version = None
        self.path_label.setText("")
        self.size_label.setText("")
        self.time_label.setText("")
        self._original.set_placeholder(_("Select a file to preview it."))
        self.clear_processed()

    def _load(self, pane: ImagePane, path: str, placeholder: str) -> None:
        # One decode per pane at a time: a fast click-through must not queue a
        # full decode per file with the newest one last.
        self._request += 1
        token = self._request
        self._tokens[pane] = token
        if pane in self._decoding:
            self._queued[pane] = (token, path, placeholder)
            return
        self._start_load(pane, token, path, placeholder)

    def _start_load(self, pane: ImagePane, token: int, path: str, placeholder: str) -> None:
        self._decoding.add(pane)
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
        if pane is None:
            return
        self._decoding.discard(pane)
        queued = self._queued.pop(pane, None)
        if queued is not None:
            # Decode only the newest request that arrived while this one ran.
            if self._tokens.get(pane) == queued[0]:
                self._start_load(pane, *queued)
            return
        if self._tokens.get(pane) != token:
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
