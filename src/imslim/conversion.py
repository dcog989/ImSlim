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
    if source_mime == "image/jpeg":
        return [[resolve_tool("djpegli"), source, destination]]
    if source_mime == "image/jxl":
        return [[resolve_tool("djxl"), source, destination]]
    if source_mime == "image/avif":
        return [[resolve_tool("avifdec"), source, destination]]
    to_png(source, destination)
    return []
