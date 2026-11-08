"""Compress the selected file into a temporary preview, off the UI thread.

The comparison pane shows what Process would produce for the current settings
long before (or without) the real batch writing anything to the destination.
"""

import logging
from typing import override

from PySide6.QtCore import Signal

from .batch_flow import BatchFlow
from .command_runner import CompressionContext
from .result_item import ResultItem
from .workers import Task

logger = logging.getLogger(__name__)


class CompressPreviewTask(Task):
    """Runs the batch compressor on one file into a caller-provided temp path."""

    ready: Signal = Signal(int, object)  # token, ResultItem | None

    def __init__(
        self,
        token: int,
        flow: BatchFlow,
        result_item: ResultItem,
        output_path: str,
    ) -> None:
        super().__init__()
        self._token: int = token
        self._flow: BatchFlow = flow
        self._result_item: ResultItem = result_item
        self._output_path: str = output_path
        self._context: CompressionContext = CompressionContext()

    def cancel(self) -> None:
        self._context.cancel()

    @override
    def run(self) -> None:
        try:
            result: ResultItem | None = self._flow.preview(
                self._result_item, self._output_path, self._context
            )
        except Exception:
            logger.exception("Preview compression failed unexpectedly")
            result = None
        try:
            self.ready.emit(self._token, result)
        finally:
            self.finished.emit()
