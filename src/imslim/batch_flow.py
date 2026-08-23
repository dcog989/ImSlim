from PySide6.QtCore import QObject, Signal

from .batch_summary import BatchSummary
from .compression_manager import CompressionManager
from .result_item import ResultItem
from .settings_manager import SettingsManager
from .workers import AnalyzeWorker, BuildSettingsSnapshot


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
    result_updated: Signal = Signal(ResultItem)

    def __init__(self, settings: SettingsManager, manager: CompressionManager) -> None:
        super().__init__()
        self._settings: SettingsManager = settings
        self._manager: CompressionManager = manager
        self.summary: BatchSummary = BatchSummary()
        self._active: bool = False
        self._analyze_worker: AnalyzeWorker | None = None
        _res = self.result_updated.connect(self._on_result_updated)
        # The manager emits this from its own thread; the queued connection
        # delivers _on_compression_enabled on the UI thread.
        _res = self.compression_enabled.connect(self._on_compression_enabled)

    @property
    def active(self) -> bool:
        return self._active

    def start(self, paths: list[str]) -> None:
        self._active = True
        snapshot = BuildSettingsSnapshot(
            self._settings.save_method,
            self._settings.output_folder,
        )
        worker = AnalyzeWorker(paths, self._settings.recursive, snapshot)
        self._analyze_worker = worker
        _res = worker.items_ready.connect(self._on_items_ready)
        _res = worker.no_files.connect(self._on_no_files)
        _res = worker.output_folder_error.connect(self._on_output_folder_error)
        _res = worker.finished.connect(self._on_analyze_finished)
        worker.start()

    def cancel(self) -> None:
        self._manager.cancel()

    def reset(self) -> None:
        self.summary.reset()
        self.summary_changed.emit()

    def _on_items_ready(self, result_items: list[ResultItem]) -> None:
        for result_item in result_items:
            self.summary.record_added()
            self.item_added.emit(result_item)
            if result_item.error:
                self.result_updated.emit(result_item)

        result_items = [item for item in result_items if not item.error]

        self.items_ready.emit()
        self.compression_enabled.emit(False)

        for result_item in result_items:
            result_item.running = True
            result_item.updated.emit()

        self._manager.compress(
            result_items,
            self.result_updated.emit,
            self.compression_enabled.emit,
        )

    def _on_compression_enabled(self, enabled: bool) -> None:
        self._active = not enabled

    def _on_result_updated(self, result_item: ResultItem) -> None:
        if result_item.cancelled:
            self.summary.record_done()
        elif result_item.error:
            self.summary.record_failed()
            self.summary.record_done()
        elif result_item.skipped:
            self.summary.record_skipped()
            self.summary.record_done()
        else:
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

    def _on_analyze_finished(self) -> None:
        worker = self._analyze_worker
        self._analyze_worker = None
        if worker is not None:
            worker.deleteLater()
