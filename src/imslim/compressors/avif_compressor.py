from ..binary_resolver import resolve_tool
from ..compressor import Command, Compressor
from ..result_item import ResultItem


class AVIFCompressor(Compressor):
    @classmethod
    def get_file_type(cls) -> str:
        return "avif"

    def _intermediate_path(self, result_item: ResultItem) -> str:
        return self._png_intermediate_path(result_item)

    def build_command(self, result_item: ResultItem) -> list[Command]:
        intermediate = self._intermediate_path(result_item)

        # avifenc can't read AVIF input, so decode to a temporary PNG first
        avifdec = [resolve_tool("avifdec"), result_item.filename, intermediate]

        avifenc = [resolve_tool("avifenc")]

        # avifenc preserves metadata by default. Strip only non-rendering
        # metadata (EXIF/XMP); keep the ICC color profile so colors still
        # render correctly (see issue: color profiles stripped with metadata off).
        if not self.settings.metadata:
            avifenc += ["--ignore-exif", "--ignore-xmp"]

        if self.settings.lossy:
            # tune=iq + 10-bit depth is the best quality/size operating point for libaom
            avifenc += [
                "-q",
                str(self.settings.avif_lossy_level),
                "-a",
                "tune=iq",
                "-d",
                "10",
            ]
        else:
            avifenc.append("--lossless")

        # higher effort -> slower but better compression (speed 0-10, default 6)
        avifenc += ["--speed", str(10 - self.settings.avif_lossless_level)]
        avifenc += [intermediate, result_item.tmp_filename]

        return [Command(avifdec), Command(avifenc)]

    def get_intermediate_files(self, result_item: ResultItem) -> list[str]:
        return [self._intermediate_path(result_item)]
