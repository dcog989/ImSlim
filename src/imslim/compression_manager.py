import os
import threading
from concurrent.futures import ThreadPoolExecutor

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


class CompressionManager:
    def __init__(self, settings_manager):
        self.settings = settings_manager
        self.compressors = {}

    def mime_type_to_compressor_type(self, mime_type: str) -> str | None:
        return MIME_TO_COMPRESSOR.get(mime_type, (None,))[0]

    def register_compressor(self, ConcreteCompressor):
        file_type = ConcreteCompressor.get_file_type()
        if file_type not in self.compressors:
            self.compressors[file_type] = ConcreteCompressor(self.settings)

    def compress(self, result_items, c_update_result_item, c_enable_compression):
        threading.Thread(
            target=self._compress,
            args=(result_items, c_update_result_item, c_enable_compression),
            daemon=True,
        ).start()

    def _compress(self, result_items, c_update_result_item, c_enable_compression):
        max_workers = max(1, (os.cpu_count() or 1) // 2)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for result_item in result_items:
                compressor_type = self.mime_type_to_compressor_type(result_item.mime_type)
                compressor = self.compressors.get(compressor_type)
                if compressor is None:
                    result_item.set_error(_("Format of this file is not supported."))
                    c_update_result_item(result_item)
                    continue
                future = executor.submit(compressor.run, result_item, c_update_result_item)
                futures.append(future)

            for future in futures:
                future.result()
        c_enable_compression(True)
