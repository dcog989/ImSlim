"""Compressor registry.

Add a new format's compressor here alongside its `FormatSpec` entry;
`create_compression_manager()` registers everything in `ALL_COMPRESSORS`.
"""

from ..compressor import Compressor
from .avif_compressor import AVIFCompressor
from .gif_compressor import GIFCompressor
from .jpeg_compressor import JPEGCompressor
from .jxl_compressor import JXLCompressor
from .png_compressor import PNGCompressor
from .svg_compressor import SVGCompressor
from .webp_compressor import WEBPCompressor

__all__ = ["ALL_COMPRESSORS"]

ALL_COMPRESSORS: tuple[type[Compressor], ...] = (
    PNGCompressor,
    JPEGCompressor,
    WEBPCompressor,
    AVIFCompressor,
    JXLCompressor,
    GIFCompressor,
    SVGCompressor,
)
