import os
import threading
from concurrent.futures import ThreadPoolExecutor


class CompressionManager:
    def __init__(self, settings_manager):
        self.settings = settings_manager
        self.compressors = {}

    def mime_type_to_compressor_type(self, mime_type: str) -> str | None:
        if mime_type == "image/jpeg":
            return "jpeg"
        elif mime_type == "image/png":
            return "png"
        elif mime_type == "image/webp":
            return "webp"
        elif mime_type == "image/avif":
            return "avif"
        elif mime_type == "image/jxl":
            return "jxl"
        elif mime_type == "image/gif":
            return "gif"
        elif mime_type == "image/svg+xml":
            return "svg"
        return None

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
