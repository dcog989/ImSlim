from .binary_resolver import resolve_tool
from .formats import DECODER_TOOLS, is_converting, native_inputs
from .image_convert import to_png

__all__ = [
    "decode_to_png",
    "decoder_argv",
    "is_converting",
    "native_inputs",
]


def decode_to_png(source_mime: str, source: str, destination: str) -> list[list[str]]:
    """Decode an arbitrary source image to a PNG at `destination`.

    Returns zero or more argv lists for bundled decoders. Sources without a
    bundled decoder (WebP/GIF/BMP/TIFF/SVG) are decoded in-process with Qt,
    which happens here rather than as a subprocess, so the returned list is
    empty for those. Must be called off the UI thread; QImage is thread-safe.
    """
    argv = decoder_argv(source_mime, source, destination)
    if argv is not None:
        return [argv]
    to_png(source, destination)
    return []


def decoder_argv(source_mime: str, source: str, destination: str) -> list[str] | None:
    """argv for the bundled decoder of `source_mime`, or None when Qt must
    decode the source in-process instead."""
    tool = DECODER_TOOLS.get(source_mime)
    if tool is None:
        return None
    return [resolve_tool(tool), source, destination]
