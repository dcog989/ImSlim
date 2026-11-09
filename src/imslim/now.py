"""ImSlimNow: process the files given on the command line without the main window."""

import time

from PySide6.QtCore import QEventLoop, QObject, QTimer
from PySide6.QtWidgets import QMessageBox

from ._i18n import _
from .batch_flow import BatchFlow
from .batch_summary import BatchSummary
from .dialogs import CompletionDialog, ProgressDialog
from .result_item import ResultItem
from .settings_manager import SAVE_OUTPUT_FOLDER, SettingsManager

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2

# Same debounce as the GUI: a tiny batch should not flash a dialog.
_PROGRESS_DELAY_MS = 1000


def exit_code(summary: BatchSummary) -> int:
    """0 only when every file was compressed or skipped."""
    unprocessed = summary.total - (summary.compressed + summary.skipped + summary.failed)
    return EXIT_FAILED if summary.failed or unprocessed > 0 else EXIT_OK


class NowRunner(QObject):
    """Runs one analyze→compress batch and reports the outcome through dialogs."""

    def __init__(self, settings: SettingsManager, flow: BatchFlow) -> None:
        super().__init__()
        self._flow: BatchFlow = flow
        self._settings: SettingsManager = settings
        self._loop: QEventLoop = QEventLoop()
        self._code: int = EXIT_OK
        self._items: list[ResultItem] = []
        self._batch_items: list[ResultItem] = []
        self._batch_started: float | None = None
        self._progress: ProgressDialog | None = None
        self._finished: bool = False
        self._timer: QTimer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(_PROGRESS_DELAY_MS)
        _res = self._timer.timeout.connect(self._show_progress)
        _res = self._flow.items_added.connect(self._on_items_added)
        _res = self._flow.items_ready.connect(self._on_items_ready)
        _res = self._flow.batch_started.connect(self._on_batch_started)
        _res = self._flow.compression_enabled.connect(self._on_busy)
        _res = self._flow.summary_changed.connect(self._on_summary)
        _res = self._flow.no_files.connect(self._on_no_files)
        _res = self._flow.output_folder_error.connect(self._on_output_folder_error)
        _res = self._flow.analyze_failed.connect(self._on_analyze_failed)

    def run(self, paths: list[str]) -> int:
        self._timer.start()
        self._flow.analyze(paths)
        _res = self._loop.exec()
        self._flow.shutdown()
        return self._code

    # ---------------------------------------------------------------- signals
    def _on_items_added(self, result_items: list[ResultItem]) -> None:
        self._items.extend(result_items)

    def _on_items_ready(self) -> None:
        if self._finished:
            return
        self._batch_items = list(self._items)
        # Failed analysis items are passed along: start_batch counts them as
        # failures, so the confirmation window still explains what went wrong.
        self._flow.start_batch(self._batch_items)

    def _on_batch_started(self) -> None:
        self._batch_started = time.monotonic()

    def _on_busy(self, enabled: bool) -> None:
        if not enabled or self._finished:
            return
        self._close_progress()
        if self._batch_started is None:
            self._quit()
            return
        self._code = exit_code(self._flow.summary)
        dialog = CompletionDialog(
            self._flow.summary,
            self._batch_items,
            time.monotonic() - self._batch_started,
            self._settings.output_folder
            if self._settings.save_method == SAVE_OUTPUT_FOLDER
            else "",
        )
        self._batch_items = []
        _res = dialog.exec()
        self._quit()

    def _on_summary(self) -> None:
        if self._progress is not None:
            self._progress.set_progress(self._flow.summary.done, self._flow.summary.total)

    def _on_no_files(self) -> None:
        self._code = EXIT_USAGE
        _res = QMessageBox.information(
            None, _("No files found"), _("No image files were found in the given paths.")
        )
        self._quit()

    def _on_output_folder_error(self) -> None:
        self._code = EXIT_USAGE
        _res = QMessageBox.warning(
            None,
            _("Error"),
            _("Can't use the output folder. Choose a folder or another destination."),
        )
        self._quit()

    def _on_analyze_failed(self) -> None:
        self._code = EXIT_USAGE
        _res = QMessageBox.warning(
            None, _("Error"), _("An unexpected error occurred while analyzing the images.")
        )
        self._quit()

    # ------------------------------------------------------------------ dialogs
    def _show_progress(self) -> None:
        if self._finished or self._progress is not None:
            return
        dialog = ProgressDialog(_("Processing"))
        _res = dialog.cancel_requested.connect(self._cancel)
        self._progress = dialog
        dialog.show()

    def _cancel(self) -> None:
        self._flow.cancel()
        self._close_progress()

    def _close_progress(self) -> None:
        self._timer.stop()
        if self._progress is not None:
            self._progress.finish()
            self._progress = None

    def _quit(self) -> None:
        if self._finished:
            return
        self._finished = True
        self._close_progress()
        self._loop.quit()
