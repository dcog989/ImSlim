import os
import tempfile
import time
from typing import ClassVar, cast, override

from PySide6.QtCore import QEvent, QMimeData, QObject, QPoint, QSize, Qt, QThread, Signal
from PySide6.QtGui import (
    QAction,
    QClipboard,
    QContextMenuEvent,
    QDragEnterEvent,
    QDropEvent,
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
from .compression_manager import CompressionManager
from .compressors.avif_compressor import AVIFCompressor
from .compressors.gif_compressor import GIFCompressor
from .compressors.jpeg_compressor import JPEGCompressor
from .compressors.jxl_compressor import JXLCompressor
from .compressors.png_compressor import PNGCompressor
from .compressors.svg_compressor import SVGCompressor
from .compressors.webp_compressor import WEBPCompressor
from .result_item import ResultItem
from .result_item_manager import ResultItemManager
from .result_item_row import ResultItemRow
from .settings import SettingsDialog
from .settings_manager import SAVE_BACKUP_OVERWRITE, SAVE_NEW_FILE, SettingsManager
from .tools import (
    get_image_paths_from_folder,
    image_filter,
    sizeof_fmt,
    static_about_pairs,
    system_info_pairs,
    tool_version_pairs,
)
from .widgets import gear_icon, imslim_icon, info_icon


class _Bridge(QObject):
    result_updated: Signal = Signal(ResultItem)
    compression_enabled: Signal = Signal(bool)


class _VersionProbeWorker(QThread):
    """Queries bundled compression tool versions off the UI thread."""

    versions_ready: Signal = Signal(list)

    @override
    def run(self) -> None:
        self.versions_ready.emit(tool_version_pairs())


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


_CLOSE = "\u2715"


class ImSlimWindow(QWidget):
    def __init__(self, app: QApplication) -> None:
        super().__init__()
        self.app: QApplication = app
        self.setWindowTitle("ImSlim")
        self.setWindowIcon(imslim_icon())
        self.resize(650, 500)
        self.setAcceptDrops(True)

        self.settings: SettingsManager = SettingsManager()
        self.bridge: _Bridge = _Bridge()
        _res = self.bridge.result_updated.connect(self.update_result_item)
        _res = self.bridge.compression_enabled.connect(self.enable_compression)
        self.prefs_dialog: SettingsDialog | None = None
        self._about_dialog: QMessageBox | None = None
        self._about_static_pairs: list[tuple[str, str]] | None = None
        self._about_tool_pairs: list[tuple[str, str]] | None = None
        self._about_worker: _VersionProbeWorker | None = None

        self.paste_filter: _PasteFilter = _PasteFilter()
        _res = self.paste_filter.context_menu_requested.connect(self.on_context_menu)
        self.installEventFilter(self.paste_filter)

        self.create_actions()
        self.loading_spinner: QProgressBar = QProgressBar()
        self.results_container: QWidget = QWidget()
        self.results_layout: QVBoxLayout = QVBoxLayout()
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

        self.result_item_manager: ResultItemManager = ResultItemManager(self.settings)
        self.rows: list[ResultItemRow] = []

    # ------------------------------------------------------------------ UI
    def build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 6, 8, 6)

        icon_color = self.palette().color(self.palette().ColorRole.WindowText)

        self.about_button: QToolButton = QToolButton()
        self.about_button.setIcon(info_icon(icon_color))
        self.about_button.setIconSize(QSize(20, 20))
        self.about_button.setToolTip(_("About ImSlim"))
        self.about_button.setFixedSize(32, 32)
        self.about_button.setStyleSheet("QToolButton { padding: 0; }")
        _res = self.about_button.clicked.connect(self.on_about)

        self.clear_button: QToolButton = QToolButton()
        self.clear_button.setText(_CLOSE)
        self.clear_button.setToolTip(_("Clear results and return to the main window."))
        self.clear_button.setFixedSize(32, 32)
        self.clear_button.setStyleSheet("QToolButton { padding: 0; }")
        _res = self.clear_button.clicked.connect(self.clear_results)

        self.stop_button: QToolButton = QToolButton()
        self.stop_button.setText(_("Stop"))
        self.stop_button.setToolTip(_("Stop the current compression."))
        self.stop_button.setFixedHeight(32)
        self.stop_button.setStyleSheet("QToolButton { padding: 0 12px; }")
        _res = self.stop_button.clicked.connect(self.stop_compression)
        self.stop_button.hide()

        header_layout.addWidget(self.about_button)
        header_layout.addWidget(self.clear_button)
        header_layout.addWidget(self.stop_button)
        header_layout.addStretch(1)

        self.results_title: QLabel = QLabel(_("Compression Results"))
        title_font = self.results_title.font()
        title_font.setPointSize(15)
        title_font.setBold(True)
        self.results_title.setFont(title_font)
        self.results_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.results_title.hide()
        header_layout.addWidget(self.results_title, alignment=Qt.AlignmentFlag.AlignCenter)

        header_layout.addStretch(1)

        self.settings_button: QToolButton = QToolButton()
        self.settings_button.setIcon(gear_icon(icon_color))
        self.settings_button.setIconSize(QSize(20, 20))
        self.settings_button.setToolTip(_("Settings"))
        self.settings_button.setFixedSize(32, 32)
        self.settings_button.setStyleSheet("QToolButton { padding: 0; }")
        _res = self.settings_button.clicked.connect(self.on_settings)
        header_layout.addWidget(self.settings_button)

        self.subtitle_label: QLabel = QLabel()
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label.hide()

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

        self.set_saving_subtitle()

    def _build_home_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 24, 40, 32)
        layout.addStretch(1)

        icon = QLabel()
        icon.setPixmap(imslim_icon().pixmap(180))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)

        layout.addSpacing(8)

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

    def _build_results_page(self) -> QScrollArea:
        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setContentsMargins(12, 12, 12, 12)
        self.results_layout.setSpacing(2)
        self.results_layout.addWidget(self._build_results_header())
        self.results_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.results_container)
        return scroll

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
    def enable_compression(self, enable: bool) -> None:
        self.clear_button.setEnabled(enable)
        self.stop_button.setVisible(not enable)

    def stop_compression(self) -> None:
        self.manager.cancel()
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
        self.rows.clear()
        self.stop_button.hide()
        while self.results_layout.count() > 2:
            item = self.results_layout.takeAt(1)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    # ------------------------------------------------------- compression flow
    def handle_files(self, paths: list[str]) -> list[str]:
        final_files: list[str] = []
        for path in paths:
            if os.path.isdir(path):
                final_files.extend(get_image_paths_from_folder(path, self.settings.recursive))
            else:
                final_files.append(path)
        return final_files

    def compress_files(self, paths: list[str]) -> None:
        paths = self.handle_files(paths)
        if not paths:
            _res = QMessageBox.information(self, _("No files found"), _("No files found"))
            return

        if not self.result_item_manager.begin_batch():
            _res = QMessageBox.warning(self, _("Error"), _("Can't create the output folder."))
            return

        result_items: list[ResultItem] = []
        for path in paths:
            result_item = self.result_item_manager.build(path)
            self.add_row(result_item)
            if result_item.error:
                self.update_result_item(result_item)
            else:
                result_items.append(result_item)

        self.show_view("results")
        self.enable_compression(False)

        for result_item in result_items:
            result_item.running = True
            result_item.updated.emit()

        self.manager.compress(
            result_items,
            self.bridge.result_updated.emit,
            self.bridge.compression_enabled.emit,
        )

    def add_row(self, result_item: ResultItem) -> None:
        row = ResultItemRow(result_item)
        self.results_layout.insertWidget(self.results_layout.count() - 1, row)
        self.rows.append(row)

    def update_result_item(self, result_item: ResultItem):
        result_item.running = False
        if result_item.cancelled:
            result_item.subtitle_label = _("Cancelled")
            result_item.savings = ""
            result_item.updated.emit()
            return
        if result_item.error:
            result_item.subtitle_label = result_item.error_message
        elif result_item.skipped:
            result_item.savings = _("Skipped")
        else:
            if result_item.size > 0:
                savings = round(100 - (result_item.new_size * 100 / result_item.size))
            else:
                savings = 0
            result_item.savings = str(savings) + "%"
            result_item.subtitle_label += " → " + sizeof_fmt(result_item.new_size)
        result_item.updated.emit()

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
            self.show_view("loading")
            self.compress_files(paths)
            return

        image = self._read_clipboard_image(clipboard)
        if image.isNull():
            return
        path = self._save_clipboard_image(image)
        if path:
            self.show_view("loading")
            self.compress_files([path])

    @staticmethod
    def _urls_to_paths(mime: QMimeData) -> list[str]:
        paths: list[str] = []
        if mime.hasUrls():
            for url in mime.urls():
                local = url.toLocalFile()
                if local:
                    paths.append(local)
        return paths

    def _read_clipboard_image(self, clipboard: QClipboard) -> QImage:
        # On Wayland, image data is transferred asynchronously from the
        # clipboard owner, so the first read may come back empty.
        image = clipboard.image()
        attempts = 0
        while attempts < 20:
            if not image.isNull():
                break
            self.app.processEvents()
            time.sleep(0.05)
            image = clipboard.image()
            attempts += 1
        return image

    def _save_clipboard_image(self, image: QImage) -> str | None:
        directory = tempfile.gettempdir()
        path = os.path.join(directory, f"imslim-pasted-{time.time_ns()}.png")
        if image.save(path, b"PNG"):
            return path
        return None

    def on_select(self) -> None:
        files, _filter = QFileDialog.getOpenFileNames(self, _("Select Images"), "", image_filter())
        if not files:
            return
        self.show_view("loading")
        self.compress_files(files)

    def on_select_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, _("Select Folder"))
        if not folder:
            return
        if not self._confirm_directory_compression():
            return
        self.show_view("loading")
        self.compress_files([folder])

    def _confirm_directory_compression(self) -> bool:
        if self.settings.save_method == SAVE_NEW_FILE:
            message = _(
                "All of the images in the directories selected and their "
                + "subdirectories will be compressed. The original images will "
                + "not be modified. New compressed files will be saved with a "
                + "“.imslim.[timestamp]” suffix."
            )
        else:
            message = _(
                "All of the images in the directories selected and their "
                + "subdirectories will be compressed and overwritten. A backup "
                + "of the original images will be saved with a "
                + "“.BAK.[timestamp]” suffix."
            )
        if self.settings.output_folder:
            message += "\n\n" + _("Output folder: %s") % self.settings.output_folder
        box = QMessageBox(self)
        box.setWindowTitle(_("Are you sure you want to compress images in these directories?"))
        box.setText(message)
        box.setIcon(
            QMessageBox.Icon.Warning
            if self.settings.save_method == SAVE_BACKUP_OVERWRITE
            else QMessageBox.Icon.Question
        )
        _res = box.addButton(QMessageBox.StandardButton.Cancel)
        _res = box.addButton(QMessageBox.StandardButton.Ok)
        return box.exec() == QMessageBox.StandardButton.Ok

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
        self.show_view("loading")
        self.compress_files(paths)

    # ------------------------------------------------------------- save method
    def set_saving_subtitle(self) -> None:
        if self.settings.save_method == SAVE_NEW_FILE:
            label = _("Saving new compressed files with a “.imslim.[timestamp]” suffix")
        else:
            label = _("Backing up originals (“.BAK.[timestamp]”) and overwriting them")
        if self.settings.output_folder:
            label += " → " + self.settings.output_folder
        self.subtitle_label.setText(label)

    # ------------------------------------------------------------- dialogs
    def on_settings(self) -> None:
        if self.prefs_dialog is not None:
            _res = self.prefs_dialog.close()
        self.prefs_dialog = SettingsDialog(self.settings, self)
        _res = self.prefs_dialog.settings_changed.connect(self.set_saving_subtitle)
        self.prefs_dialog.show()

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
        worker = _VersionProbeWorker()
        self._about_worker = worker
        _res = worker.versions_ready.connect(self._on_about_versions)
        _res = worker.finished.connect(self._on_about_worker_finished)
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

    def _on_about_worker_finished(self) -> None:
        if self._about_worker is None:
            return
        self._about_worker.deleteLater()
        self._about_worker = None
