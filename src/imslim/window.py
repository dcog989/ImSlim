import html
import os
from collections.abc import Callable
from enum import Enum, auto
from typing import override

from PySide6.QtCore import QDir, QSize, Qt
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QColor,
    QContextMenuEvent,
    QDragEnterEvent,
    QDropEvent,
    QIcon,
    QKeySequence,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ._i18n import _
from ._logging import configure_logging
from .batch_flow import BatchFlow
from .clipboard_intake import ClipboardIntake, urls_to_paths
from .composition import AppContext
from .conversion import is_converting
from .formats import TARGET_SPECS, Format, image_filter
from .icons import chevron_left_icon, download_icon, gear_icon, imslim_icon
from .results_view import ResultsView
from .settings import SettingsDialog
from .settings_manager import SettingsManager
from .theme import combo_stylesheet

_V_SPACING = 16


class View(Enum):
    HOME = auto()
    LOADING = auto()
    RESULTS = auto()


class ImSlimWindow(QWidget):
    def __init__(self, app: QApplication, context: AppContext) -> None:
        super().__init__()
        self.app: QApplication = app
        self.settings: SettingsManager = context.settings
        self.manager = context.manager
        self.flow: BatchFlow = context.flow
        self.clipboard: ClipboardIntake = ClipboardIntake(self.app.clipboard(), self)
        self.setWindowTitle("ImSlim")
        self.setWindowIcon(imslim_icon())
        self.resize(650, 500)
        self.setAcceptDrops(True)

        self.prefs_dialog: SettingsDialog | None = None

        self.create_actions()
        self.build_ui()
        self.show_view(View.HOME)

        _res = self.flow.item_added.connect(self.results.add_item)
        _res = self.flow.items_ready.connect(self._show_items_ready)
        _res = self.flow.compression_enabled.connect(self.enable_compression)
        _res = self.flow.summary_changed.connect(self._update_summary)
        _res = self.flow.no_files.connect(self._on_analyze_no_files)
        _res = self.flow.output_folder_error.connect(self._on_analyze_output_error)
        _res = self.flow.analyze_failed.connect(self._on_analyze_failed)
        _res = self.flow.result_updated.connect(self.results.update_item)
        _res = self.clipboard.paths_ready.connect(self.compress_files)
        _res = self.results.stop_requested.connect(self.stop_compression)
        # Ctrl+Q and logout call quit() without a window closeEvent, so also
        # hook the application-level signal to guarantee cleanup.
        _res = self.app.aboutToQuit.connect(self.flow.shutdown)

    # ------------------------------------------------------------------ UI
    def build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 18, 12, 18)
        header_layout.setSpacing(8)

        icon_color = self.palette().color(self.palette().ColorRole.WindowText)

        self.clear_button: QToolButton = self._make_icon_button(
            chevron_left_icon(icon_color),
            _("Return to main window"),
            self.clear_results,
        )

        self.results_title: QLabel = QLabel(_("Compression Results"))
        title_font = self.results_title.font()
        title_font.setPointSize(15)
        title_font.setBold(True)
        self.results_title.setFont(title_font)
        self.results_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.results_title.hide()
        header_layout.addWidget(self.clear_button)
        self.header_left_spacer: QWidget = QWidget()
        self.header_left_spacer.setFixedWidth(32)
        header_layout.addWidget(self.header_left_spacer)
        header_layout.addStretch(1)
        header_layout.addWidget(self.results_title)

        self.label_format: QLabel = QLabel(_("Output format:"))
        self.combo_format = self._build_option_combo(
            (_("Same as input"), *(_(spec.display) for spec in TARGET_SPECS)),
            _(
                "Output format. Convert every input to the selected format, or "
                + "keep each file's original format."
            ),
        )
        self.combo_compression = self._build_option_combo(
            (_("Lossy"), _("Lossless")),
            _(
                "Compression method. Lossy produces much smaller files with some "
                + "quality loss; lossless preserves the original pixels exactly."
            ),
        )
        self.combo_metadata = self._build_option_combo(
            (_("Keep metadata"), _("Remove metadata")),
            _(
                "Metadata retention. Keep or strip metadata such as EXIF, ICC "
                + "profiles and comments from the compressed images."
            ),
        )
        self.combo_attributes = self._build_option_combo(
            (_("Keep attributes"), _("Reset attributes")),
            _(
                "File attributes. Keep the original timestamps and permissions on "
                + "the output files, or reset them to the defaults."
            ),
        )

        self.combo_format.setCurrentIndex(self._target_index())
        self.combo_compression.setCurrentIndex(0 if self.settings.lossy else 1)
        self.combo_metadata.setCurrentIndex(0 if self.settings.metadata else 1)
        self.combo_attributes.setCurrentIndex(0 if self.settings.file_attributes else 1)

        _res = self.combo_format.currentIndexChanged.connect(self.on_format_changed)
        _res = self.combo_compression.currentIndexChanged.connect(self.on_compression_changed)
        _res = self.combo_metadata.currentIndexChanged.connect(self.on_metadata_changed)
        _res = self.combo_attributes.currentIndexChanged.connect(self.on_attributes_changed)

        header_layout.addWidget(self.label_format)
        header_layout.addWidget(self.combo_format)
        header_layout.addWidget(self.combo_compression)
        header_layout.addWidget(self.combo_metadata)
        header_layout.addWidget(self.combo_attributes)

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
        self.results: ResultsView = ResultsView()

        self._pages: dict[View, QWidget] = {
            View.HOME: self.home_page,
            View.LOADING: self.loading_page,
            View.RESULTS: self.results,
        }
        for page in self._pages.values():
            _res = self.stack.addWidget(page)

        root.addWidget(self.stack, 1)

    def _build_home_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, _V_SPACING, 40, _V_SPACING)
        layout.setSpacing(_V_SPACING)

        icon = QLabel()
        bg = self.palette().color(self.palette().ColorRole.Window)
        icon_color = QColor("#3a3a3a") if bg.lightness() < 128 else QColor("#d3d3d3")
        icon.setPixmap(download_icon(icon_color, 240).pixmap(240))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)

        drop_label = QLabel(_("Drop or paste files or directory here to compress."))
        drop_font = drop_label.font()
        drop_font.setPointSize(12)
        drop_font.setBold(True)
        drop_label.setFont(drop_font)
        drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(drop_label)

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

    # ----------------------------------------------------------------- actions
    def create_actions(self) -> None:
        self.act_select: QAction = QAction(_("Select Files"), self)
        self.act_select.setShortcut(QKeySequence("Ctrl+O"))
        _res = self.act_select.triggered.connect(self.on_select)

        self.act_paste: QAction = QAction(_("Paste from Clipboard"), self)
        self.act_paste.setShortcut(QKeySequence.StandardKey.Paste)
        _res = self.act_paste.triggered.connect(self.on_paste)

        self.act_select_folder: QAction = QAction(_("Select Directory"), self)
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
        self.results.set_busy(not enable)

    def stop_compression(self) -> None:
        self.flow.cancel()
        self.results.set_stop_enabled(False)

    def show_view(self, view: View) -> None:
        self.stack.setCurrentWidget(self._pages[view])
        is_results = view is View.RESULTS
        self.clear_button.setVisible(is_results)
        self.results_title.setVisible(is_results)
        show_options = not is_results
        self.label_format.setVisible(show_options)
        self.combo_format.setVisible(show_options)
        self.combo_compression.setVisible(show_options)
        self.combo_metadata.setVisible(show_options)
        self.combo_attributes.setVisible(show_options)
        self.settings_button.setVisible(show_options)
        self.header_left_spacer.setVisible(show_options)

    def clear_results(self) -> None:
        self.show_view(View.HOME)
        self.results.clear()
        self.flow.reset()
        self.clipboard.cleanup()

    # ------------------------------------------------------- compression flow
    def compress_files(self, paths: list[str]) -> None:
        if self.flow.active:
            _res = QMessageBox.information(
                self, _("Compression in progress"), _("Wait for the current compression to finish.")
            )
            return
        self.show_view(View.LOADING)
        self.flow.start(paths)

    def _show_items_ready(self) -> None:
        self.results.set_converting(is_converting(self.settings.target_format))
        self.show_view(View.RESULTS)

    def _on_analyze_no_files(self) -> None:
        self.show_view(View.HOME)
        _res = QMessageBox.information(self, _("No files found"), _("No files found"))

    def _on_analyze_output_error(self) -> None:
        self.show_view(View.HOME)
        _res = QMessageBox.warning(self, _("Error"), _("Can't create the output folder."))

    def _on_analyze_failed(self) -> None:
        self.show_view(View.HOME)
        _res = QMessageBox.warning(
            self, _("Error"), _("An unexpected error occurred while analyzing the images.")
        )

    def _update_summary(self) -> None:
        converting = is_converting(self.settings.target_format)
        self.results.set_summary(self.flow.summary.text(converting))

    # ----------------------------------------------------------------- file IO
    @override
    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        menu = QMenu(self)
        menu.addAction(self.act_paste)
        _res = menu.addSeparator()
        menu.addAction(self.act_select)
        menu.addAction(self.act_select_folder)
        _res = menu.exec(event.globalPos())
        event.accept()

    def on_paste(self) -> None:
        self.clipboard.request()

    def on_select(self) -> None:
        files, _filter = QFileDialog.getOpenFileNames(
            self, _("Select Images"), self._dialog_start_dir(), image_filter()
        )
        if not files:
            return
        self.compress_files(files)

    def on_select_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, _("Select Folder"), self._dialog_start_dir()
        )
        if not folder:
            return
        self.compress_files([folder])

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
        paths = urls_to_paths(event.mimeData())
        if not paths:
            return
        self.compress_files(paths)

    # ---------------------------------------------------------------- lifecycle
    @override
    def closeEvent(self, event: QCloseEvent) -> None:
        # Cancel any running batch and wait for its subprocesses/threads so we
        # don't orphan tools or leave .name.tmp/sidecar files behind.
        self.flow.shutdown()
        self.clipboard.cleanup()
        super().closeEvent(event)

    # ------------------------------------------------------------- active settings
    @staticmethod
    def _build_option_combo(items: tuple[str, ...], tooltip: str) -> QComboBox:
        combo = QComboBox()
        combo.addItems([_(item) for item in items])
        combo.setStyleSheet(combo_stylesheet())
        combo.setToolTip(f"<div style='width: 300px'>{html.escape(tooltip)}</div>")
        return combo

    def _target_index(self) -> int:
        target = self.settings.target_format
        for index, spec in enumerate(TARGET_SPECS):
            if spec.key == target:
                return index + 1
        return 0

    def on_format_changed(self, index: int) -> None:
        self.settings.target_format = Format.KEEP if index <= 0 else TARGET_SPECS[index - 1].key

    def on_compression_changed(self, index: int) -> None:
        self.settings.lossy = index == 0

    def on_metadata_changed(self, index: int) -> None:
        self.settings.metadata = index == 0

    def on_attributes_changed(self, index: int) -> None:
        self.settings.file_attributes = index == 0

    # ------------------------------------------------------------- dialogs
    def on_settings(self) -> None:
        if self.prefs_dialog is not None:
            _res = self.prefs_dialog.close()
        dialog = SettingsDialog(self.settings, self)
        # Without this the parented dialog would be kept alive by the window
        # until it is destroyed, accumulating one per open.
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        _res = dialog.settings_changed.connect(self._reconfigure_logging)
        # Clear on finished, not destroyed: finished fires synchronously inside
        # close() (before deleteLater), so the reference is never left dangling
        # and a reopen can't call close() on the already-deleted wrapper.
        _res = dialog.finished.connect(self._on_prefs_dialog_finished)
        self.prefs_dialog = dialog
        dialog.show()

    def _on_prefs_dialog_finished(self, _result: int) -> None:
        self.prefs_dialog = None

    def _reconfigure_logging(self) -> None:
        # Log level / max size / backups apply immediately rather than at the
        # next restart; pass the live settings so unsynced edits are honored.
        configure_logging(self.settings)
