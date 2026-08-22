import os
from typing import override

from PySide6.QtCore import QObject, QThread, Signal

from .image_utils import get_image_paths_from_folder
from .result_item import ResultItem
from .result_item_manager import ResultItemManager
from .system_info import tool_version_pairs


class Bridge(QObject):
    """Cross-thread signal bridge from compression workers to the UI thread."""

    result_updated: Signal = Signal(ResultItem)
    compression_enabled: Signal = Signal(bool)


class VersionProbeWorker(QThread):
    """Queries bundled compression tool versions off the UI thread."""

    versions_ready: Signal = Signal(list)

    @override
    def run(self) -> None:
        self.versions_ready.emit(tool_version_pairs())


class BuildSettingsSnapshot:
    """Plain values ResultItemManager needs, captured on the UI thread.

    QSettings isn't thread-safe, so the snapshot replaces the live
    SettingsManager inside the analyze worker.
    """

    def __init__(self, save_method: int, output_folder: str) -> None:
        self.save_method: int = save_method
        self.output_folder: str = output_folder


class AnalyzeWorker(QThread):
    """Collects files and builds ResultItems off the UI thread.

    Building each item stats the file and sniffs its MIME type, which for a
    large directory would otherwise freeze the UI during "Analyzing Images".
    """

    items_ready: Signal = Signal(list)
    no_files: Signal = Signal()
    output_folder_error: Signal = Signal()

    def __init__(self, paths: list[str], recursive: bool, settings: BuildSettingsSnapshot) -> None:
        super().__init__()
        self._paths: list[str] = paths
        self._recursive: bool = recursive
        self._settings: BuildSettingsSnapshot = settings
        # The ResultItems are parentless QObjects built on this thread; the
        # queued items_ready delivery runs on the UI thread *after* run()
        # returns, so keep them referenced here until the consumer has them,
        # otherwise Python GC destroys the C++ objects and delivery segfaults.
        self._result_items: list[ResultItem] = []

    @override
    def run(self) -> None:
        final_files: list[str] = []
        for path in self._paths:
            if os.path.isdir(path):
                final_files.extend(get_image_paths_from_folder(path, self._recursive))
            else:
                final_files.append(path)

        if not final_files:
            self.no_files.emit()
            return

        manager = ResultItemManager(self._settings)
        if not manager.begin_batch():
            self.output_folder_error.emit()
            return

        self._result_items = [manager.build(path) for path in final_files]
        self.items_ready.emit(self._result_items)
