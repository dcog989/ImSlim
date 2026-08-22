import os
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from ._i18n import _

# MIME type -> (compressor type, output extension). Formats that are re-encoded
# to a different format on output (BMP/TIFF -> WebP) carry a different extension
# here; for the rest the source extension is kept. Single source of truth shared
# with result_item_manager (ALLOWED_MIME_TYPES / OUTPUT_EXTENSIONS).
MIME_TO_COMPRESSOR = {
    "image/jpeg": ("jpeg", None),
    "image/png": ("png", None),
    "image/webp": ("webp", None),
    "image/avif": ("avif", None),
    "image/jxl": ("jxl", None),
    "image/gif": ("gif", None),
    "image/svg+xml": ("svg", None),
    "image/bmp": ("webp", ".webp"),
    "image/tiff": ("webp", ".webp"),
}

ALLOWED_MIME_TYPES = frozenset(MIME_TO_COMPRESSOR)

OUTPUT_EXTENSIONS = {
    mime: extension for mime, (_compress_type, extension) in MIME_TO_COMPRESSOR.items() if extension
}

_KILL_GRACE_SECONDS = 0.5


class CompressionContext:
    """Shared cancellation state for one compression batch."""

    def __init__(self) -> None:
        self._cancel_event = threading.Event()
        self._processes: list[subprocess.Popen] = []
        self._lock = threading.Lock()

    @property
    def cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def register_process(self, process: subprocess.Popen) -> None:
        with self._lock:
            self._processes.append(process)

    def unregister_process(self, process: subprocess.Popen) -> None:
        with self._lock:
            if process in self._processes:
                self._processes.remove(process)

    def cancel(self) -> None:
        if self._cancel_event.is_set():
            return
        self._cancel_event.set()
        with self._lock:
            processes = list(self._processes)
        deadline = time.monotonic() + _KILL_GRACE_SECONDS
        for process in processes:
            try:
                process.terminate()
            except OSError:
                pass
        for process in processes:
            try:
                remaining = max(0.0, deadline - time.monotonic())
                process.wait(timeout=remaining)
            except subprocess.TimeoutExpired, OSError:
                try:
                    process.kill()
                except OSError:
                    pass


class CompressionManager:
    def __init__(self, settings_manager):
        self.settings = settings_manager
        self.compressors = {}
        self._context: CompressionContext | None = None

    def mime_type_to_compressor_type(self, mime_type: str) -> str | None:
        return MIME_TO_COMPRESSOR.get(mime_type, (None,))[0]

    def register_compressor(self, ConcreteCompressor):
        file_type = ConcreteCompressor.get_file_type()
        if file_type not in self.compressors:
            self.compressors[file_type] = ConcreteCompressor(self.settings)

    def compress(self, result_items, c_update_result_item, c_enable_compression):
        context = CompressionContext()
        self._context = context
        threading.Thread(
            target=self._compress,
            args=(result_items, c_update_result_item, c_enable_compression, context),
            daemon=True,
        ).start()

    def cancel(self):
        if self._context is not None:
            self._context.cancel()

    def _compress(self, result_items, c_update_result_item, c_enable_compression, context):
        max_workers = max(1, (os.cpu_count() or 1) // 2)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            break_index = len(result_items)
            for index, result_item in enumerate(result_items):
                if context.cancelled:
                    break_index = index
                    break
                compressor_type = self.mime_type_to_compressor_type(result_item.mime_type)
                compressor = self.compressors.get(compressor_type)
                if compressor is None:
                    result_item.set_error(_("Format of this file is not supported."))
                    c_update_result_item(result_item)
                    continue
                futures.append(
                    executor.submit(compressor.run, result_item, c_update_result_item, context)
                )

            for future in futures:
                future.result()

            if context.cancelled:
                for result_item in result_items[break_index:]:
                    result_item.cancelled = True
                    result_item.running = False
                    c_update_result_item(result_item)
        c_enable_compression(True)
