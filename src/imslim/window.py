import os
import shutil
import tempfile
import time
from typing import override

from PySide6.QtCore import QDir, Qt, QTimer
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDropEvent,
    QKeySequence,
    QResizeEvent,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ._i18n import _
from .batch_flow import BatchFlow
from .clipboard_intake import ClipboardIntake, urls_to_paths
from .compare_view import CompareView
from .composition import AppContext
from .dialogs import AboutDialog, CompletionDialog, ProgressDialog
from .formats import MIME_TO_FORMAT, TARGET_EXTENSIONS, image_filter, is_converting
from .icons import imslim_icon
from .options_view import OptionsView
from .pipeline import remove_quietly
from .preview_task import CompressPreviewTask
from .queue_view import QueueView
from .result_item import ResultItem, ResultState
from .settings_manager import SAVE_OUTPUT_FOLDER, SettingsManager
from .theme import accent_color, splitter_stylesheet
from .workers import start_task

# A batch that finishes sooner than this never shows a progress dialog: it would
# just flash on screen and steal focus.
_PROGRESS_DELAY_MS = 1000
# A slider drag or a held spinner emits changes continuously; one preview per
# settle keeps the compare pane current without re-encoding on every step.
_PREVIEW_DELAY_MS = 300


class ImSlimWindow(QWidget):
    def __init__(self, app: QApplication, context: AppContext) -> None:
        super().__init__()
        self.app: QApplication = app
        self.settings: SettingsManager = context.settings
        self.flow: BatchFlow = context.flow
        self._pending_paths: list[str] = []
        self._batch_items: list[ResultItem] = []
        self._batch_started_at: float | None = None
        self._batch_output_folder: str = ""
        self._progress: ProgressDialog | None = None
        self.about_dialog: AboutDialog | None = None
        self._preview_token: int = 0
        self._preview_task: CompressPreviewTask | None = None
        self._preview_item: ResultItem | None = None
        self._preview_dir: str = ""
        self.clipboard: ClipboardIntake = ClipboardIntake(self.app.clipboard(), self)
        self.setWindowTitle("ImSlim")
        self.setWindowIcon(imslim_icon())
        self.setMinimumSize(1024, 640)
        if not self.restoreGeometry(self.settings.window_geometry):
            self.resize(1280, 800)
        self.setAcceptDrops(True)

        self.build_ui()
        self.create_actions()
        self._connect_flow()

        self._progress_timer: QTimer = QTimer(self)
        self._progress_timer.setSingleShot(True)
        self._progress_timer.setInterval(_PROGRESS_DELAY_MS)
        _res = self._progress_timer.timeout.connect(self._show_progress)

        self._preview_timer: QTimer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(_PREVIEW_DELAY_MS)
        _res = self._preview_timer.timeout.connect(self._start_preview)

        _res = self.app.aboutToQuit.connect(self.flow.shutdown)

    # ------------------------------------------------------------------ UI
    def build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.splitter: QSplitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(4)
        self.splitter.setStyleSheet(splitter_stylesheet())
        self.queue: QueueView = QueueView(self.settings)
        self.options: OptionsView = OptionsView(self.settings)
        self.compare: CompareView = CompareView()
        _res = self.splitter.addWidget(self.queue)
        _res = self.splitter.addWidget(self.options)
        _res = self.splitter.addWidget(self.compare)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 3)
        self.splitter.setSizes([320, 340, 660])
        if self.settings.layout_state:
            _res = self.splitter.restoreState(self.settings.layout_state)
        root.addWidget(self.splitter)

        self.drop_indicator: QWidget = QWidget(self)
        self.drop_indicator.setObjectName("dropIndicator")
        self.drop_indicator.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.drop_indicator.setStyleSheet(
            "QWidget#dropIndicator {"
            + f" border: 3px dashed {accent_color().name()};"
            + " background-color: transparent;"
            + " }"
        )
        self.drop_indicator.hide()

        _res = self.queue.add_files_requested.connect(self.on_select)
        _res = self.queue.add_directory_requested.connect(self.on_select_folder)
        _res = self.queue.selection_changed.connect(self._on_selection_changed)
        _res = self.options.process_requested.connect(self.start_batch)
        _res = self.options.about_requested.connect(self.on_about)
        _res = self.options.options_changed.connect(self._on_options_changed)
        _res = self.clipboard.paths_ready.connect(self.add_paths)

    def create_actions(self) -> None:
        self.act_select: QAction = QAction(_("Add Files"), self)
        self.act_select.setShortcut(QKeySequence("Ctrl+O"))
        _res = self.act_select.triggered.connect(self.on_select)

        self.act_select_folder: QAction = QAction(_("Add Directory"), self)
        _res = self.act_select_folder.triggered.connect(self.on_select_folder)

        self.act_paste: QAction = QAction(_("Paste from Clipboard"), self)
        self.act_paste.setShortcut(QKeySequence.StandardKey.Paste)
        _res = self.act_paste.triggered.connect(self.on_paste)

        self.act_quit: QAction = QAction(_("Quit"), self)
        self.act_quit.setShortcut(QKeySequence("Ctrl+Q"))
        _res = self.act_quit.triggered.connect(self.app.quit)

        for action in (
            self.act_select,
            self.act_select_folder,
            self.act_paste,
            self.act_quit,
        ):
            self.addAction(action)

        for sequence in ("Ctrl++", "Ctrl+="):
            zoom_in = QShortcut(QKeySequence(sequence), self)
            _res = zoom_in.activated.connect(self._zoom_in)
        zoom_out = QShortcut(QKeySequence("Ctrl+-"), self)
        _res = zoom_out.activated.connect(self._zoom_out)
        zoom_fit = QShortcut(QKeySequence("Ctrl+0"), self)
        _res = zoom_fit.activated.connect(self.compare.fit)

    # One shortcut per key: two widgets owning Ctrl++ makes Qt treat it as
    # ambiguous and neither fires. Keyboard zoom is for the comparison pane,
    # and only while it has focus.
    def _zoom_in(self) -> None:
        if self._compare_has_focus():
            self.compare.zoom_in()

    def _zoom_out(self) -> None:
        if self._compare_has_focus():
            self.compare.zoom_out()

    def _compare_has_focus(self) -> bool:
        focus = QApplication.focusWidget()
        return focus is not None and (focus is self.compare or self.compare.isAncestorOf(focus))

    def _connect_flow(self) -> None:
        _res = self.flow.item_added.connect(self._on_item_added)
        _res = self.flow.items_ready.connect(self._on_items_ready)
        _res = self.flow.batch_started.connect(self._on_batch_started)
        _res = self.flow.compression_enabled.connect(self._on_busy)
        _res = self.flow.summary_changed.connect(self._on_summary)
        _res = self.flow.result_updated.connect(self._on_result_updated)
        _res = self.flow.no_files.connect(self._on_analyze_no_files)
        _res = self.flow.output_folder_error.connect(self._on_analyze_output_error)
        _res = self.flow.analyze_failed.connect(self._on_analyze_failed)

    # ------------------------------------------------------------- signals
    def _on_item_added(self, result_item: ResultItem) -> None:
        self.queue.add_items([result_item])

    def _on_items_ready(self) -> None:
        if self.queue.selected_item() is None and self.queue.items:
            self.queue.select(self.queue.items[0])
        self._update_process_enabled()

    def _on_batch_started(self) -> None:
        self._batch_items = self.queue.items
        self._batch_started_at = time.monotonic()
        self._batch_output_folder = (
            self.settings.output_folder if self.settings.save_method == SAVE_OUTPUT_FOLDER else ""
        )
        self._cancel_preview()
        selected = self.queue.selected_item()
        if selected is not None:
            self._refresh_compare(selected)
        self._progress_timer.start()

    def _on_busy(self, enabled: bool) -> None:
        busy = not enabled
        self.queue.set_busy(busy)
        self.options.set_busy(busy)
        self._update_process_enabled()
        if busy:
            return
        self._progress_timer.stop()
        if self._progress is not None:
            _res = self._progress.close()
            self._progress = None
        self._finish_batch()
        self._drain_pending()

    def _on_summary(self) -> None:
        if self._progress is not None:
            self._progress.set_progress(self.flow.summary.done, self.flow.summary.total)

    def _on_result_updated(self, result_item: ResultItem) -> None:
        self.queue.update_item(result_item)
        if result_item is not self.queue.selected_item():
            return
        if result_item.state is ResultState.DONE:
            # The real output supersedes any preview still being encoded.
            self._cancel_preview()
        self._refresh_compare(result_item)

    def _on_selection_changed(self, result_item: object) -> None:
        self._cancel_preview()
        if isinstance(result_item, ResultItem):
            self.compare.show_original(result_item.filename, result_item.size, result_item.mtime)
            self._refresh_compare(result_item)
            self._schedule_preview(result_item)
        else:
            self._preview_item = None
            self.compare.clear()

    def _refresh_compare(self, result_item: ResultItem) -> None:
        # Both panes always hold an image: the real output when it exists, the
        # source otherwise (the comparison preview replaces it when ready).
        has_result = (
            result_item.state is ResultState.DONE
            and bool(result_item.new_filename)
            and os.path.exists(result_item.new_filename)
        )
        self.compare.show_processed(
            result_item.new_filename if has_result else result_item.filename
        )

    # --------------------------------------------------------------- previews
    def _on_options_changed(self) -> None:
        item = self.queue.selected_item()
        if item is not None:
            self._schedule_preview(item)

    def _schedule_preview(self, result_item: ResultItem) -> None:
        """Queue a preview of the selected file once option changes settle."""
        if self.flow.active or result_item.state is ResultState.DONE:
            return
        self._preview_item = result_item
        self._preview_timer.start()

    def _cancel_preview(self) -> None:
        self._preview_token += 1
        self._preview_timer.stop()
        if self._preview_task is not None:
            self._preview_task.cancel()
            self._preview_task = None

    def _start_preview(self) -> None:
        result_item = self._preview_item
        if result_item is None or self.flow.active or result_item.state is ResultState.DONE:
            return
        if self._preview_task is not None:
            self._preview_task.cancel()
        self._preview_token += 1
        token = self._preview_token
        if not self._preview_dir:
            self._preview_dir = tempfile.mkdtemp(prefix="imslim-preview-")
        extension = self._preview_extension(result_item)
        path = os.path.join(self._preview_dir, f"preview-{token}{extension}")
        task = CompressPreviewTask(token, self.flow, result_item, path)
        _res = task.ready.connect(self._on_preview_ready)
        self._preview_task = task
        start_task(task)

    def _preview_extension(self, result_item: ResultItem) -> str:
        target = self.settings.target_format
        if is_converting(target):
            return TARGET_EXTENSIONS[target]
        spec = MIME_TO_FORMAT.get(result_item.mime_type)
        return spec.output_extension if spec is not None else ""

    def _on_preview_ready(self, token: int, result: object) -> None:
        if token != self._preview_token:
            return
        self._preview_task = None
        item = self._preview_item
        if (
            item is None
            or item.state is ResultState.DONE
            or not isinstance(result, ResultItem)
            or result.state is not ResultState.DONE
        ):
            return
        self.compare.show_processed(result.new_filename)
        # Drop the previous preview file: the pane already holds its pixels.
        for name in os.listdir(self._preview_dir):
            if name != os.path.basename(result.new_filename):
                remove_quietly(os.path.join(self._preview_dir, name))

    def _show_progress(self) -> None:
        if not self.flow.active:
            return
        dialog = ProgressDialog(_("Processing"), self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        _res = dialog.cancel_requested.connect(self.stop_compression)
        self._progress = dialog
        dialog.show()

    def _finish_batch(self) -> None:
        if self._batch_started_at is None:
            return
        elapsed = time.monotonic() - self._batch_started_at
        self._batch_started_at = None
        dialog = CompletionDialog(
            self.flow.summary,
            self._batch_items,
            elapsed,
            self._batch_output_folder,
            self,
        )
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.show()

    def _update_process_enabled(self) -> None:
        self.options.set_process_enabled(not self.flow.active and self.queue.has_processable_items)

    # ---------------------------------------------------------------- actions
    def add_paths(self, paths: list[str]) -> None:
        if not paths:
            return
        if self.flow.active:
            # "Open with" can arrive while a batch runs; queue it for the next.
            self._pending_paths.extend(paths)
            return
        self.clipboard.cleanup_unless_used(paths)
        self.flow.analyze(paths)

    def _drain_pending(self) -> None:
        if self.flow.active or not self._pending_paths:
            return
        paths = self._pending_paths
        self._pending_paths = []
        self.add_paths(paths)

    def start_batch(self) -> None:
        if self.flow.active:
            return
        items = self.queue.items
        if not items:
            return
        self.flow.start_batch(items)

    def stop_compression(self) -> None:
        self.flow.cancel()
        if self._progress is not None:
            _res = self._progress.close()
            self._progress = None

    def on_paste(self) -> None:
        self.clipboard.request()

    def on_select(self) -> None:
        files, _filter = QFileDialog.getOpenFileNames(
            self, _("Select Images"), self._dialog_start_dir(), image_filter()
        )
        if files:
            self.add_paths(files)

    def on_select_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, _("Select Folder"), self._dialog_start_dir()
        )
        if folder:
            self.add_paths([folder])

    def _dialog_start_dir(self) -> str:
        start = self.settings.default_open_dialog_directory
        if start and os.path.isdir(start):
            return start
        return QDir.homePath()

    # ------------------------------------------------------------------ DnD
    @override
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls() and not self.flow.active:
            self._show_drop_indicator()
            event.acceptProposedAction()

    def _show_drop_indicator(self) -> None:
        self.drop_indicator.setGeometry(self.rect())
        self.drop_indicator.raise_()
        self.drop_indicator.show()

    @override
    def resizeEvent(self, event: QResizeEvent) -> None:
        if self.drop_indicator.isVisible():
            self.drop_indicator.setGeometry(self.rect())
        super().resizeEvent(event)

    @override
    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self.drop_indicator.hide()
        super().dragLeaveEvent(event)

    @override
    def dropEvent(self, event: QDropEvent) -> None:
        self.drop_indicator.hide()
        paths = urls_to_paths(event.mimeData())
        if paths:
            self.add_paths(paths)

    # ---------------------------------------------------------------- dialogs
    def on_about(self) -> None:
        if self.about_dialog is not None:
            _res = self.about_dialog.close()
        dialog = AboutDialog(self.settings, self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        _res = dialog.finished.connect(self._on_about_dialog_finished)
        self.about_dialog = dialog
        dialog.show()

    def _on_about_dialog_finished(self, _result: int) -> None:
        self.about_dialog = None

    def _on_analyze_no_files(self) -> None:
        _res = QMessageBox.information(self, _("No files found"), _("No files found"))

    def _on_analyze_output_error(self) -> None:
        _res = QMessageBox.warning(self, _("Error"), _("Can't create the output folder."))

    def _on_analyze_failed(self) -> None:
        _res = QMessageBox.warning(
            self, _("Error"), _("An unexpected error occurred while analyzing the images.")
        )

    # --------------------------------------------------------------- lifecycle
    @override
    def closeEvent(self, event: QCloseEvent) -> None:
        self._cancel_preview()
        if self._preview_dir:
            shutil.rmtree(self._preview_dir, ignore_errors=True)
        self.flow.shutdown()
        self.clipboard.cleanup()
        self.settings.window_geometry = bytes(self.saveGeometry().data())
        self.settings.layout_state = bytes(self.splitter.saveState().data())
        super().closeEvent(event)
