import logging

from PySide6.QtCore import QObject, QThreadPool, QTimer, Signal

from .batch_options import BatchOptions
from .batch_summary import BatchSummary
from .command_runner import CompressionContext
from .compression_manager import CompressionManager
from .formats import is_converting
from .result_item import ResultItem, ResultState
from .result_item_manager import ResultItemManager
from .settings_manager import SettingsManager
from .workers import AnalyzeTask

logger = logging.getLogger(__name__)

# Bound on how long shutdown waits for the analyze thread to notice cancellation
# between files; folder walks check it per entry.
_ANALYZE_SHUTDOWN_TIMEOUT_MS = 5000
# The summary line is a few counters; repainting it per finished image is wasted
# layout work in a large batch.
_SUMMARY_INTERVAL_MS = 100


class BatchFlow(QObject):
    """Orchestrates analysis and the analyze→compress→update batch.

    Analysis and compression are separate steps: the queue collects files
    first, and Process starts a batch over them. All state mutations happen on
    the UI thread; worker results arrive via queued signal connections.
    """

    item_added: Signal = Signal(ResultItem)
    items_ready: Signal = Signal()
    batch_started: Signal = Signal()
    compression_enabled: Signal = Signal(bool)
    summary_changed: Signal = Signal()
    no_files: Signal = Signal()
    output_folder_error: Signal = Signal()
    analyze_failed: Signal = Signal()
    result_updated: Signal = Signal(ResultItem)

    def __init__(self, settings: SettingsManager, manager: CompressionManager) -> None:
        super().__init__()
        self._settings: SettingsManager = settings
        self._manager: CompressionManager = manager
        self.summary: BatchSummary = BatchSummary()
        self._active: bool = False
        self._compressing: bool = False
        self._batch_pending: bool = False
        self._shutting_down: bool = False
        self._analyze_worker: AnalyzeTask | None = None
        # Dedicated single-thread pool so shutdown can wait for exactly this
        # analyze run without waiting on unrelated pooled tasks.
        self._analyze_pool: QThreadPool = QThreadPool()
        self._analyze_pool.setMaxThreadCount(1)
        self._options: BatchOptions | None = None
        # Items already tallied for the running batch. A RUNNING update can be
        # delivered after the worker already moved the item to DONE (the signals
        # are queued), so the state read here is not a reliable "first terminal
        # update" marker; the item identity is.
        self._counted: set[ResultItem] = set()
        self._summary_timer: QTimer = QTimer(self)
        self._summary_timer.setSingleShot(True)
        self._summary_timer.setInterval(_SUMMARY_INTERVAL_MS)
        _res = self._summary_timer.timeout.connect(self.summary_changed.emit)
        _res = self.result_updated.connect(self._on_result_updated)
        # The manager emits this from its own thread; the queued connection
        # delivers _on_compression_enabled on the UI thread.
        _res = self.compression_enabled.connect(self._on_compression_enabled)

    @property
    def active(self) -> bool:
        return self._active

    @property
    def converting(self) -> bool:
        """Whether this batch converts every input to the target format.

        Read from the batch's settings snapshot rather than live settings, so a
        settings edit mid-batch cannot change what the results page describes.
        """
        return self._options is not None and is_converting(self._options.target_format)

    def analyze(self, paths: list[str]) -> None:
        """Collect and inspect `paths`; the caller decides when to process them."""
        if self._shutting_down or self._active:
            return
        self._active = True
        self._options = BatchOptions.from_settings(self._settings)
        worker = AnalyzeTask(paths, self._options)
        self._analyze_worker = worker
        _res = worker.items_ready.connect(self._on_items_ready)
        _res = worker.no_files.connect(self._on_no_files)
        _res = worker.output_folder_error.connect(self._on_output_folder_error)
        _res = worker.analysis_failed.connect(self._on_analyze_failed)
        _res = worker.finished.connect(self._on_analyze_finished)
        self.compression_enabled.emit(False)
        self._analyze_pool.start(worker)

    def start_batch(self, result_items: list[ResultItem]) -> None:
        """Prepare `result_items` with a fresh options snapshot and compress them."""
        if self._shutting_down or self._active or not result_items:
            return
        self._batch_pending = True
        options = BatchOptions.from_settings(self._settings)
        manager = ResultItemManager(options)
        if not manager.begin_batch():
            self.output_folder_error.emit()
            return
        self._options = options
        self._counted.clear()
        self.summary.reset()
        to_process: list[ResultItem] = []
        for result_item in result_items:
            manager.prepare(result_item)
            self.summary.record_added()
            if result_item.state is ResultState.ERROR:
                # Failed analysis (missing or unsupported): already final.
                self.result_updated.emit(result_item)
            else:
                to_process.append(result_item)
        self._active = True
        self._compressing = True
        self.batch_started.emit()
        self.compression_enabled.emit(False)
        if not to_process:
            self._finish_batch()
            return
        self._manager.compress(
            to_process,
            options,
            self.result_updated.emit,
            self.compression_enabled.emit,
        )

    def preview(
        self,
        result_item: ResultItem,
        output_path: str,
        context: CompressionContext,
    ) -> ResultItem:
        """Compress `result_item` into `output_path` with the current settings."""
        options = BatchOptions.from_settings(self._settings)
        return self._manager.preview(result_item, options, output_path, context)

    def cancel(self) -> None:
        worker = self._analyze_worker
        if worker is not None:
            worker.cancel()
        self._manager.cancel()

    def shutdown(self) -> None:
        """Stop the running batch and wait for its threads to unwind.

        Idempotent: both the window's closeEvent and QApplication.aboutToQuit
        may reach this during a normal quit.
        """
        if self._shutting_down:
            return
        self._shutting_down = True
        worker = self._analyze_worker
        if worker is not None:
            worker.cancel()
            if not self._analyze_pool.waitForDone(_ANALYZE_SHUTDOWN_TIMEOUT_MS):
                logger.warning("Analyze worker still running after shutdown timeout")
            self._analyze_worker = None
        self._manager.shutdown()

    def reset(self) -> None:
        self._summary_timer.stop()
        self.summary.reset()
        self.summary_changed.emit()

    def _finish_batch(self) -> None:
        self._compressing = False
        self._active = False
        self.compression_enabled.emit(True)

    def _on_items_ready(self, result_items: list[ResultItem]) -> None:
        if self._shutting_down:
            return
        self._active = False
        self._batch_pending = False
        for result_item in result_items:
            self.item_added.emit(result_item)
        self.items_ready.emit()
        # A listener may have started a batch synchronously from items_ready;
        # only re-enable the UI when the queue is left waiting for Process.
        if not self._batch_pending and not self._compressing:
            self._active = False
            self.compression_enabled.emit(True)

    def _on_compression_enabled(self, enabled: bool) -> None:
        self._active = not enabled
        if enabled:
            self._compressing = False

    def _on_result_updated(self, result_item: ResultItem) -> None:
        # RUNNING is an interim UI refresh, not a terminal outcome to tally.
        if result_item.state is ResultState.RUNNING:
            return
        if result_item in self._counted:
            return
        self._counted.add(result_item)
        match result_item.state:
            case ResultState.ERROR:
                self.summary.record_failed()
            case ResultState.SKIPPED:
                self.summary.record_skipped()
            case ResultState.CANCELLED:
                pass
            case _:
                saved_bytes = (
                    result_item.size - result_item.new_size
                    if result_item.size > result_item.new_size
                    else 0
                )
                self.summary.record_compressed(saved_bytes)
        self.summary.record_done()
        if not self._summary_timer.isActive():
            self._summary_timer.start()

    def _on_no_files(self) -> None:
        self._active = False
        self.no_files.emit()
        self.compression_enabled.emit(True)

    def _on_output_folder_error(self) -> None:
        self._active = False
        self.output_folder_error.emit()
        self.compression_enabled.emit(True)

    def _on_analyze_failed(self) -> None:
        self._active = False
        self.analyze_failed.emit()
        self.compression_enabled.emit(True)

    def _on_analyze_finished(self) -> None:
        # Task deletes itself once finished; just drop our reference.
        self._analyze_worker = None
        # Cancelled analysis emits nothing else, so it is the only path that
        # still has to re-enable the UI here.
        if self._active and not self._compressing:
            self._active = False
            self.compression_enabled.emit(True)
