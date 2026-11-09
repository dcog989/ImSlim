"""Dialogs: batch progress, batch completion and the About window."""

import html
import os
from typing import override

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QPalette, QShowEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from ._i18n import _
from ._logging import LOG_LEVELS, configure_logging
from .batch_summary import BatchSummary
from .format import savings_percent, sizeof_fmt
from .icons import imslim_icon, shield_alert_icon
from .result_item import ResultItem, ResultState
from .settings_manager import SettingsManager, config_file_path, log_file_path
from .spinner import Spinner
from .system_info import static_about_pairs, system_info_pairs
from .theme import apply_muted_palette
from .workers import VersionProbeTask, start_task

_GITHUB_URL = "https://github.com/dcog989/ImSlim"
# The completion list is for failures and a sample; a huge batch must not
# build one widget per file on the UI thread.
_MAX_LISTED = 200

# Log level labels match the values in _logging.LOG_LEVELS, in that order.
_LOG_LEVEL_LABELS: dict[str, str] = {
    "NONE": _("None"),
    "DEBUG": _("Debug"),
    "INFO": _("Info"),
    "WARNING": _("Warning"),
    "ERROR": _("Error"),
}


class ProgressDialog(QDialog):
    """Busy dialog with a running counter and a cancel button."""

    cancel_requested: Signal = Signal()

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self.setMinimumWidth(320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        self.spinner: Spinner = Spinner(64)
        layout.addWidget(self.spinner, alignment=Qt.AlignmentFlag.AlignCenter)
        self.label: QLabel = QLabel(_("Processing…"))
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)
        self.bar: QProgressBar = QProgressBar()
        self.bar.setRange(0, 0)
        self.bar.setTextVisible(False)
        layout.addWidget(self.bar)
        cancel = QPushButton(_("Cancel"))
        _res = cancel.clicked.connect(self.cancel_requested.emit)
        layout.addWidget(cancel, alignment=Qt.AlignmentFlag.AlignCenter)

    @override
    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.spinner.start()

    @override
    def done(self, result: int) -> None:
        self.spinner.stop()
        super().done(result)

    def set_progress(self, done: int, total: int) -> None:
        if total <= 0:
            self.bar.setRange(0, 0)
            return
        self.bar.setRange(0, total)
        self.bar.setValue(done)
        # A figure space is digit-width, so the centred counter keeps its place
        # when the done count gains a digit.
        done_text = str(done).rjust(len(str(total)), "\u2007")
        self.label.setText(_("{done} of {total} images").format(done=done_text, total=total))


def batch_size_totals(result_items: list[ResultItem]) -> tuple[int, int]:
    """Total bytes before and after for the non-failed items.

    Skipped, cancelled and not-yet-processed items keep their source file, so
    their after-size is the original. A finished item reports its real output,
    which may be larger than the source.
    """
    original = 0
    after = 0
    for item in result_items:
        if item.state is ResultState.ERROR:
            continue
        original += item.size
        after += item.new_size if item.state is ResultState.DONE else item.size
    return original, after


