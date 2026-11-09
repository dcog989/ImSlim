"""File properties dialog for a queued image."""

import os
import time
from typing import override

from PySide6.QtCore import QEvent, Qt
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
from .exif import read_exif
from .format import sizeof_fmt
from .result_item import ResultItem
from .theme import apply_muted_palette


def image_details(item: ResultItem) -> list[tuple[str, str]]:
    """Collect the rows shown for one file; cheap, no full decode."""
    rows: list[tuple[str, str]] = [
        (_("Name"), os.path.basename(item.filename)),
        (_("Folder"), os.path.dirname(item.filename)),
        (_("Type"), f"{item.mime_type or _('Unknown')} · {os.path.splitext(item.filename)[1]}"),
        (_("Size"), f"{item.size} bytes ({sizeof_fmt(item.size)})"),
    ]
    if item.mtime > 0:
        rows.append((_("Modified"), time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(item.mtime))))

    reader = QImageReader(item.filename)
    size = reader.size()
    if size.isValid():
        rows.append((_("Dimensions"), f"{size.width()} × {size.height()} px"))
        frames = reader.imageCount()
        if frames > 1:
            rows.append((_("Frames"), str(frames)))
    else:
        rows.append((_("Dimensions"), _("Not readable by Qt")))

    rows.extend(read_exif(item.filename))
    return rows


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

        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(1, 1)
        for row, (label, value) in enumerate(image_details(item)):
            key = QLabel(label)
            apply_muted_palette(key)
            self._muted_labels.append(key)
            key.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            value_label = QLabel(value)
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            grid.addWidget(key, row, 0)
            grid.addWidget(value_label, row, 1)
        layout.addLayout(grid)
        layout.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(_("Close"))
        copy = QPushButton(_("Copy Path"))
        _res = copy.clicked.connect(self._copy_path)
        buttons.addButton(copy, QDialogButtonBox.ButtonRole.ActionRole)
        _res = buttons.rejected.connect(self.close)
        layout.addWidget(buttons)

    @override
    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.PaletteChange:
            for label in self._muted_labels:
                apply_muted_palette(label)
        super().changeEvent(event)

    def _copy_path(self) -> None:
        QGuiApplication.clipboard().setText(self._path)
