import os
from collections.abc import Callable
from typing import override

from PySide6.QtCore import QObject, QRunnable, QSize, Qt, QThreadPool, QUrl, Signal
from PySide6.QtGui import (
    QAction,
    QContextMenuEvent,
    QDesktopServices,
    QIcon,
    QImage,
    QMouseEvent,
    QPixmap,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QProgressBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ._i18n import _
from .result_item import ResultItem
from .tools import create_thumbnail_qimage
from .widgets import circle_off_icon, shield_alert_icon

# Shared, bounded pool: a batch of hundreds of rows must not spawn a thread per
# row. The cap follows compression_manager's reasoning (decode is cheap but
# saturating every core is wasteful); it is never zero even on a single-core box.
_THUMBNAIL_POOL = QThreadPool()
_THUMBNAIL_POOL.setMaxThreadCount(max(2, (os.cpu_count() or 2) // 2))


# Both __init__s are called explicitly below; the multiple-inheritance
# warning is a false positive for the standard QObject+QRunnable combo.
class _ThumbnailTask(QObject, QRunnable):  # pyright: ignore[reportUnsafeMultipleInheritance]
    """Decode a thumbnail image in a pooled worker thread; emits a value QImage."""

    loaded: Signal = Signal(object)

    def __init__(self, filename: str, size: int) -> None:
        QObject.__init__(self)
        QRunnable.__init__(self)
        # Managed by the row/pool (tryTake + deleteLater), not auto-deleted.
        self.setAutoDelete(False)
        self._filename: str = filename
        self._size: int = size

    @override
    def run(self) -> None:
        self.loaded.emit(create_thumbnail_qimage(self._filename, self._size, self._size))
        # deleteLater() posts to the main thread (the object's affinity), so it
        # runs after any queued 'loaded' delivery and never while run() winds down.
        self.deleteLater()


class _ClickableThumbnail(QLabel):
    """Thumbnail label that emits a click signal."""

    clicked: Signal = Signal()

    @override
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class ResultItemRow(QWidget):
    def __init__(self, result_item: ResultItem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.result_item: ResultItem = result_item

        self.thumbnail: _ClickableThumbnail = _ClickableThumbnail()
        self.thumbnail.setCursor(Qt.CursorShape.PointingHandCursor)
        _res = self.thumbnail.clicked.connect(self._open_compressed)
        self.title_label: QLabel = QLabel(result_item.filename)
        title_font = self.title_label.font()
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setWordWrap(True)
        self.subtitle_label: QLabel = QLabel()
        self.subtitle_label.setObjectName("rowSubtitle")
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.savings_label: QLabel = QLabel()
        self.savings_label.setObjectName("rowSavings")

        self.spinner: QProgressBar = QProgressBar()
        self.spinner.setRange(0, 0)
        self.spinner.setFixedSize(20, 16)
        self.spinner.setTextVisible(False)

        self.skipped_button: QToolButton = self._make_info_button(
            self._show_skipped_info,
            circle_off_icon(self.palette().color(self.palette().ColorRole.WindowText), 16),
        )
        self.error_button: QToolButton = self._make_info_button(
            self._show_error_info,
            shield_alert_icon(self.palette().color(self.palette().ColorRole.WindowText), 16),
        )

        text_vbox = QVBoxLayout()
        text_vbox.setSpacing(0)
        text_vbox.addWidget(self.title_label)
        text_vbox.addWidget(self.subtitle_label)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        layout.addWidget(self.thumbnail)
        layout.addLayout(text_vbox, 1)
        layout.addWidget(self.savings_label)
        layout.addWidget(self.spinner)
        layout.addWidget(self.skipped_button)
        layout.addWidget(self.error_button)

        self._thumbnail_task: _ThumbnailTask | None = _ThumbnailTask(result_item.filename, 48)
        _res = self._thumbnail_task.loaded.connect(self._set_thumbnail)
        _THUMBNAIL_POOL.start(self._thumbnail_task)

        _res = result_item.updated.connect(self.refresh)
        self.refresh()

    def _set_thumbnail(self, image: QImage | None) -> None:
        self._thumbnail_task = None
        if image is None:
            return
        self.thumbnail.setPixmap(QPixmap.fromImage(image))

    def stop_thumbnail_loader(self) -> None:
        task = self._thumbnail_task
        self._thumbnail_task = None
        if task is not None and _THUMBNAIL_POOL.tryTake(task):
            # Task was still queued; skip the decode entirely.
            task.deleteLater()

    @staticmethod
    def _make_info_button(handler: Callable[..., None], icon: QIcon | None = None) -> QToolButton:
        button = QToolButton()
        if icon is None:
            button.setText("i")
        else:
            button.setIcon(icon)
            button.setIconSize(QSize(16, 16))
        button.setToolTip(_("More Information"))
        button.setVisible(False)
        _res = button.clicked.connect(handler)
        return button

    def refresh(self) -> None:
        item = self.result_item
        self.spinner.setVisible(item.running)

        self.subtitle_label.setText(item.subtitle_label)
        self.savings_label.setText(item.savings)
        self.savings_label.setVisible(not item.running)

        self.skipped_button.setVisible(item.skipped and not item.running)
        self.error_button.setVisible(item.error and item.error_details)

    def _show_skipped_info(self) -> None:
        _res = QMessageBox.information(
            self,
            _("Skipped"),
            _(
                "Compression was skipped because compressing the file would have "
                + "resulted in a larger file size."
            ),
        )

    def _show_error_info(self) -> None:
        _res = QMessageBox.warning(
            self,
            _("Error"),
            self.result_item.error_details_message,
        )

    @override
    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        if not self._compressed_exists():
            event.ignore()
            return

        menu = QMenu(self)
        open_image = QAction(_("Open Image"), menu)
        _res = open_image.triggered.connect(self._open_compressed)
        show_in_folder = QAction(_("Show in Folder"), menu)
        _res = show_in_folder.triggered.connect(self._show_in_folder)
        menu.addAction(open_image)
        menu.addAction(show_in_folder)
        _res = menu.exec(event.globalPos())

    def _compressed_exists(self) -> bool:
        return bool(self.result_item.new_filename) and os.path.exists(self.result_item.new_filename)

    def _open_compressed(self) -> None:
        if not self._compressed_exists():
            return
        _res = QDesktopServices.openUrl(QUrl.fromLocalFile(self.result_item.new_filename))

    def _show_in_folder(self) -> None:
        if not self._compressed_exists():
            return
        folder = os.path.dirname(self.result_item.new_filename)
        _res = QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
