import logging
import os
import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor

from ._i18n import _
from .compressor import CompressionContext, Compressor
from .result_item import ResultItem
from .settings_manager import SettingsManager

logger = logging.getLogger(__name__)

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

# Compressor types referenced by MIME_TO_COMPRESSOR; used to validate that every
# configured type is covered by a registered compressor.
_CONFIGURED_COMPRESSOR_TYPES = frozenset(
    compress_type for compress_type, _extension in MIME_TO_COMPRESSOR.values()
)


class CompressionManager:
    def __init__(self, settings_manager: SettingsManager) -> None:
        self.settings: SettingsManager = settings_manager
        self.compressors: dict[str, Compressor] = {}
        self._context: CompressionContext | None = None

    def mime_type_to_compressor_type(self, mime_type: str) -> str | None:
        return MIME_TO_COMPRESSOR.get(mime_type, (None, None))[0]

    def register_compressor(self, ConcreteCompressor: type[Compressor]) -> None:
        file_type = ConcreteCompressor.get_file_type()
        assert file_type in _CONFIGURED_COMPRESSOR_TYPES, (
            f"Compressor '{file_type}' is not referenced in MIME_TO_COMPRESSOR"
        )
        if file_type not in self.compressors:
            self.compressors[file_type] = ConcreteCompressor(self.settings)

    def validate_configured_compressors(self) -> None:
        unregistered = sorted(_CONFIGURED_COMPRESSOR_TYPES - set(self.compressors))
        assert not unregistered, (
            f"No compressor registered for configured types: {', '.join(unregistered)}"
        )

    def _collect_used_compressors(self, result_items: list[ResultItem]) -> set[Compressor]:
        used: set[Compressor] = set()
        for result_item in result_items:
            compressor = self.compressors.get(
                self.mime_type_to_compressor_type(result_item.mime_type) or ""
            )
            if compressor is not None:
                used.add(compressor)
        return used

    def compress(
        self,
        result_items: list[ResultItem],
        c_update_result_item: Callable[[ResultItem], None],
        c_enable_compression: Callable[[bool], None],
    ) -> None:
        context = CompressionContext()
        self._context = context
        logger.info("Starting compression batch of %d images", len(result_items))
        threading.Thread(
            target=self._compress,
            args=(result_items, c_update_result_item, c_enable_compression, context),
            daemon=True,
        ).start()

    def cancel(self) -> None:
        if self._context is not None:
            self._context.cancel()

    def _compress(
        self,
        result_items: list[ResultItem],
        c_update_result_item: Callable[[ResultItem], None],
        c_enable_compression: Callable[[bool], None],
        context: CompressionContext,
    ) -> None:
        # Avoid oversubscribing: encode tools (e.g. cwebp -mt) already thread internally.
        max_workers = max(1, (os.cpu_count() or 1) // 2)
        used_compressors = self._collect_used_compressors(result_items)
        try:
            for compressor in used_compressors:
                try:
                    compressor.prepare_batch(result_items)
                except OSError as err:
                    logger.warning("Failed to prepare batch resources: %s", err)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures: list[Future[None]] = []
                break_index = len(result_items)
                for index, result_item in enumerate(result_items):
                    if context.cancelled:
                        break_index = index
                        break
                    compressor_type = self.mime_type_to_compressor_type(result_item.mime_type)
                    compressor = self.compressors.get(compressor_type or "")
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
