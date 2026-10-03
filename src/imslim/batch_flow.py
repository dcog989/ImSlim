import logging

from PySide6.QtCore import QObject, QThreadPool, Signal

from .batch_options import BatchOptions
from .batch_summary import BatchSummary
from .compression_manager import CompressionManager
from .result_item import ResultItem, ResultState
from .settings_manager import SettingsManager
from .workers import AnalyzeTask

logger = logging.getLogger(__name__)

# Bound on how long shutdown waits for the analyze thread to notice cancellation
# between files; folder walks check it per entry.
_ANALYZE_SHUTDOWN_TIMEOUT_MS = 5000


class BatchFlow(QObject):
    """Orchestrates one analyze→compress→update batch.

    Owns the compression manager, the analyze worker, and the batch summary;
    emits signals the window renders. All state mutations happen on the UI
    thread: worker results arrive via queued signal connections.
    """

    item_added: Signal = Signal(ResultItem)
    items_ready: Signal = Signal()
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
        self._shutting_down: bool = False
        self._analyze_worker: AnalyzeTask | None = None
        # Dedicated single-thread pool so shutdown can wait for exactly this
        # analyze run without waiting on unrelated pooled tasks.
        self._analyze_pool: QThreadPool = QThreadPool()
        self._analyze_pool.setMaxThreadCount(1)
        self._options: BatchOptions | None = None
        _res = self.result_updated.connect(self._on_result_updated)
        # The manager emits this from its own thread; the queued connection
        # delivers _on_compression_enabled on the UI thread.
        _res = self.compression_enabled.connect(self._on_compression_enabled)

    @property
    def active(self) -> bool:
        return self._active

    def start(self, paths: list[str]) -> None:
        if self._shutting_down:
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
        self._analyze_pool.start(worker)

    def cancel(self) -> None:
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
        self.summary.reset()
        self.summary_changed.emit()

    def _on_items_ready(self, result_items: list[ResultItem]) -> None:
        if self._shutting_down:
            return
        options = self._options
        if options is None:
            raise RuntimeError("items arrived before a batch was started")
        for result_item in result_items:
            self.summary.record_added()
            self.item_added.emit(result_item)
            if result_item.state is ResultState.ERROR:
                self.result_updated.emit(result_item)

        result_items = [item for item in result_items if item.state is not ResultState.ERROR]

        self.items_ready.emit()
        self.compression_enabled.emit(False)

        self._compressing = True
        self._manager.compress(
            result_items,
            options,
            self.result_updated.emit,
            self.compression_enabled.emit,
        )

    def _on_compression_enabled(self, enabled: bool) -> None:
        self._active = not enabled
        if enabled:
            self._compressing = False

    def _on_result_updated(self, result_item: ResultItem) -> None:
        # RUNNING is an interim UI refresh, not a terminal outcome to tally.
        if result_item.state is ResultState.RUNNING:
            return
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
        self.summary_changed.emit()

    def _on_no_files(self) -> None:
        self._active = False
        self.no_files.emit()

    def _on_output_folder_error(self) -> None:
        self._active = False
        self.output_folder_error.emit()

    def _on_analyze_failed(self) -> None:
        self._active = False
        self.analyze_failed.emit()

    def _on_analyze_finished(self) -> None:
        if not self._compressing:
            self._active = False
        # Task deletes itself once finished; just drop our reference.
        self._analyze_worker = None
