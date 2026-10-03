import os
from collections.abc import Callable
from typing import override

from PySide6.QtCore import QObject, QRunnable, QSize, Qt, QThreadPool, QUrl, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
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
from .image_utils import create_thumbnail_qimage
from .result_item import ResultItem, ResultState
from .widgets import circle_off_icon, shield_alert_icon, triangle_alert_icon

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
    finished: Signal = Signal()

    def __init__(self, filename: str, size: int) -> None:
        QObject.__init__(self)
        QRunnable.__init__(self)
        # Managed by the in-flight registry (tryTake + deleteLater), not the pool.
        self.setAutoDelete(False)
        self._filename: str = filename
        self._size: int = size
        # Queued onto the main thread, so it runs after any queued 'loaded'
        # delivery and never while run() winds down.
        _res = self.finished.connect(self._release)

    @override
    def run(self) -> None:
        try:
            self.loaded.emit(create_thumbnail_qimage(self._filename, self._size, self._size))
        finally:
            self.finished.emit()

    def _release(self) -> None:
        _ACTIVE_TASKS.discard(self)
        self.deleteLater()


# Holds every started task until it finishes, so a running QRunnable is never
# garbage-collected (and its C++ object destroyed) mid-run() when its row is
# removed; _release drops it on the main thread after run() returns.
_ACTIVE_TASKS: set[_ThumbnailTask] = set()

# Every row paints the same three 16px info icons; rendering them per row is
# pure waste, so memoize by window-text color (rgba) for the current theme.
_INFO_ICONS: dict[int, tuple[QIcon, QIcon, QIcon]] = {}


def _info_icons(color: QColor) -> tuple[QIcon, QIcon, QIcon]:
    key = color.rgba()
    icons = _INFO_ICONS.get(key)
    if icons is None:
        icons = (
            circle_off_icon(color, 16),
            shield_alert_icon(color, 16),
            triangle_alert_icon(color, 16),
        )
        _INFO_ICONS[key] = icons
    return icons


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

        skipped_icon, error_icon, warning_icon = _info_icons(
            self.palette().color(self.palette().ColorRole.WindowText)
        )
        self.skipped_button: QToolButton = self._make_info_button(
            self._show_skipped_info, skipped_icon
        )
        self.error_button: QToolButton = self._make_info_button(self._show_error_info, error_icon)
        self.warning_button: QToolButton = self._make_info_button(
            self._show_warning_info, warning_icon
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
        layout.addWidget(self.warning_button)
        layout.addWidget(self.error_button)

        task = _ThumbnailTask(result_item.filename, 48)
        self._thumbnail_task: _ThumbnailTask | None = task
        _ACTIVE_TASKS.add(task)
        _res = task.loaded.connect(self._set_thumbnail)
        _THUMBNAIL_POOL.start(task)

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
        if task is None or not _THUMBNAIL_POOL.tryTake(task):
            # Already running: the registry keeps it alive and _release cleans
            # it up once run() returns; never drop it mid-run.
            return
        # Still queued; skip the decode entirely.
        _ACTIVE_TASKS.discard(task)
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
        running = item.state is ResultState.RUNNING
        self.spinner.setVisible(running)

        self.subtitle_label.setText(item.subtitle_label)
        self.savings_label.setText(item.savings)
        self.savings_label.setVisible(not running)

        self.skipped_button.setVisible(item.state is ResultState.SKIPPED)
        self.error_button.setVisible(
            item.state is ResultState.ERROR and bool(item.error_details_message)
        )
        self.warning_button.setVisible(bool(item.warning_message) and not running)

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
        # Raw tool output can contain characters AutoText would treat as markup,
        # so force plain text instead of HTML-escaping the stored details.
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(_("Error"))
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setText(self.result_item.error_details_message)
        _res = box.exec()

    def _show_warning_info(self) -> None:
        _res = QMessageBox.warning(
            self,
            _("Warning"),
            self.result_item.warning_message,
        )

    @override
    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        # Accept even without a compressed file so the window's paste menu does
        # not appear when right-clicking a row.
        event.accept()
        if not self._compressed_exists():
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
