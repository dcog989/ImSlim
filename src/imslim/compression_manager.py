import logging
import os
import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor

from ._i18n import _
from .batch_options import BatchOptions
from .compressor import CompressionContext, Compressor
from .conversion import is_converting
from .formats import CONFIGURED_COMPRESSOR_TYPES, MIME_TO_COMPRESSOR
from .result_item import ResultItem

logger = logging.getLogger(__name__)

# Bound on how long shutdown waits for the compression worker to unwind and
# clean up temp files after cancellation; the kill grace is far shorter.
_SHUTDOWN_TIMEOUT_SECONDS = 5.0


class CompressionManager:
    def __init__(self) -> None:
        self.compressors: dict[str, Compressor] = {}
        self._context: CompressionContext | None = None
        self._thread: threading.Thread | None = None

    def mime_type_to_compressor_type(self, mime_type: str) -> str | None:
        return MIME_TO_COMPRESSOR.get(mime_type, (None, None))[0]

    def register_compressor(self, ConcreteCompressor: type[Compressor]) -> None:
        file_type = ConcreteCompressor.get_file_type()
        assert file_type in CONFIGURED_COMPRESSOR_TYPES, (
            f"Compressor '{file_type}' is not referenced in MIME_TO_COMPRESSOR"
        )
        if file_type not in self.compressors:
            self.compressors[file_type] = ConcreteCompressor()

    def validate_configured_compressors(self) -> None:
        unregistered = sorted(CONFIGURED_COMPRESSOR_TYPES - set(self.compressors))
        assert not unregistered, (
            f"No compressor registered for configured types: {', '.join(unregistered)}"
        )

    def _compressor_for(self, result_item: ResultItem, options: BatchOptions) -> Compressor | None:
        """Resolve the compressor for one item: the conversion target when
        converting, otherwise the compressor matching the source format."""
        if is_converting(options.target_format):
            return self.compressors.get(options.target_format)
        return self.compressors.get(self.mime_type_to_compressor_type(result_item.mime_type) or "")

    def _collect_used_compressors(
        self, result_items: list[ResultItem], options: BatchOptions
    ) -> set[Compressor]:
        used: set[Compressor] = set()
        for result_item in result_items:
            compressor = self._compressor_for(result_item, options)
            if compressor is not None:
                used.add(compressor)
        return used

    def compress(
        self,
        result_items: list[ResultItem],
        options: BatchOptions,
        c_update_result_item: Callable[[ResultItem], None],
        c_enable_compression: Callable[[bool], None],
    ) -> None:
        context = CompressionContext()
        self._context = context
        logger.info("Starting compression batch of %d images", len(result_items))
        thread = threading.Thread(
            target=self._compress,
            args=(result_items, options, c_update_result_item, c_enable_compression, context),
            daemon=True,
        )
        self._thread = thread
        thread.start()

    def cancel(self) -> None:
        if self._context is not None:
            self._context.cancel()

    def shutdown(self) -> None:
        """Cancel any running batch and wait for its worker to finish cleanup."""
        self.cancel()
        thread = self._thread
        if thread is not None:
            thread.join(_SHUTDOWN_TIMEOUT_SECONDS)
            if thread.is_alive():
                logger.warning(
                    "Compression worker still running %.1fs after shutdown",
                    _SHUTDOWN_TIMEOUT_SECONDS,
                )

    def _compress(
        self,
        result_items: list[ResultItem],
        options: BatchOptions,
        c_update_result_item: Callable[[ResultItem], None],
        c_enable_compression: Callable[[bool], None],
        context: CompressionContext,
    ) -> None:
        # Avoid oversubscribing: encode tools (e.g. cwebp -mt) already thread internally.
        max_workers = max(1, (os.cpu_count() or 1) // 2)
        used_compressors = self._collect_used_compressors(result_items, options)
        try:
            for compressor in used_compressors:
                try:
                    compressor.prepare_batch(result_items, options)
                except OSError as err:
                    logger.warning("Failed to prepare batch resources: %s", err)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures: list[Future[None]] = []
                break_index = len(result_items)
                for index, result_item in enumerate(result_items):
                    if context.cancelled:
                        break_index = index
                        break
                    compressor = self._compressor_for(result_item, options)
                    if compressor is None:
                        result_item.set_error(_("Format of this file is not supported."))
                        c_update_result_item(result_item)
                        continue
                    futures.append(
                        executor.submit(
                            compressor.run, result_item, c_update_result_item, context, options
                        )
                    )

                for future in futures:
                    future.result()

                if context.cancelled:
                    for result_item in result_items[break_index:]:
                        result_item.cancelled = True
                        result_item.running = False
                        c_update_result_item(result_item)
        except Exception:
            # A compressor escaped its own error handling (e.g. BaseException
            # from run()); surface it and still re-enable the UI below.
            logger.exception("Compression batch failed unexpectedly")
        finally:
            for compressor in used_compressors:
                try:
                    compressor.finish_batch()
                except Exception as err:
                    logger.warning("Failed to finish batch resources: %s", err)
            c_enable_compression(True)
        logger.info("Compression batch finished")
