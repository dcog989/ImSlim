"""Results list: chunked rows, per-item updates and the busy overlay."""

from typing import override

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ._i18n import _
from .result_item import ResultItem
from .result_item_row import ResultItemRow
from .spinner import Spinner
from .theme import apply_muted_palette, muted_color

# Rows are built in small timer-driven chunks so a huge batch does not block the
# UI thread building thousands of widgets in one event-loop iteration.
_ROW_CHUNK_SIZE = 50


def _make_stop_button() -> QToolButton:
    button = QToolButton()
    button.setText(_("Stop"))
    button.setToolTip(_("Stop the current compression."))
    button.setFixedHeight(32)
    button.setStyleSheet("QToolButton { padding: 0 12px; }")
    return button


class ResultsPage(QWidget):
    """Results list covered by a spinner overlay while compressing."""

    def __init__(self, stop_button: QToolButton, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.overlay: QWidget = QWidget(self)
        self.overlay.setObjectName("processingOverlay")
        self.overlay.setStyleSheet(
            "QWidget#processingOverlay { background-color: rgba(128, 128, 128, 150); }"
        )
        layout = QVBoxLayout(self.overlay)
        layout.addStretch(1)
        self.spinner: Spinner = Spinner(120)
        layout.addWidget(self.spinner, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(stop_button, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(1)
        self.overlay.hide()

    def show_overlay(self) -> None:
        self.overlay.setGeometry(self.rect())
        self.overlay.raise_()
        self.overlay.show()
        self.spinner.start()

    def hide_overlay(self) -> None:
        self.overlay.hide()
        self.spinner.stop()

    @override
    def resizeEvent(self, event: QResizeEvent) -> None:
        if self.overlay.isVisible():
            self.overlay.setGeometry(self.rect())
        super().resizeEvent(event)


class ResultsView(ResultsPage):
    stop_requested: Signal = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        stop_button = _make_stop_button()
        super().__init__(stop_button, parent)
        self.stop_button: QToolButton = stop_button
        _res = stop_button.clicked.connect(self.stop_requested.emit)

        self.results_container: QWidget = QWidget()
        self.results_layout: QVBoxLayout = QVBoxLayout(self.results_container)
        self.results_layout.setContentsMargins(12, 12, 12, 12)
        self.results_layout.setSpacing(2)
        self.results_layout.addWidget(self._build_results_header())

        self.rows_container: QWidget = QWidget()
        self.rows_layout: QVBoxLayout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(2)
        self.results_layout.addWidget(self.rows_container)
        self.results_layout.addStretch(1)

        self.summary_label: QLabel = self._build_summary_label()
        self.results_layout.addWidget(self.summary_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.results_container)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll)

        self._row_count: int = 0
        self._pending_rows: list[ResultItem] = []
        self._rows: dict[ResultItem, ResultItemRow] = {}
        self._row_timer: QTimer = QTimer(self)
        self._row_timer.setSingleShot(True)
        self._row_timer.setInterval(0)
        _res = self._row_timer.timeout.connect(self._flush_rows)
        self._overlay_timer: QTimer = QTimer(self)
        self._overlay_timer.setSingleShot(True)
        self._overlay_timer.setInterval(1000)
        _res = self._overlay_timer.timeout.connect(self.show_overlay)

    def _build_results_header(self) -> QWidget:
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(8)

        image_label = QLabel(_("Image:"))
        self.reduced_label = QLabel()
        header_font = image_label.font()
        header_font.setBold(True)
        image_label.setFont(header_font)
        self.reduced_label.setFont(header_font)

        layout.addWidget(image_label)
        layout.addStretch(1)
        layout.addWidget(self.reduced_label)
        return header

    def _build_summary_label(self) -> QLabel:
        label = QLabel()
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setContentsMargins(0, 8, 0, 0)
        apply_muted_palette(label)
        return label

    def add_item(self, result_item: ResultItem) -> None:
        self._pending_rows.append(result_item)
        if not self._row_timer.isActive():
            self._row_timer.start()

    def _flush_rows(self) -> None:
        """Build the next chunk of queued rows with repaints suppressed.

        Compressing thousands of files emits one item_added per file in a
        single event-loop iteration; building the widgets here in capped chunks
        keeps that iteration short so the window stays responsive.
        """
        if not self._pending_rows:
            return
        batch = self._pending_rows[:_ROW_CHUNK_SIZE]
        del self._pending_rows[:_ROW_CHUNK_SIZE]
        self.results_container.setUpdatesEnabled(False)
        try:
            for result_item in batch:
                row = ResultItemRow(result_item)
                self._apply_row_alternation(row, self._row_count)
                self.rows_layout.addWidget(row)
                self._rows[result_item] = row
                self._row_count += 1
        finally:
            self.results_container.setUpdatesEnabled(True)
        if self._pending_rows:
            self._row_timer.start()

    @staticmethod
    def _apply_row_alternation(row: ResultItemRow, index: int) -> None:
        if index % 2 == 0:
            return
        palette = row.palette()
        base = palette.color(palette.ColorRole.Base)
        window = palette.color(palette.ColorRole.Window)
        palette.setColor(palette.ColorRole.Window, muted_color(base, window, 0.6))
        row.setPalette(palette)
        row.setAutoFillBackground(True)

    def update_item(self, result_item: ResultItem) -> None:
        self._refresh_row(result_item)

    def _refresh_row(self, result_item: ResultItem) -> None:
        row = self._rows.get(result_item)
        if row is not None:
            row.refresh()

    def set_converting(self, converting: bool) -> None:
        self.reduced_label.setText(_("Size change:") if converting else _("Reduced by:"))

    def set_summary(self, text: str) -> None:
        self.summary_label.setText(text)

    def set_busy(self, busy: bool) -> None:
        if busy:
            self._overlay_timer.start()
        else:
            self._overlay_timer.stop()
            self.hide_overlay()
            self.stop_button.setEnabled(True)

    def set_stop_enabled(self, enabled: bool) -> None:
        self.stop_button.setEnabled(enabled)

    def clear(self) -> None:
        self._pending_rows.clear()
        self._row_timer.stop()
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                if isinstance(widget, ResultItemRow):
                    widget.stop_thumbnail_loader()
                widget.deleteLater()
        self._row_count = 0
        self._rows.clear()
