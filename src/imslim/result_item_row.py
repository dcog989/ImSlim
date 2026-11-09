import os
import time
from collections.abc import Callable
from typing import override

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QContextMenuEvent,
    QIcon,
    QMouseEvent,
    QPalette,
)
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QToolButton,
    QWidget,
)

from ._i18n import _
from .format import savings_percent, sizeof_fmt
from .icons import circle_off_icon, shield_alert_icon, triangle_alert_icon
from .item_menu import build_item_menu
from .result_item import ResultItem, ResultState
from .theme import accent_color, muted_color
from .widgets import ElidedLabel, plain_tooltip

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


def _savings_text(item: ResultItem) -> str:
    """Format the per-item saving; blank for states that have no saving."""
    if item.state in (
        ResultState.IDLE,
        ResultState.CANCELLED,
        ResultState.ERROR,
        ResultState.SKIPPED,
    ):
        return ""
    percent = savings_percent(item.size, item.new_size) if item.size > 0 else 0
    return f"{percent}%"


def item_summary(item: ResultItem) -> str:
    """Short state text shared by the list row and the thumbnail grid."""
    match item.state:
        case ResultState.RUNNING:
            return _("Compressing…")
        case ResultState.CANCELLED:
            return _("Cancelled")
        case ResultState.ERROR:
            return item.error_message or _("Failed")
        case ResultState.DONE:
            return sizeof_fmt(item.size) + " → " + sizeof_fmt(item.new_size)
        case ResultState.SKIPPED:
            return _("Already optimal")
        case _:
            return sizeof_fmt(item.size)


class ResultItemRow(QWidget):
    clicked: Signal = Signal()

    def __init__(self, result_item: ResultItem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.result_item: ResultItem = result_item
        self._alternate: bool = False
        self._selected: bool = False

        self.title_label: ElidedLabel = ElidedLabel(os.path.basename(result_item.filename))
        self.title_label.setToolTip(plain_tooltip(result_item.filename))
        # The name keeps priority; the size/timestamp summary gives way first.
        self.title_label.setMinimumWidth(60)
        self.subtitle_label: ElidedLabel = ElidedLabel()

        self.savings_label: QLabel = QLabel()

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

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        layout.addWidget(self.title_label, 1)
        layout.addWidget(self.subtitle_label)
        layout.addWidget(self.savings_label)
        layout.addWidget(self.spinner)
        layout.addWidget(self.skipped_button)
        layout.addWidget(self.warning_button)
        layout.addWidget(self.error_button)

        self.refresh()
        self._apply_background()

    @staticmethod
    def _make_info_button(handler: Callable[..., None], icon: QIcon) -> QToolButton:
        button = QToolButton()
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

        subtitle = item_summary(item)
        if item.state is ResultState.IDLE and item.mtime > 0:
            subtitle += " · " + time.strftime("%Y-%m-%d %H:%M", time.localtime(item.mtime))
        self.subtitle_label.setText(subtitle)
        self.savings_label.setText(_savings_text(item))
        self.savings_label.setVisible(item.state is not ResultState.IDLE and not running)

        self.skipped_button.setVisible(item.state is ResultState.SKIPPED)
        self.error_button.setVisible(
            item.state is ResultState.ERROR and bool(item.error_details_message)
        )
        self.warning_button.setVisible(bool(item.warning_message) and not running)

    def set_selected(self, selected: bool) -> None:
        if selected == self._selected:
            return
        self._selected = selected
        self._apply_background()

    def set_alternate(self, alternate: bool) -> None:
        if alternate == self._alternate:
            return
        self._alternate = alternate
        self._apply_background()

    def refresh_theme(self) -> None:
        """Re-read the application palette after a light/dark switch."""
        skipped, error, warning = _info_icons(
            QApplication.palette().color(QPalette.ColorRole.WindowText)
        )
        self.skipped_button.setIcon(skipped)
        self.error_button.setIcon(error)
        self.warning_button.setIcon(warning)
        self._apply_background()

    def _apply_background(self) -> None:
        # Read the live application palette: the row is built before it is
        # parented, so this is the same base the old captured copy held, without
        # keeping the old theme or compounding the blend on a repaint.
        palette = QPalette(QApplication.palette())
        window = palette.color(QPalette.ColorRole.Window)
        base = palette.color(QPalette.ColorRole.Base)
        if self._selected:
            color = muted_color(accent_color(), base, 0.55)
        elif self._alternate:
            color = muted_color(base, window, 0.6)
        else:
            color = window
        palette.setColor(QPalette.ColorRole.Window, color)
        self.setPalette(palette)
        self.setAutoFillBackground(True)

    @override
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)

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
        # Accept unconditionally so the window's paste menu does not appear when
        # right-clicking a row.
        event.accept()
        menu = build_item_menu(self.result_item, self)
        if menu.isEmpty():
            return
        _res = menu.exec(event.globalPos())
