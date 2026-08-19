import os
import tempfile
import time
from typing import ClassVar

from PySide6.QtCore import QEvent, QObject, QPoint, Qt, Signal
from PySide6.QtGui import QAction, QIcon, QImage, QKeySequence
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
from .compression_manager import CompressionManager
from .compressors.avif_compressor import AVIFCompressor
from .compressors.gif_compressor import GIFCompressor
from .compressors.jpeg_compressor import JPEGCompressor
from .compressors.jxl_compressor import JXLCompressor
from .compressors.png_compressor import PNGCompressor
from .compressors.svg_compressor import SVGCompressor
from .compressors.webp_compressor import WEBPCompressor
from .preferences import PreferencesDialog
from .result_item import ResultItem
from .result_item_manager import ResultItemManager
from .result_item_row import ResultItemRow
from .settings_manager import SAVE_BACKUP_OVERWRITE, SAVE_NEW_FILE, SettingsManager
from .tools import (
    debug_pairs,
    get_image_paths_from_folder,
    image_filter,
    sizeof_fmt,
)
from .widgets import ModeToggle, stylized_i_icon


class _Bridge(QObject):
    result_updated = Signal(object)
    compression_enabled = Signal(bool)


class _PasteFilter(QObject):
    """Shows the paste context menu for widgets without their own handler."""

    context_menu_requested = Signal(QPoint)

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.ContextMenu:
            target = QApplication.widgetAt(event.globalPos())
            if target is None or not self._is_result_row(target):
                self.context_menu_requested.emit(event.globalPos())
                return True
        return super().eventFilter(obj, event)

    @staticmethod
    def _is_result_row(widget) -> bool:
        current = widget
        while current is not None:
            if isinstance(current, ResultItemRow):
                return True
            current = current.parentWidget()
        return False


_HAMBURGER = "\u2630"


