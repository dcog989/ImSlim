"""File properties dialog for a queued image."""

import logging
import os
import time
from typing import override

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QGuiApplication, QImageReader
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ._i18n import _
from .exif import read_exif, read_exif_and_size
from .format import sizeof_fmt
from .result_item import ResultItem
from .theme import apply_muted_palette
from .workers import Task, start_task

logger = logging.getLogger(__name__)


def _base_details(item: ResultItem) -> list[tuple[str, str]]:
    """Rows that need no decoding."""
    rows: list[tuple[str, str]] = [
        (_("Name"), os.path.basename(item.filename)),
        (_("Folder"), os.path.dirname(item.filename)),
        (_("Type"), f"{item.mime_type or _('Unknown')} · {os.path.splitext(item.filename)[1]}"),
    ]
    if not os.path.exists(item.filename):
        rows.append((_("Status"), _("File is missing")))
        return rows
    rows.append(
        (
            _("Size"),
            _("{count} bytes ({formatted})").format(
                count=item.size, formatted=sizeof_fmt(item.size)
            ),
        )
    )
    if item.mtime > 0:
        rows.append((_("Modified"), time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(item.mtime))))
    return rows


def image_details(item: ResultItem) -> list[tuple[str, str]]:
    """Collect the rows shown for one file; the slow decodes happen off the UI thread."""
    rows = _base_details(item)
    if not os.path.exists(item.filename):
        return rows

    reader = QImageReader(item.filename)
    size = reader.size()
    if size.isValid():
        rows.append((_("Dimensions"), f"{size.width()} × {size.height()} px"))
        frames = reader.imageCount()
        if frames > 1:
            rows.append((_("Frames"), str(frames)))
        exif_rows = read_exif(item.filename, item.mime_type)
    else:
        # Formats such as AVIF and JXL are decoded by the bundled tools, not Qt.
        decoded_size, exif_rows = read_exif_and_size(item.filename, item.mime_type)
        if decoded_size is None:
            rows.append((_("Dimensions"), _("Not readable")))
        else:
            rows.append((_("Dimensions"), f"{decoded_size[0]} × {decoded_size[1]} px"))
    rows.extend(exif_rows)
    return rows


class PropertiesTask(Task):
    """Builds the metadata rows off the UI thread; decoding a large file is slow."""

    details_ready: Signal = Signal(list)

    def __init__(self, item: ResultItem) -> None:
        super().__init__()
        self._item: ResultItem = item

    @override
    def run(self) -> None:
        try:
            self.details_ready.emit(image_details(self._item))
        except Exception as err:
            logger.exception("Could not read properties for %s", self._item.filename)
            self.details_ready.emit([(_("Error"), str(err))])
        finally:
            self.finished.emit()


class PropertiesDialog(QDialog):
    """Detailed information about one queued image, plus Copy Path."""

    def __init__(self, item: ResultItem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._path: str = item.filename
        self._muted_labels: list[QLabel] = []
        self.setWindowTitle(_("Properties — {name}").format(name=os.path.basename(item.filename)))
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self._grid: QGridLayout = QGridLayout()
        self._grid.setHorizontalSpacing(24)
        self._grid.setVerticalSpacing(6)
        self._grid.setColumnStretch(1, 1)
        layout.addLayout(self._grid)
        layout.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(_("Close"))
        copy = QPushButton(_("Copy Path"))
        _res = copy.clicked.connect(self._copy_path)
        buttons.addButton(copy, QDialogButtonBox.ButtonRole.ActionRole)
        _res = buttons.rejected.connect(self.close)
        layout.addWidget(buttons)

        self._render([*_base_details(item), (_("Metadata"), _("Reading…"))])
        self._task: PropertiesTask = PropertiesTask(item)
        _res = self._task.details_ready.connect(self._render)
        start_task(self._task)

    def _render(self, rows: list[tuple[str, str]]) -> None:
        while self._grid.count():
            entry = self._grid.takeAt(0)
            if entry is None:
                break
            widget = entry.widget()
            if widget is not None:
                widget.deleteLater()
        self._muted_labels.clear()
        for row, (label, value) in enumerate(rows):
            key = QLabel(label)
            apply_muted_palette(key)
            self._muted_labels.append(key)
            key.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            value_label = QLabel(value)
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self._grid.addWidget(key, row, 0)
            self._grid.addWidget(value_label, row, 1)

    @override
    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.PaletteChange:
            for label in self._muted_labels:
                apply_muted_palette(label)
        super().changeEvent(event)

    def _copy_path(self) -> None:
        QGuiApplication.clipboard().setText(self._path)
