import logging
import os
import threading
from typing import override

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from .batch_options import BatchOptions
from .image_utils import get_image_paths_from_folder
from .result_item import ResultItem
from .result_item_manager import ResultItemManager, is_generated_output
from .system_info import tool_version_pairs

logger = logging.getLogger(__name__)

# Shared pool for one-shot tasks (version probe etc.). Thumbnails keep their own
# pool so their thread budget stays independent.
_TASK_POOL = QThreadPool()
_TASK_POOL.setMaxThreadCount(max(2, (os.cpu_count() or 2) // 2))

# Holds every started task until it finishes, so a running QRunnable is never
# garbage-collected (and its C++ object destroyed) mid-run; _release drops it on
# the main thread after run() returns.
_ACTIVE_TASKS: set[Task] = set()


# Both __init__s are called explicitly in Task.__init__; the multiple-inheritance
# warning is a false positive for the standard QObject+QRunnable combo.
class Task(QObject, QRunnable):  # pyright: ignore[reportUnsafeMultipleInheritance]
    """One-shot background job run on a QThreadPool that reports via signals."""

    finished: Signal = Signal()

    def __init__(self) -> None:
        QObject.__init__(self)
        QRunnable.__init__(self)
        self.setAutoDelete(False)
        _ACTIVE_TASKS.add(self)
        _res = self.finished.connect(self._release)

    def _release(self) -> None:
        _ACTIVE_TASKS.discard(self)
        self.deleteLater()

    def abandon(self) -> None:
        """Drop a task that never ran (still queued) and schedule deletion."""
        _ACTIVE_TASKS.discard(self)
        self.deleteLater()


def start_task(task: Task) -> None:
    _TASK_POOL.start(task)


class VersionProbeTask(Task):
    """Queries bundled compression tool versions off the UI thread."""

    versions_ready: Signal = Signal(list)

    @override
    def run(self) -> None:
        try:
            self.versions_ready.emit(tool_version_pairs())
        finally:
            self.finished.emit()


class AnalyzeTask(Task):
    """Collects files and builds ResultItems off the UI thread.

    Building each item stats the file and sniffs its MIME type, which for a
    large directory would otherwise freeze the UI during "Analyzing Images".
    """

    items_ready: Signal = Signal(list)
    no_files: Signal = Signal()
    output_folder_error: Signal = Signal()
    analysis_failed: Signal = Signal(str)

    def __init__(self, paths: list[str], options: BatchOptions) -> None:
        super().__init__()
        self._paths: list[str] = paths
        self._options: BatchOptions = options
        self._cancel_event: threading.Event = threading.Event()
        # The ResultItems are parentless QObjects built here; the queued
        # items_ready delivery runs on the UI thread after run() returns, so
        # keep them referenced until the consumer has them, otherwise Python GC
        # destroys the C++ objects and delivery segfaults.
        self._result_items: list[ResultItem] = []

    def cancel(self) -> None:
        self._cancel_event.set()

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    @override
    def run(self) -> None:
        try:
            self._analyze()
        except Exception as err:
            logger.exception("Analyze failed unexpectedly")
            self.analysis_failed.emit(str(err))
        finally:
            self.finished.emit()

    def _analyze(self) -> None:
        final_files: list[str] = []
        seen: set[str] = set()
        for path in self._paths:
            if self.is_cancelled():
                return
            if os.path.isdir(path):
                candidates = get_image_paths_from_folder(
                    path, self._options.recursive, self.is_cancelled
                )
            else:
                candidates = [path]
            for candidate in candidates:
                if is_generated_output(candidate):
                    continue
                # A folder and a file inside it (or overlapping selections)
                # name the same file; realpath collapses them to one entry.
                key = os.path.normcase(os.path.realpath(candidate))
                if key in seen:
                    continue
                seen.add(key)
                final_files.append(candidate)

        if self.is_cancelled():
            return
        if not final_files:
            self.no_files.emit()
            return

        manager = ResultItemManager(self._options)
        if not manager.begin_batch():
            self.output_folder_error.emit()
            return

        self._result_items = []
        for path in final_files:
            if self.is_cancelled():
                return
            self._result_items.append(manager.build(path))
        self.items_ready.emit(self._result_items)
