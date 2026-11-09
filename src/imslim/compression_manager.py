import logging
import threading
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import replace

from ._i18n import _
from .batch_options import BatchOptions
from .command_runner import CompressionContext
from .compressor import Compressor
from .compressors import ALL_COMPRESSORS
from .formats import (
    CONFIGURED_COMPRESSOR_TYPES,
    FORMAT_BY_KEY,
    MIME_TO_FORMAT,
    CompressorType,
    is_converting,
)
from .pipeline import CompressionPipeline
from .result_item import ResultItem, ResultState
from .result_item_manager import ResultItemManager
from .system_info import worker_count

logger = logging.getLogger(__name__)

# Bound on how long shutdown waits for the compression worker to unwind and
# clean up temp files after cancellation; the kill grace is far shorter.
_SHUTDOWN_TIMEOUT_SECONDS = 5.0

# How many compressions may sit queued ahead of the pool per worker. Without a
# cap a 100k-image batch submits a Future per file before the first finishes;
# two per worker keeps every worker fed while overlapping submit with completion.
_MAX_PENDING_PER_WORKER = 2


class CompressionManager:
    def __init__(self) -> None:
        self.compressors: dict[CompressorType, Compressor] = {}
        self._pipeline: CompressionPipeline = CompressionPipeline()
        self._context: CompressionContext | None = None
        self._thread: threading.Thread | None = None

    def register_compressor(self, ConcreteCompressor: type[Compressor]) -> None:
        file_type = ConcreteCompressor.get_file_type()
        if file_type not in CONFIGURED_COMPRESSOR_TYPES:
            raise ValueError(f"Compressor '{file_type}' is not referenced in FORMAT_SPECS")
        if file_type not in self.compressors:
            self.compressors[file_type] = ConcreteCompressor()

    def validate_configured_compressors(self) -> None:
        unregistered = sorted(CONFIGURED_COMPRESSOR_TYPES - set(self.compressors))
        if unregistered:
            raise RuntimeError(
                f"No compressor registered for configured types: {', '.join(unregistered)}"
            )

    def _compressor_for(self, result_item: ResultItem, options: BatchOptions) -> Compressor | None:
        """Resolve the compressor for one item: the conversion target when
        converting, otherwise the compressor matching the source format."""
        if is_converting(options.target_format):
            target_spec = FORMAT_BY_KEY[options.target_format]
            return self.compressors.get(target_spec.compressor_key)
        spec = MIME_TO_FORMAT.get(result_item.mime_type)
        if spec is None:
            return None
        return self.compressors.get(spec.compressor_key)

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

    def preview(
        self,
        result_item: ResultItem,
        options: BatchOptions,
        output_path: str,
        context: CompressionContext,
    ) -> ResultItem:
        """Compress one item into `output_path` without touching its real output.

        Runs the same compressor and options a batch would, so the comparison
        pane shows exactly what Process would write. `skip_if_larger` is
        overridden: the preview must exist even when the real run would keep
        the original. Returns a copy; `result_item` itself is never modified.
        """
        preview = replace(
            result_item,
            new_filename=output_path,
            tmp_filename=output_path + ".tmp",
            backup_filename="",
            state=ResultState.IDLE,
            new_size=0,
            error_message="",
            error_details_message="",
        )
        compressor = self._compressor_for(preview, options)
        if compressor is None:
            preview.set_error(_("Format of this file is not supported."))
            return preview
        self._pipeline.run(
            compressor,
            preview,
            lambda _item: None,
            context,
            replace(options, skip_if_larger=False),
            report=False,
        )
        return preview

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
        try:
            # Naming the outputs stats the filesystem for every item; keep that
            # off the UI thread. The output folder was created at batch start.
            manager = ResultItemManager(options)
            prepared_count = 0
            for prepared_count, result_item in enumerate(result_items):
                if context.cancelled:
                    break
                manager.prepare(result_item)
            else:
                prepared_count = len(result_items)
            if context.cancelled:
                for result_item in result_items[prepared_count:]:
                    result_item.state = ResultState.CANCELLED
                    c_update_result_item(result_item)
                result_items = result_items[:prepared_count]

            # Encoders are capped to two threads per job, so half the cores as
            # workers keeps the total near the core count.
            max_workers = worker_count()
            max_pending = max_workers * _MAX_PENDING_PER_WORKER
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                pending: set[Future[None]] = set()
                break_index = len(result_items)
                for index, result_item in enumerate(result_items):
                    if context.cancelled:
                        break_index = index
                        break
                    if result_item.state is ResultState.ERROR:
                        # prepare() failed on this item (missing source, no
                        # output directory); do not spend an encoder run on it.
                        c_update_result_item(result_item)
                        continue
                    compressor = self._compressor_for(result_item, options)
                    if compressor is None:
                        result_item.set_error(_("Format of this file is not supported."))
                        c_update_result_item(result_item)
                        continue
                    if len(pending) >= max_pending:
                        # Wait for any finished job, not the oldest one: a
                        # single slow file must not keep the other workers idle.
                        done, pending = wait(pending, return_when=FIRST_COMPLETED)
                        for future in done:
                            future.result()
                    pending.add(
                        executor.submit(
                            self._pipeline.run,
                            compressor,
                            result_item,
                            c_update_result_item,
                            context,
                            options,
                        )
                    )

                while pending:
                    done, pending = wait(pending, return_when=FIRST_COMPLETED)
                    for future in done:
                        future.result()

                if context.cancelled:
                    for result_item in result_items[break_index:]:
                        result_item.state = ResultState.CANCELLED
                        c_update_result_item(result_item)
        except Exception:
            # A compressor escaped its own error handling (e.g. BaseException
            # from run()); surface it and still re-enable the UI below.
            logger.exception("Compression batch failed unexpectedly")
        finally:
            c_enable_compression(True)
        logger.info("Compression batch finished")


def create_compression_manager() -> CompressionManager:
    """Build a CompressionManager wired with every registered compressor.

    Composition root: callers depend on the manager, not on concrete
    compressor classes.
    """
    manager = CompressionManager()
    for compressor in ALL_COMPRESSORS:
        manager.register_compressor(compressor)
    manager.validate_configured_compressors()
    return manager