class CompletionDialog(QDialog):
    """Batch summary: counts, elapsed time, savings and the files that need attention."""

    def __init__(
        self,
        summary: BatchSummary,
        result_items: list[ResultItem],
        elapsed_seconds: float,
        output_folder: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("Finished"))
        self.setMinimumWidth(460)
        self._rows: list[ResultItem] = list(result_items)
        self._output_folder: str = output_folder or self._result_folder()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        headline = QLabel(_("Compression finished"))
        headline_font = headline.font()
        headline_font.setPointSize(14)
        headline_font.setBold(True)
        headline.setFont(headline_font)
        layout.addWidget(headline)

        original, after = batch_size_totals(result_items)
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(4)
        _res = self._grid_row(grid, 0, _("Images"), str(summary.total))
        _res = self._grid_row(grid, 1, _("Time"), _elapsed_text(elapsed_seconds))
        _res = self._grid_row(grid, 2, _("Size"), f"{sizeof_fmt(original)} → {sizeof_fmt(after)}")
        _res = self._grid_row(grid, 3, _("Skipped"), str(summary.skipped))
        self.failed_label: QLabel = self._grid_row(grid, 4, _("Failed"), str(summary.failed))
        if summary.failed:
            self.failed_label.setStyleSheet(f"color: {QColor(Qt.GlobalColor.red).name()};")
        layout.addLayout(grid)

        self.list: QListWidget = QListWidget()
        self.list.setMinimumHeight(120)
        self._populate_list()
        layout.addWidget(self.list, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(_("Close"))
        if self._output_folder:
            open_folder = QPushButton(_("Open Output Folder"))
            _res = open_folder.clicked.connect(self._open_output_folder)
            buttons.addButton(open_folder, QDialogButtonBox.ButtonRole.ActionRole)
        _res = buttons.rejected.connect(self.close)
        layout.addWidget(buttons)

    @staticmethod
    def _grid_row(grid: QGridLayout, row: int, label: str, value: str) -> QLabel:
        key = QLabel(label)
        key.setWordWrap(False)
        grid.addWidget(key, row, 0)
        value_label = QLabel(value)
        value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        grid.addWidget(value_label, row, 1)
        return value_label

    def _populate_list(self) -> None:
        failures = [item for item in self._rows if item.state is ResultState.ERROR]
        others = [item for item in self._rows if item.state is not ResultState.ERROR]
        shown = failures[:_MAX_LISTED]
        shown += others[: max(0, _MAX_LISTED - len(shown))]
        for item in shown:
            entry = QListWidgetItem(self._row_text(item))
            entry.setToolTip(item.error_details_message or item.error_message)
            if item.state is ResultState.ERROR:
                entry.setForeground(QColor(Qt.GlobalColor.red))
                entry.setIcon(shield_alert_icon(QColor(Qt.GlobalColor.red), 16))
            self.list.addItem(entry)
        remaining = len(self._rows) - len(shown)
        if remaining:
            self.list.addItem(
                QListWidgetItem(_("… and {count} more files").format(count=remaining))
            )
        if not self._rows:
            self.list.hide()

    @staticmethod
    def _row_text(item: ResultItem) -> str:
        name = os.path.basename(item.filename)
        match item.state:
            case ResultState.ERROR:
                text = _("Failed: {name}").format(name=name)
                return f"{text} — {item.error_message}" if item.error_message else text
            case ResultState.SKIPPED:
                return _("Skipped: {name}").format(name=name)
            case ResultState.CANCELLED:
                return _("Cancelled: {name}").format(name=name)
            case _:
                percent = savings_percent(item.size, item.new_size)
                return _("{name} — {percent}%").format(name=name, percent=percent)

    def _result_folder(self) -> str:
        """The folder the batch wrote to, when it did not go to one output folder."""
        for item in self._rows:
            folder = os.path.dirname(item.new_filename)
            if folder and os.path.isdir(folder):
                return folder
        return ""

    def _open_output_folder(self) -> None:
        if os.path.isdir(self._output_folder):
            _res = QDesktopServices.openUrl(QUrl.fromLocalFile(self._output_folder))


def _elapsed_text(seconds: float) -> str:
    if seconds < 60:
        return _("{seconds:.1f} s").format(seconds=seconds)
    minutes = int(seconds // 60)
    return _("{minutes} min {seconds:.0f} s").format(minutes=minutes, seconds=seconds % 60)


class AboutView(QWidget):
    """Logo, facts table with clickable paths, log level, and the copied environment."""

    def __init__(self, settings: SettingsManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings: SettingsManager = settings
        self._tool_pairs: list[tuple[str, str]] = []
        self._populated: bool = False
        self._probe_worker: VersionProbeTask | None = None
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        icon = QLabel()
        icon.setPixmap(imslim_icon().pixmap(80))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)

        title = QLabel("ImSlim")
        title_font = title.font()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        tagline = QLabel(_("Compress common image formats, lossless or lossy."))
        apply_muted_palette(tagline)
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(tagline)
        layout.addSpacing(14)

        table = QGridLayout()
        table.setHorizontalSpacing(32)
        table.setVerticalSpacing(8)
        table.setColumnMinimumWidth(0, 64)
        table.setColumnStretch(1, 1)

        log_file = log_file_path()
        config_file = config_file_path()
        row = 0
        self._add_row(table, row, _("Version"), QLabel(__version__))
        row += 1
        self._add_separator(table, row)
        row += 1
        self._add_row(table, row, _("Config"), self._path_link(config_file))
        row += 1
        self._add_row(table, row, _("Logs"), self._path_link(os.path.dirname(log_file)))
        row += 1
        self._add_row(
            table,
            row,
            _("Latest log"),
            self._link(_("Open latest log"), QUrl.fromLocalFile(log_file)),
        )
        row += 1
        self._add_row(table, row, _("Log level"), self._build_log_level())
        row += 1
        self._add_separator(table, row)
        row += 1
        self._add_row(table, row, _("Source"), self._link(_GITHUB_URL, QUrl(_GITHUB_URL)))
        layout.addLayout(table)

        layout.addSpacing(14)
        self.copy_button: QPushButton = QPushButton(_("Copy Environment"))
        self.copy_button.setFixedWidth(180)
        _res = self.copy_button.clicked.connect(self._copy_environment)
        layout.addWidget(self.copy_button, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)

    def _build_log_level(self) -> QComboBox:
        combo = QComboBox()
        combo.addItems([_LOG_LEVEL_LABELS[level] for level in LOG_LEVELS])
        combo.setMaximumWidth(160)
        level = self._settings.log_level
        combo.setCurrentIndex(LOG_LEVELS.index(level) if level in LOG_LEVELS else 1)
        _res = combo.currentIndexChanged.connect(self._on_log_level)
        return combo

    def _on_log_level(self, index: int) -> None:
        self._settings.log_level = LOG_LEVELS[index]
        configure_logging(self._settings)

    @staticmethod
    def _add_row(grid: QGridLayout, row: int, label: str, value: QWidget) -> None:
        key = QLabel(label)
        apply_muted_palette(key)
        key.setFixedWidth(64)
        key.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        grid.addWidget(key, row, 0)
        if isinstance(value, QLabel):
            value.setMaximumWidth(420)
        grid.addWidget(value, row, 1)

    @staticmethod
    def _add_separator(grid: QGridLayout, row: int) -> None:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        apply_muted_palette(
            line,
            factor=0.6,
            fg_role=QPalette.ColorRole.WindowText,
            bg_role=QPalette.ColorRole.Window,
        )
        grid.addWidget(line, row, 0, 1, 2)

    @staticmethod
    def _link(text: str, url: QUrl) -> QLabel:
        label = QLabel(f'<a href="{html.escape(url.toString(), quote=True)}">{text}</a>')
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setOpenExternalLinks(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        return label

    def _path_link(self, path: str) -> QLabel:
        return self._link(html.escape(path), QUrl.fromLocalFile(path))

    def populate(self) -> None:
        if self._populated:
            return
        self._populated = True
        # Only the tool versions need work; they spawn subprocesses, so probe
        # them off the UI thread for the environment copied into bug reports.
        worker = VersionProbeTask()
        _res = worker.versions_ready.connect(self._on_versions)
        self._probe_worker = worker
        start_task(worker)

    def _env_text(self) -> str:
        lines: list[str] = []
        lines += [f"{key}: {value}" for key, value in static_about_pairs()]
        lines += [f"{key}: {value}" for key, value in system_info_pairs()]
        qt_platform = QApplication.platformName()
        if qt_platform:
            lines.append(f"Qt Platform: {qt_platform}")
        lines += [f"{key}: {value}" for key, value in self._tool_pairs]
        return "\n".join(lines)

    def _on_versions(self, tool_pairs: list[tuple[str, str]]) -> None:
        self._tool_pairs = tool_pairs

    def _copy_environment(self) -> None:
        QApplication.clipboard().setText(self._env_text())
        self.copy_button.setText(_("Copied"))
        QTimer.singleShot(2000, lambda: self.copy_button.setText(_("Copy Environment")))


class AboutDialog(QDialog):
    """The About tab content in its own window, opened from column 2."""

    def __init__(self, settings: SettingsManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("About ImSlim"))
        self.resize(560, 480)
        self.tab: AboutView = AboutView(settings)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tab)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(_("Close"))
        _res = buttons.rejected.connect(self.close)
        wrapper = QHBoxLayout()
        wrapper.setContentsMargins(12, 0, 12, 12)
        wrapper.addStretch(1)
        wrapper.addWidget(buttons)
        layout.addLayout(wrapper)
        self.tab.populate()
