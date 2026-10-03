from .binary_resolver import resolve_tool
from .image_convert import to_png

KEEP_FORMAT = "keep"

TARGET_FORMATS: tuple[str, ...] = ("png", "jpeg", "webp", "avif", "jxl")

TARGET_EXTENSIONS: dict[str, str] = {
    "png": ".png",
    "jpeg": ".jpg",
    "webp": ".webp",
    "avif": ".avif",
    "jxl": ".jxl",
}

# Source MIME type -> bundled decoder that emits PNG. Formats absent here have
# no bundled decoder and are decoded in-process with Qt. Single source of truth
# shared by decode_to_png and the per-format compressors that pre-decode a
# source before their encoder (which cannot read that format) consumes it.
DECODER_TOOLS: dict[str, str] = {
    "image/jpeg": "djpegli",
    "image/avif": "avifdec",
    "image/jxl": "djxl",
}

# Source MIME types each target encoder can consume without a pre-decode step.
# PNG is native to every raster target; AVIF/JXL/JPEG also read their own format
# directly (the compressors decode those internally).
_NATIVE_INPUTS: dict[str, frozenset[str]] = {
    "png": frozenset({"image/png"}),
    "jpeg": frozenset({"image/jpeg", "image/png"}),
    "webp": frozenset({"image/jpeg", "image/png", "image/webp"}),
    "avif": frozenset({"image/avif", "image/png"}),
    "jxl": frozenset({"image/jxl", "image/png"}),
}


def native_inputs(target: str) -> frozenset[str]:
    return _NATIVE_INPUTS.get(target, frozenset())


def is_converting(target: str) -> bool:
    """True when the target selects a real conversion format.

    Unknown/legacy values fall back to keep-format behaviour.
    """
    return target in TARGET_FORMATS


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