class ImSlimWindow(QWidget):
    def __init__(self, app, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.app = app
        self.setWindowTitle("ImSlim")
        self.setWindowIcon(QIcon(stylized_i_icon(128)))
        self.resize(650, 500)
        self.setAcceptDrops(True)

        self.settings = SettingsManager()
        self.bridge = _Bridge()
        self.bridge.result_updated.connect(self.update_result_item)
        self.bridge.compression_enabled.connect(self.enable_compression)
        self.prefs_dialog = None

        self.paste_filter = _PasteFilter()
        self.paste_filter.context_menu_requested.connect(self.on_context_menu)
        self.installEventFilter(self.paste_filter)

        self.create_actions()
        self.build_ui()
        self.show_view("home")

        self.manager = CompressionManager(self.settings)
        self.manager.register_compressor(PNGCompressor)
        self.manager.register_compressor(JPEGCompressor)
        self.manager.register_compressor(WEBPCompressor)
        self.manager.register_compressor(AVIFCompressor)
        self.manager.register_compressor(JXLCompressor)
        self.manager.register_compressor(GIFCompressor)
        self.manager.register_compressor(SVGCompressor)

        self.result_item_manager = ResultItemManager(self.settings)
        self.rows: list[ResultItemRow] = []

    # ------------------------------------------------------------------ UI
    def build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 6, 8, 6)

        self.clear_button = QToolButton()
        self.clear_button.setText(_("Clear"))
        self.clear_button.setToolTip(_("Clear results and return to the main window."))
        self.clear_button.setFixedHeight(32)
        self.clear_button.setStyleSheet("QToolButton { padding: 0 12px; }")
        self.clear_button.clicked.connect(self.clear_results)

        self.stop_button = QToolButton()
        self.stop_button.setText(_("Stop"))
        self.stop_button.setToolTip(_("Stop the current compression."))
        self.stop_button.setFixedHeight(32)
        self.stop_button.setStyleSheet("QToolButton { padding: 0 12px; }")
        self.stop_button.clicked.connect(self.stop_compression)
        self.stop_button.hide()

        header_layout.addWidget(self.clear_button)
        header_layout.addWidget(self.stop_button)
        header_layout.addStretch(1)

        self.mode_toggle = ModeToggle()
        self.mode_toggle.setMinimumWidth(240)
        self.mode_toggle.setMaximumWidth(240)
        header_layout.addWidget(self.mode_toggle, alignment=Qt.AlignCenter)

        header_layout.addStretch(1)

        self.menu_button = QToolButton()
        self.menu_button.setText(_HAMBURGER)
        self.menu_button.setToolTip(_("Main Menu"))
        self.menu_button.setFixedSize(32, 32)
        self.menu_button.clicked.connect(self._open_main_menu)
        header_layout.addWidget(self.menu_button)

        self.subtitle_label = QLabel()
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        self.subtitle_label.hide()

        root.addWidget(header)

        # Content stack
        self.stack = QStackedWidget()

        self.home_page = self._build_home_page()
        self.loading_page = self._build_loading_page()
        self.results_page = self._build_results_page()

        self.stack.addWidget(self.home_page)  # index 0
        self.stack.addWidget(self.loading_page)  # index 1
        self.stack.addWidget(self.results_page)  # index 2

        root.addWidget(self.stack, 1)

        self._apply_mode_state()
        self.set_saving_subtitle()

    def _build_home_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 24, 40, 32)
        layout.addStretch(1)

        icon = QLabel()
        icon.setPixmap(stylized_i_icon(180))
        icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon)

        layout.addSpacing(8)

        drop_label = QLabel(_("Drop or paste files or directory here to compress."))
        drop_font = drop_label.font()
        drop_font.setPointSize(12)
        drop_font.setBold(True)
        drop_label.setFont(drop_font)
        drop_label.setAlignment(Qt.AlignCenter)
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
        select_files.setCursor(Qt.PointingHandCursor)
        select_files.clicked.connect(self.on_select)
        select_files.setStyleSheet(lozenge)
        buttons.addWidget(select_files, 0, Qt.AlignCenter)

        select_dir = QPushButton(_("Select Directory"))
        select_dir.setMinimumHeight(36)
        select_dir.setFixedWidth(200)
        select_dir.setCursor(Qt.PointingHandCursor)
        select_dir.clicked.connect(self.on_select_folder)
        select_dir.setStyleSheet(lozenge)
        buttons.addWidget(select_dir, 0, Qt.AlignCenter)

        layout.addLayout(buttons)
        return page

    def _build_loading_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addStretch(1)
        self.loading_spinner = QProgressBar()
        self.loading_spinner.setRange(0, 0)
        self.loading_spinner.setTextVisible(False)
        self.loading_spinner.setFixedWidth(120)
        self.loading_spinner.setAlignment(Qt.AlignCenter)

        title = QLabel(_("Analyzing Images"))
        title_font = title.font()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)

        description = QLabel(_("Analyzing your images before compression…"))
        description.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.loading_spinner, alignment=Qt.AlignCenter)
        layout.addSpacing(12)
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addStretch(1)
        return page

    def _build_results_page(self):
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

    def _build_main_menu(self) -> QMenu:
        menu = QMenu(self)
        menu.addAction(self.act_settings)
        menu.addAction(self.act_about)
        menu.setStyleSheet(
            "QMenu {"
            "  background-color: palette(base);"
            "  border: 1px solid palette(mid);"
            "  border-radius: 8px;"
            "  padding: 6px;"
            "}"
            "QMenu::item {"
            "  padding: 6px 16px;"
            "  border-radius: 4px;"
            "}"
            "QMenu::item:selected {"
            "  background-color: palette(highlight);"
            "  color: palette(highlighted-text);"
            "}"
        )
        return menu

    def _open_main_menu(self):
        menu = self._build_main_menu()
        button = self.menu_button
        menu_width = menu.sizeHint().width()
        x = button.mapToGlobal(QPoint(0, 0)).x() + button.width() - menu_width
        y = button.mapToGlobal(QPoint(0, 0)).y() + button.height()
        menu.popup(QPoint(x, y))

    # ----------------------------------------------------------------- actions
    def create_actions(self):
        self.act_select = QAction(_("Browse Files"), self)
        self.act_select.setShortcut(QKeySequence("Ctrl+O"))
        self.act_select.triggered.connect(self.on_select)

        self.act_paste = QAction(_("Paste from Clipboard"), self)
        self.act_paste.setShortcut(QKeySequence.StandardKey.Paste)
        self.act_paste.triggered.connect(self.on_paste)

        self.act_select_folder = QAction(_("Browse Directory"), self)
        self.act_select_folder.triggered.connect(self.on_select_folder)

        self.act_clear = QAction(_("Clear Results"), self)
        self.act_clear.setShortcut(QKeySequence("Ctrl+Shift+C"))
        self.act_clear.triggered.connect(self.clear_results)

        self.act_settings = QAction(_("Settings"), self)
        self.act_settings.setShortcut(QKeySequence("Ctrl+,"))
        self.act_settings.triggered.connect(self.on_preferences)

        self.act_about = QAction(_("About ImSlim"), self)
        self.act_about.triggered.connect(self.on_about)

        self.act_quit = QAction(_("Quit"), self)
        self.act_quit.setShortcut(QKeySequence("Ctrl+Q"))
        self.act_quit.triggered.connect(self.app.quit)

        self.addAction(self.act_select)
        self.addAction(self.act_paste)
        self.addAction(self.act_clear)
        self.addAction(self.act_settings)
        self.addAction(self.act_quit)

    # ----------------------------------------------------------------- helpers
    def enable_compression(self, enable):
        self.clear_button.setEnabled(enable)
        self.stop_button.setVisible(not enable)

    def stop_compression(self):
        self.manager.cancel()
        self.stop_button.setEnabled(False)

    _VIEWS: ClassVar[dict[str, tuple[int, bool, bool]]] = {
        "home": (0, False, True),
        "loading": (1, False, True),
        "results": (2, True, False),
    }

    def show_view(self, view):
        index, show_clear, show_mode = self._VIEWS[view]
        self.stack.setCurrentIndex(index)
        self.clear_button.setVisible(show_clear)
        self.mode_toggle.setVisible(show_mode)

    def _apply_mode_state(self):
        self.mode_toggle.setLossy(self.settings.lossy)
        self.mode_toggle.modeChanged.connect(self.on_mode_selected)

    def on_mode_selected(self, lossy):
        self.settings.lossy = lossy

    def clear_results(self):
        self.show_view("home")
        self.rows.clear()
        self.stop_button.hide()
        while self.results_layout.count() > 2:
            item = self.results_layout.takeAt(1)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    # ------------------------------------------------------- compression flow
    def handle_files(self, paths):
        final_files = []
        for path in paths:
            if os.path.isdir(path):
                final_files.extend(get_image_paths_from_folder(path, self.settings.recursive))
            else:
                final_files.append(path)
        return final_files

    def compress_files(self, paths):
        paths = self.handle_files(paths)
        if not paths:
            QMessageBox.information(self, _("No files found"), _("No files found"))
            return

        if not self.result_item_manager.begin_batch():
            QMessageBox.warning(self, _("Error"), _("Can't create the output folder."))
            return

        result_items = []
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

    def add_row(self, result_item):
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
    def on_context_menu(self, pos: QPoint):
        menu = QMenu(self)
        menu.addAction(self.act_paste)
        menu.addSeparator()
        menu.addAction(self.act_select)
        menu.addAction(self.act_select_folder)
        menu.exec(pos)

    def on_paste(self):
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
    def _urls_to_paths(mime) -> list[str]:
        paths = []
        if mime.hasUrls():
            for url in mime.urls():
                local = url.toLocalFile()
                if local:
                    paths.append(local)
        return paths

    def _read_clipboard_image(self, clipboard) -> QImage:
        # On Wayland, image data is transferred asynchronously from the
        # clipboard owner, so the first read may come back empty.
        image = clipboard.image()
        for _ in range(20):
            if not image.isNull():
                break
            self.app.processEvents()
            time.sleep(0.05)
            image = clipboard.image()
        return image

    def _save_clipboard_image(self, image) -> str | None:
        directory = tempfile.gettempdir()
        path = os.path.join(directory, f"imslim-pasted-{time.time_ns()}.png")
        if image.save(path, "PNG"):
            return path
        return None

    def on_select(self):
        files, _filter = QFileDialog.getOpenFileNames(self, _("Select Images"), "", image_filter())
        if not files:
            return
        self.show_view("loading")
        self.compress_files(files)

    def on_select_folder(self):
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
                "subdirectories will be compressed. The original images will "
                "not be modified. New compressed files will be saved with a "
                "“.imslim.[timestamp]” suffix."
            )
        else:
            message = _(
                "All of the images in the directories selected and their "
                "subdirectories will be compressed and overwritten. A backup "
                "of the original images will be saved with a "
                "“.BAK.[timestamp]” suffix."
            )
        if self.settings.output_folder:
            message += "\n\n" + _(f"Output folder: {self.settings.output_folder}")
        box = QMessageBox(self)
        box.setWindowTitle(_("Are you sure you want to compress images in these directories?"))
        box.setText(message)
        box.setIcon(
            QMessageBox.Warning
            if self.settings.save_method == SAVE_BACKUP_OVERWRITE
            else QMessageBox.Question
        )
        box.addButton(QMessageBox.Cancel)
        box.addButton(QMessageBox.Ok)
        return box.exec() == QMessageBox.Ok

    # ------------------------------------------------------------------ DnD
    def dragEnterEvent(self, event):
        mime = event.mimeData()
        if mime.hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = self._urls_to_paths(event.mimeData())
        if not paths:
            return
        self.show_view("loading")
        self.compress_files(paths)

    # ------------------------------------------------------------- save method
    def set_saving_subtitle(self):
        if self.settings.save_method == SAVE_NEW_FILE:
            label = _("Saving new compressed files with a “.imslim.[timestamp]” suffix")
        else:
            label = _("Backing up originals (“.BAK.[timestamp]”) and overwriting them")
        if self.settings.output_folder:
            label += " → " + self.settings.output_folder
        self.subtitle_label.setText(label)

    # ------------------------------------------------------------- dialogs
    def on_preferences(self):
        if self.prefs_dialog is not None:
            self.prefs_dialog.close()
        self.prefs_dialog = PreferencesDialog(self.settings, self)
        self.prefs_dialog.settings_changed.connect(self.set_saving_subtitle)
        self.prefs_dialog.show()

    def on_about(self):
        debug_lines = "".join(
            f"<tr><td><b>{key}</b></td><td>{value}</td></tr>" for key, value in debug_pairs()
        )
        QMessageBox.about(
            self,
            _("About ImSlim"),
            _(
                "<div style='min-width: 360px;'>"
                "<div style='font-size: 18pt; font-weight: bold;'>ImSlim</div>"
                "<div style='font-size: 9pt; color: #808080;'>"
                "Version {version}</div>"
                "<div style='margin-top: 10px;'>"
                "Compress your images in PNG, JPEG, GIF, WebP, AVIF, JXL and SVG, "
                "in both lossless and lossy modes.</div>"
                "<hr style='color: palette(mid); background-color: palette(mid); height: 1px; border: none; margin: 12px 0;'/>"
                "<div style='font-weight: bold;'>Environment</div>"
                "<table style='border-spacing: 6px 2px;'>"
                "{debug}"
                "</table>"
                "</div>"
            ).format(version=__version__, debug=debug_lines),
        )
