import os
import threading
from concurrent.futures import ThreadPoolExecutor

# MIME types that are re-encoded to a different format on output. The value is
# the output file extension (the source file itself is left untouched).
OUTPUT_EXTENSIONS = {
    "image/bmp": ".webp",
    "image/tiff": ".webp",
}

_MIME_TO_COMPRESSOR_TYPE = {
    "image/jpeg": "jpeg",
    "image/png": "png",
    "image/webp": "webp",
    "image/avif": "avif",
    "image/jxl": "jxl",
    "image/gif": "gif",
    "image/svg+xml": "svg",
    "image/bmp": "webp",
    "image/tiff": "webp",
}


class CompressionManager:
    def __init__(self, settings_manager):
        self.settings = settings_manager
        self.compressors = {}

    def mime_type_to_compressor_type(self, mime_type: str) -> str | None:
        return _MIME_TO_COMPRESSOR_TYPE.get(mime_type)

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
        cpu_count = os.cpu_count() or 1
        executor = ThreadPoolExecutor(max_workers=cpu_count)
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
