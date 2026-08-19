import os

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QAction, QDesktopServices
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

from .result_item import ResultItem
from .tools import create_thumbnail


class ResultItemRow(QWidget):
    def __init__(self, result_item: ResultItem, parent=None):
        super().__init__(parent)
        self.result_item = result_item

        self.thumbnail = QLabel()
        self.title_label = QLabel(result_item.filename)
        title_font = self.title_label.font()
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setWordWrap(True)
        self.subtitle_label = QLabel()
        self.subtitle_label.setObjectName("rowSubtitle")
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.savings_label = QLabel()
        self.savings_label.setObjectName("rowSavings")

        self.spinner = QProgressBar()
        self.spinner.setRange(0, 0)
        self.spinner.setFixedSize(20, 16)
        self.spinner.setTextVisible(False)

        self.skipped_button = QToolButton()
        self.skipped_button.setText("i")
        self.skipped_button.setToolTip(_("More Information"))
        self.skipped_button.setVisible(False)
        self.skipped_button.clicked.connect(self._show_skipped_info)

        self.error_button = QToolButton()
        self.error_button.setText("i")
        self.error_button.setToolTip(_("More Information"))
        self.error_button.setVisible(False)
        self.error_button.clicked.connect(self._show_error_info)

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

        thumbnail = create_thumbnail(result_item.filename, 48, 48)
        if thumbnail:
            self.thumbnail.setPixmap(thumbnail)

        result_item.updated.connect(self.refresh)
        self.refresh()

    def refresh(self):
        item = self.result_item
        self.spinner.setVisible(item.running)

        self.subtitle_label.setText(item.subtitle_label)
        self.savings_label.setText(item.savings)
        self.savings_label.setVisible(not item.running)

        self.skipped_button.setVisible(item.skipped and not item.running)
        self.error_button.setVisible(item.error and item.error_details)

    def _show_skipped_info(self):
        QMessageBox.information(
            self,
            _("Skipped"),
            _(
                "Compression was skipped because compressing the file would have "
                "resulted in a larger file size."
            ),
        )

    def _show_error_info(self):
        QMessageBox.warning(
            self,
            _("Error"),
            self.result_item.error_details_message,
        )

    def contextMenuEvent(self, event):
        filename = self.result_item.new_filename
        if not filename or not os.path.exists(filename):
            event.ignore()
            return

        menu = QMenu(self)
        open_image = QAction(_("Open Image"), menu)
        open_image.triggered.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(filename)))
        show_in_folder = QAction(_("Show in Folder"), menu)
        show_in_folder.triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(filename)))
        )
        menu.addAction(open_image)
        menu.addAction(show_in_folder)
        menu.exec(event.globalPos())
