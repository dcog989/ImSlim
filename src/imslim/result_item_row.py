import os
from collections.abc import Callable
from typing import override

from PySide6.QtCore import Qt, QThread, QUrl, Signal
from PySide6.QtGui import QAction, QContextMenuEvent, QDesktopServices, QImage, QPixmap
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


class _ThumbnailLoader(QThread):
    """Decode a thumbnail image off the UI thread; emits a value QImage."""

    loaded: Signal = Signal(object)

    def __init__(self, filename: str, size: int, parent: QWidget | None = None):
        super().__init__(parent)
        self._filename: str = filename
        self._size: int = size

    @override
    def run(self) -> None:
        self.loaded.emit(create_thumbnail_qimage(self._filename, self._size, self._size))


class ResultItemRow(QWidget):
    def __init__(self, result_item: ResultItem, parent: QWidget | None = None):
        super().__init__(parent)
        self.result_item: ResultItem = result_item

        self.thumbnail: QLabel = QLabel()
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

        self.skipped_button: QToolButton = self._make_info_button(self._show_skipped_info)
        self.error_button: QToolButton = self._make_info_button(self._show_error_info)

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

        self._thumbnail_loader: _ThumbnailLoader | None = _ThumbnailLoader(
            result_item.filename, 48, self
        )
        _res = self._thumbnail_loader.loaded.connect(self._set_thumbnail)
        self._thumbnail_loader.start()

        _res = result_item.updated.connect(self.refresh)
        self.refresh()

    def _set_thumbnail(self, image: QImage | None) -> None:
        if self._thumbnail_loader is not None:
            self._thumbnail_loader.deleteLater()
        self._thumbnail_loader = None
        if image is None:
            return
        self.thumbnail.setPixmap(QPixmap.fromImage(image))

    @staticmethod
    def _make_info_button(handler: Callable[..., None]) -> QToolButton:
        button = QToolButton()
        button.setText("i")
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

    def _show_skipped_info(self):
        _res = QMessageBox.information(
            self,
            _("Skipped"),
            _(
                "Compression was skipped because compressing the file would have "
                + "resulted in a larger file size."
            ),
        )

    def _show_error_info(self):
        _res = QMessageBox.warning(
            self,
            _("Error"),
            self.result_item.error_details_message,
        )

    @override
    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        filename = self.result_item.new_filename
        if not filename or not os.path.exists(filename):
            event.ignore()
            return

        menu = QMenu(self)
        open_image = QAction(_("Open Image"), menu)
        _res = open_image.triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(filename))
        )
        show_in_folder = QAction(_("Show in Folder"), menu)
        _res = show_in_folder.triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(filename)))
        )
        menu.addAction(open_image)
        menu.addAction(show_in_folder)
        _res = menu.exec(event.globalPos())
