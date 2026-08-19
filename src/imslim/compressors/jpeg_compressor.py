from ..binary_resolver import resolve_tool
from ..compressor import Command, Compressor


class JPEGCompressor(Compressor):
    @classmethod
    def get_file_type(cls) -> str:
        return "jpeg"

    def _intermediate_path(self, result_item) -> str:
        return self._png_intermediate_path(result_item)

    def _encoded_path(self, result_item) -> str:
        return result_item.tmp_filename + ".enc.jpg"

    def build_command(self, result_item) -> list[Command]:
        if self.settings.lossy:
            return self._build_lossy_command(result_item)
        return self._build_lossless_command(result_item)

    def _build_lossless_command(self, result_item) -> list[Command]:
        jpegtran = [resolve_tool("jpegtran"), "-optimize"]

        if self.settings.jpg_progressive:
            jpegtran.append("-progressive")

        # Keep the ICC profile when stripping metadata so colors still render correctly.
        jpegtran += ["-copy", "all" if self.settings.metadata else "icc"]

        jpegtran += ["-outfile", result_item.tmp_filename, result_item.filename]

        return [Command(jpegtran)]

    def _build_lossy_command(self, result_item) -> list[Command]:
        intermediate = self._intermediate_path(result_item)

        # jpegli can't read JPEG input, so decode to a temporary PNG first
        djpegli = [resolve_tool("djpegli"), result_item.filename, intermediate]

        output = result_item.tmp_filename
        if not self.settings.metadata:
            output = self._encoded_path(result_item)

        cjpegli = [
            resolve_tool("cjpegli"),
            intermediate,
            output,
            "--quality",
            str(self.settings.jpg_lossy_level),
        ]
        cjpegli.append(
            "--progressive_level=2" if self.settings.jpg_progressive else "--progressive_level=0"
        )

        commands = [Command(djpegli), Command(cjpegli)]

        if not self.settings.metadata:
            # jpegli carries ICC/EXIF/XMP from the PNG; strip all but the ICC profile
            jpegtran = [
                resolve_tool("jpegtran"),
                "-copy",
                "icc",
                "-outfile",
                result_item.tmp_filename,
                self._encoded_path(result_item),
            ]
            commands.append(Command(jpegtran))

        return commands

    def get_intermediate_files(self, result_item) -> list[str]:
        files = [self._intermediate_path(result_item)]
        if not self.settings.metadata:
            files.append(self._encoded_path(result_item))
        return files
