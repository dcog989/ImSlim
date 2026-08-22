import os
import tempfile
import time
from collections.abc import Callable
from typing import ClassVar, cast, override

from PySide6.QtCore import (
    QDir,
    QEvent,
    QMimeData,
    QObject,
    QPoint,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QClipboard,
    QContextMenuEvent,
    QDragEnterEvent,
    QDropEvent,
    QIcon,
    QImage,
    QKeySequence,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from ._i18n import _
from ._logging import configure_logging
from .batch_flow import BatchFlow
from .compression_manager import CompressionManager
from .compressors.avif_compressor import AVIFCompressor
from .compressors.gif_compressor import GIFCompressor
from .compressors.jpeg_compressor import JPEGCompressor
from .compressors.jxl_compressor import JXLCompressor
from .compressors.png_compressor import PNGCompressor
from .compressors.svg_compressor import SVGCompressor
from .compressors.webp_compressor import WEBPCompressor
from .format import savings_percent, sizeof_fmt
from .image_utils import image_filter
from .result_item import ResultItem
from .result_item_row import ResultItemRow
from .settings import SettingsDialog
from .settings_manager import SettingsManager
from .system_info import static_about_pairs, system_info_pairs
from .widgets import (
    ResultsPage,
    apply_muted_palette,
    close_icon,
    gear_icon,
    imslim_icon,
    info_icon,
)
from .workers import VersionProbeWorker


class _PasteFilter(QObject):
    """Shows the paste context menu for widgets without their own handler."""

    context_menu_requested: Signal = Signal(QPoint)

    @override
    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.ContextMenu:
            context_event = cast(QContextMenuEvent, event)
            target = QApplication.widgetAt(context_event.globalPos())
            if target is None or not self._is_result_row(target):
                self.context_menu_requested.emit(context_event.globalPos())
                return True
        return super().eventFilter(obj, event)

    @staticmethod
    def _is_result_row(widget: QWidget | None) -> bool:
        current = widget
        while current is not None:
            if isinstance(current, ResultItemRow):
                return True
            current = current.parentWidget()
        return False


_V_SPACING = 16


class ImSlimWindow(QWidget):
    def __init__(self, app: QApplication) -> None:
        super().__init__()
        self.app: QApplication = app
        self.setWindowTitle("ImSlim")
        self.setWindowIcon(imslim_icon())
        self.resize(650, 500)
        self.setAcceptDrops(True)

        self.settings: SettingsManager = SettingsManager()
        self.prefs_dialog: SettingsDialog | None = None
        self._about_dialog: QMessageBox | None = None
        self._about_static_pairs: list[tuple[str, str]] | None = None
        self._about_tool_pairs: list[tuple[str, str]] | None = None

        self.paste_filter: _PasteFilter = _PasteFilter()
        _res = self.paste_filter.context_menu_requested.connect(self.on_context_menu)
        self.installEventFilter(self.paste_filter)

        self.create_actions()
        self.loading_spinner: QProgressBar = QProgressBar()
        self.results_container: QWidget = QWidget()
        self.results_layout: QVBoxLayout = QVBoxLayout()
        self.subtitle_label: QLabel = QLabel()
        self.build_ui()
        self.show_view("home")

        self.manager: CompressionManager = CompressionManager(self.settings)
        self.manager.register_compressor(PNGCompressor)
        self.manager.register_compressor(JPEGCompressor)
        self.manager.register_compressor(WEBPCompressor)
        self.manager.register_compressor(AVIFCompressor)
        self.manager.register_compressor(JXLCompressor)
        self.manager.register_compressor(GIFCompressor)
        self.manager.register_compressor(SVGCompressor)
        self.manager.validate_configured_compressors()

        self.flow: BatchFlow = BatchFlow(self.settings, self.manager)
        _res = self.flow.item_added.connect(self.add_row)
        _res = self.flow.items_ready.connect(self._show_items_ready)
        _res = self.flow.compression_enabled.connect(self.enable_compression)
        _res = self.flow.summary_changed.connect(self._update_summary)
        _res = self.flow.no_files.connect(self._on_analyze_no_files)
        _res = self.flow.output_folder_error.connect(self._on_analyze_output_error)
        _res = self.flow.result_updated.connect(self.update_result_item)

        self.rows: list[ResultItemRow] = []
        self._overlay_timer: QTimer = QTimer(self)
        self._overlay_timer.setSingleShot(True)
        self._overlay_timer.setInterval(1000)
        self._overlay_timer.timeout.connect(self._show_processing_overlay)

    # ------------------------------------------------------------------ UI
    def build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 6, 8, 6)
        header_layout.setSpacing(8)

        icon_color = self.palette().color(self.palette().ColorRole.WindowText)

        self.about_button: QToolButton = self._make_icon_button(
            info_icon(icon_color), _("About ImSlim"), self.on_about
        )
        self.clear_button: QToolButton = self._make_icon_button(
            close_icon(icon_color),
            _("Clear results and return to the main window."),
            self.clear_results,
        )

        self.stop_button: QToolButton = QToolButton()
        self.stop_button.setText(_("Stop"))
        self.stop_button.setToolTip(_("Stop the current compression."))
        self.stop_button.setFixedHeight(32)
        self.stop_button.setStyleSheet("QToolButton { padding: 0 12px; }")
        _res = self.stop_button.clicked.connect(self.stop_compression)

        header_layout.addWidget(self.about_button)

        header_layout.addStretch(1)

        self.results_title: QLabel = QLabel(_("Compression Results"))
        title_font = self.results_title.font()
        title_font.setPointSize(15)
        title_font.setBold(True)
        self.results_title.setFont(title_font)
        self.results_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.results_title.hide()
        header_layout.addWidget(self.results_title, alignment=Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.clear_button)

        header_layout.addStretch(1)

        self.settings_button: QToolButton = self._make_icon_button(
            gear_icon(icon_color), _("Settings"), self.on_settings
        )
        header_layout.addWidget(self.settings_button)

        root.addWidget(header)

        # Content stack
        self.stack: QStackedWidget = QStackedWidget()

        self.home_page: QWidget = self._build_home_page()
        self.loading_page: QWidget = self._build_loading_page()
        self.results_page: QWidget = self._build_results_page()

        _res = self.stack.addWidget(self.home_page)  # index 0
        _res = self.stack.addWidget(self.loading_page)  # index 1
        _res = self.stack.addWidget(self.results_page)  # index 2

        root.addWidget(self.stack, 1)

        self.set_active_settings()

    def _build_home_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, _V_SPACING, 40, _V_SPACING)
        layout.setSpacing(_V_SPACING)

        layout.addStretch(1)

        icon = QLabel()
        icon.setPixmap(imslim_icon().pixmap(240))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)

        layout.addStretch(1)

        self.subtitle_label = QLabel()
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.subtitle_label)

        layout.addStretch(1)

        drop_label = QLabel(_("Drop or paste files or directory here to compress."))
        drop_font = drop_label.font()
        drop_font.setPointSize(12)
        drop_font.setBold(True)
        drop_label.setFont(drop_font)
        drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(drop_label)

        layout.addStretch(1)

        # Bottom buttons
        buttons = QHBoxLayout()
        buttons.setSpacing(8)

        lozenge = (
            "QPushButton {"
            "  border-radius: 18px;"
            "  background-color: palette(highlight);"
            "  color: palette(highlighted-text);"
            "  border: none;"
            "  padding: 6px 20px;"
            "}"
            "QPushButton:hover {"
            "  background-color: palette(Highlight);"
            "}"
            "QPushButton:pressed {"
            "  background-color: palette(dark);"
            "}"
        )

        select_files = QPushButton(_("Select Files"))
        select_files.setMinimumHeight(36)
        select_files.setFixedWidth(200)
        select_files.setCursor(Qt.CursorShape.PointingHandCursor)
        _res = select_files.clicked.connect(self.on_select)
        select_files.setStyleSheet(lozenge)
        buttons.addWidget(select_files, 0, Qt.AlignmentFlag.AlignCenter)

        select_dir = QPushButton(_("Select Directory"))
        select_dir.setMinimumHeight(36)
        select_dir.setFixedWidth(200)
        select_dir.setCursor(Qt.CursorShape.PointingHandCursor)
        _res = select_dir.clicked.connect(self.on_select_folder)
        select_dir.setStyleSheet(lozenge)
        buttons.addWidget(select_dir, 0, Qt.AlignmentFlag.AlignCenter)

        layout.addLayout(buttons)
        layout.addStretch(1)
        return page

    def _build_loading_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addStretch(1)
        self.loading_spinner = QProgressBar()
        self.loading_spinner.setRange(0, 0)
        self.loading_spinner.setTextVisible(False)
        self.loading_spinner.setFixedWidth(120)
        self.loading_spinner.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel(_("Analyzing Images"))
        title_font = title.font()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        description = QLabel(_("Analyzing your images before compression…"))
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.loading_spinner, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(12)
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addStretch(1)
        return page

    def _build_results_page(self) -> ResultsPage:
        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setContentsMargins(12, 12, 12, 12)
        self.results_layout.setSpacing(2)
        self.results_layout.addWidget(self._build_results_header())
        self.results_layout.addStretch(1)
        self.summary_label = self._build_summary_label()
        self.results_layout.addWidget(self.summary_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.results_container)

        page = ResultsPage(self.stop_button)
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(scroll)
        return page

    def _build_results_header(self) -> QWidget:
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(8)

        image_label = QLabel(_("Image:"))
        reduced_label = QLabel(_("Reduced by:"))
        header_font = image_label.font()
        header_font.setBold(True)
        image_label.setFont(header_font)
        reduced_label.setFont(header_font)

        layout.addWidget(image_label)
        layout.addStretch(1)
        layout.addWidget(reduced_label)
        return header

    def _build_summary_label(self) -> QLabel:
        label = QLabel()
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setContentsMargins(0, 8, 0, 0)
        apply_muted_palette(label)
        return label

    # ----------------------------------------------------------------- actions
    def create_actions(self) -> None:
        self.act_select: QAction = QAction(_("Browse Files"), self)
        self.act_select.setShortcut(QKeySequence("Ctrl+O"))
        _res = self.act_select.triggered.connect(self.on_select)

        self.act_paste: QAction = QAction(_("Paste from Clipboard"), self)
        self.act_paste.setShortcut(QKeySequence.StandardKey.Paste)
        _res = self.act_paste.triggered.connect(self.on_paste)

        self.act_select_folder: QAction = QAction(_("Browse Directory"), self)
        _res = self.act_select_folder.triggered.connect(self.on_select_folder)

        self.act_clear: QAction = QAction(_("Clear Results"), self)
        self.act_clear.setShortcut(QKeySequence("Ctrl+Shift+C"))
        _res = self.act_clear.triggered.connect(self.clear_results)

        self.act_settings: QAction = QAction(_("Settings"), self)
        self.act_settings.setShortcut(QKeySequence("Ctrl+,"))
        _res = self.act_settings.triggered.connect(self.on_settings)

        self.act_quit: QAction = QAction(_("Quit"), self)
        self.act_quit.setShortcut(QKeySequence("Ctrl+Q"))
        _res = self.act_quit.triggered.connect(self.app.quit)

        self.addAction(self.act_select)
        self.addAction(self.act_paste)
        self.addAction(self.act_clear)
        self.addAction(self.act_settings)
        self.addAction(self.act_quit)

    # ----------------------------------------------------------------- helpers
    @staticmethod
    def _make_icon_button(icon: QIcon, tooltip: str, handler: Callable[[], None]) -> QToolButton:
        button = QToolButton()
        button.setIcon(icon)
        button.setIconSize(QSize(20, 20))
        button.setToolTip(tooltip)
        button.setFixedSize(32, 32)
        button.setStyleSheet("QToolButton { padding: 0; }")
        _res = button.clicked.connect(handler)
        return button

    def enable_compression(self, enable: bool) -> None:
        self.clear_button.setEnabled(enable)
        if enable:
            self._overlay_timer.stop()
            self.results_page.hide_overlay()
            self.stop_button.setEnabled(True)
        else:
            self._overlay_timer.start()

    def _show_processing_overlay(self) -> None:
        self.results_page.show_overlay()

    def stop_compression(self) -> None:
        self.flow.cancel()
        self.stop_button.setEnabled(False)

    _VIEWS: ClassVar[dict[str, tuple[int, bool]]] = {
        "home": (0, False),
        "loading": (1, False),
        "results": (2, True),
    }

    def show_view(self, view: str) -> None:
        index, show_clear = self._VIEWS[view]
        self.stack.setCurrentIndex(index)
        self.clear_button.setVisible(show_clear)
        self.results_title.setVisible(view == "results")

    def clear_results(self) -> None:
        self.show_view("home")
        while self.results_layout.count() > 3:
            item = self.results_layout.takeAt(1)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                if isinstance(widget, ResultItemRow):
                    widget.stop_thumbnail_loader()
                widget.deleteLater()
        self.rows.clear()
        self.flow.reset()

    # ------------------------------------------------------- compression flow
    def start_compression(self, paths: list[str]) -> None:
        """Begin compressing the given paths, switching to the loading view only
        once at least one file has been collected."""
        if self.flow.active:
            _res = QMessageBox.information(
                self, _("Compression in progress"), _("Wait for the current compression to finish.")
            )
            return
        self.compress_files(paths)

    def compress_files(self, paths: list[str]) -> None:
        if self.flow.active:
            _res = QMessageBox.information(
                self, _("Compression in progress"), _("Wait for the current compression to finish.")
            )
            return
        self.show_view("loading")
        self.flow.start(paths)

    def _show_items_ready(self) -> None:
        self.show_view("results")

    def _on_analyze_no_files(self) -> None:
        self.show_view("home")
        _res = QMessageBox.information(self, _("No files found"), _("No files found"))

    def _on_analyze_output_error(self) -> None:
        self.show_view("home")
        _res = QMessageBox.warning(self, _("Error"), _("Can't create the output folder."))

    def add_row(self, result_item: ResultItem) -> None:
        row = ResultItemRow(result_item)
        self.results_layout.insertWidget(1, row)
        self.rows.append(row)

    def update_result_item(self, result_item: ResultItem) -> None:
        result_item.running = False
        if result_item.cancelled:
            result_item.subtitle_label = _("Cancelled")
            result_item.savings = ""
        elif result_item.error:
            result_item.subtitle_label = result_item.error_message
        elif result_item.skipped:
            result_item.savings = ""
        else:
            if result_item.size > 0:
                savings = savings_percent(result_item.size, result_item.new_size)
            else:
                savings = 0
            result_item.savings = str(savings) + "%"
            result_item.subtitle_label += " → " + sizeof_fmt(result_item.new_size)
        result_item.updated.emit()

    def _update_summary(self) -> None:
        self.summary_label.setText(self.flow.summary.text())

    # ----------------------------------------------------------------- file IO
    def on_context_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)
        menu.addAction(self.act_paste)
        _res = menu.addSeparator()
        menu.addAction(self.act_select)
        menu.addAction(self.act_select_folder)
        _res = menu.exec(pos)

    def on_paste(self) -> None:
        clipboard = self.app.clipboard()
        paths = self._urls_to_paths(clipboard.mimeData())

        if paths:
            self.start_compression(paths)
            return

        self._read_clipboard_image(clipboard, attempts=0)

    @staticmethod
    def _urls_to_paths(mime: QMimeData) -> list[str]:
        paths: list[str] = []
        if mime.hasUrls():
            for url in mime.urls():
                local = url.toLocalFile()
                if local:
                    paths.append(local)
        return paths

    def _read_clipboard_image(self, clipboard: QClipboard, attempts: int) -> None:
        # On Wayland, image data is transferred asynchronously from the
        # clipboard owner, so the first read may come back empty. Retry on a
        # QTimer instead of sleeping in a loop so the UI thread stays responsive.
        image = clipboard.image()
        if not image.isNull():
            self._handle_clipboard_image(image)
            return
        if attempts >= 20:
            return
        QTimer.singleShot(
            50,
            lambda: self._read_clipboard_image(clipboard, attempts + 1),
        )

    def _handle_clipboard_image(self, image: QImage) -> None:
        path = self._save_clipboard_image(image)
        if path:
            self.start_compression([path])

    def _save_clipboard_image(self, image: QImage) -> str | None:
        directory = tempfile.gettempdir()
        path = os.path.join(directory, f"imslim-pasted-{time.time_ns()}.png")
        if image.save(path, b"PNG"):
            return path
        return None

    def on_select(self) -> None:
        files, _filter = QFileDialog.getOpenFileNames(
            self, _("Select Images"), self._dialog_start_dir(), image_filter()
        )
        if not files:
            return
        self.start_compression(files)

    def on_select_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, _("Select Folder"), self._dialog_start_dir()
        )
        if not folder:
            return
        self.start_compression([folder])

    def _dialog_start_dir(self) -> str:
        start = self.settings.default_open_dialog_directory
        if start and os.path.isdir(start):
            return start
        return QDir.homePath()

    # ------------------------------------------------------------------ DnD
    @override
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        mime = event.mimeData()
        if mime.hasUrls():
            event.acceptProposedAction()

    @override
    def dropEvent(self, event: QDropEvent) -> None:
        paths = self._urls_to_paths(event.mimeData())
        if not paths:
            return
        self.start_compression(paths)

    # ------------------------------------------------------------- active settings
    def set_active_settings(self) -> None:
        parts = [
            _("Lossy") if self.settings.lossy else _("Lossless"),
            _("Keep metadata") if self.settings.metadata else _("Remove metadata"),
            _("Keep attributes") if self.settings.file_attributes else _("Reset attributes"),
        ]
        self.subtitle_label.setText(f"[ {' | '.join(parts)} ]")

    # ------------------------------------------------------------- dialogs
    def on_settings(self) -> None:
        if self.prefs_dialog is not None:
            _res = self.prefs_dialog.close()
        self.prefs_dialog = SettingsDialog(self.settings, self)
        _res = self.prefs_dialog.settings_changed.connect(self.set_active_settings)
        _res = self.prefs_dialog.settings_changed.connect(self._reconfigure_logging)
        self.prefs_dialog.show()

    def _reconfigure_logging(self) -> None:
        # Log level / max size / backups apply immediately rather than at the
        # next restart; pass the live settings so unsynced edits are honored.
        configure_logging(self.settings)

    def on_about(self) -> None:
        static_pairs = static_about_pairs()
        dialog = QMessageBox(
            QMessageBox.Icon.NoIcon,
            _("About ImSlim"),
            self._about_message(),
            parent=self,
        )
        dialog.setIconPixmap(imslim_icon().pixmap(96))
        copy_button = dialog.addButton(_("Copy Environment"), QMessageBox.ButtonRole.ActionRole)
        self._about_dialog = dialog
        self._about_static_pairs = static_pairs
        self._about_tool_pairs = []
        _res = copy_button.clicked.connect(self._on_copy_environment)
        worker = VersionProbeWorker()
        _res = worker.versions_ready.connect(self._on_about_versions)
        # Each probe deletes itself when done, so reopening the dialog while a
        # previous probe is still running can't delete the newer worker.
        _res = worker.finished.connect(lambda: worker.deleteLater())
        worker.start()
        _res = dialog.exec()
        self._about_dialog = None
        self._about_static_pairs = None
        self._about_tool_pairs = None

    @staticmethod
    def _about_message() -> str:
        return _(
            "<div style='min-width: 360px;'>"
            + "<div style='font-size: 18pt; font-weight: bold;'>ImSlim</div>"
            + "<div style='font-size: 9pt; color: #808080;'>"
            + "Version {version}</div>"
            + "<div style='margin-top: 10px;'>"
            + "Compress common image formats, lossless or lossy.</div>"
            + "</div>"
        ).format(version=__version__)

    def _on_copy_environment(self) -> None:
        lines: list[str] = []
        if self._about_static_pairs is not None:
            lines += [f"{key}: {value}" for key, value in self._about_static_pairs]
        lines += [f"{key}: {value}" for key, value in system_info_pairs()]
        qt_platform = QApplication.platformName()
        if qt_platform:
            lines.append(f"Qt Platform: {qt_platform}")
        if self._about_tool_pairs is not None:
            lines += [f"{key}: {value}" for key, value in self._about_tool_pairs]
        clipboard = QApplication.clipboard()
        clipboard.setText("\n".join(lines))

    def _on_about_versions(self, tool_pairs: list[tuple[str, str]]) -> None:
        self._about_tool_pairs = tool_pairs
