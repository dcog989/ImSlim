"""Single source of truth for every image format the app understands.

A `FormatSpec` bundles everything the rest of the app needs to know about a
format: how it is detected (MIME + extensions), how it is decoded, which
compressor handles it, which settings knobs it exposes and how each knob is
rendered. All the derived lookup tables, the file dialog filter, the settings
defaults and the format selector are built from this table, so adding a format
means adding one compressor module plus one entry here.
"""

from dataclasses import dataclass
from typing import Literal

from ._i18n import _

KEEP_FORMAT = "keep"

_QUALITY_HINT = _("Set the quality; 100 is best.")


def _level_hint(max_level: int) -> str:
    return _("Set the level; {} is highest but slowest.").format(max_level)


@dataclass(frozen=True)
class Knob:
    """One per-format setting exposed in the Formats tab."""

    key: str
    kind: Literal["level", "flag"]
    default: int | bool
    label: str
    hint: str
    lower: int = 0
    upper: int = 0


@dataclass(frozen=True)
class FormatSpec:
    key: str
    display: str
    title: str
    compressor_key: str
    source_mimes: tuple[str, ...]
    source_extensions: tuple[str, ...]
    output_extension: str
    target: bool
    native_inputs: frozenset[str]
    decoder: str | None
    knobs: tuple[Knob, ...] = ()


FORMAT_SPECS: tuple[FormatSpec, ...] = (
    FormatSpec(
        key="png",
        display="PNG",
        title="PNG",
        compressor_key="png",
        source_mimes=("image/png",),
        source_extensions=(".png",),
        output_extension=".png",
        target=True,
        native_inputs=frozenset({"image/png"}),
        decoder=None,
        knobs=(
            Knob("png-lossy-level", "level", 90, _("Lossy"), _QUALITY_HINT, 0, 100),
            Knob("png-lossless-level", "level", 4, _("Lossless"), _level_hint(6), 0, 6),
        ),
    ),
    FormatSpec(
        key="jpeg",
        display="JPEG",
        title="JPEG / Jpegli",
        compressor_key="jpeg",
        source_mimes=("image/jpeg",),
        source_extensions=(".jpg", ".jpeg"),
        output_extension=".jpg",
        target=True,
        native_inputs=frozenset({"image/jpeg", "image/png"}),
        decoder="djpegli",
        knobs=(
            Knob("jpg-lossy-level", "level", 90, _("Lossy"), _QUALITY_HINT, 0, 100),
            Knob(
                "jpg-progressive",
                "flag",
                False,
                _("Progressive Encode"),
                _("Render incrementally, from blurry to clear."),
            ),
        ),
    ),
    FormatSpec(
        key="webp",
        display="WebP",
        title="WebP",
        compressor_key="webp",
        source_mimes=("image/webp",),
        source_extensions=(".webp",),
        output_extension=".webp",
        target=True,
        native_inputs=frozenset({"image/jpeg", "image/png", "image/webp"}),
        decoder=None,
        knobs=(
            Knob("webp-lossy-level", "level", 70, _("Lossy"), _QUALITY_HINT, 0, 100),
            Knob("webp-lossless-level", "level", 4, _("Lossless"), _level_hint(6), 0, 6),
        ),
    ),
    FormatSpec(
        key="avif",
        display="AVIF",
        title="AVIF",
        compressor_key="avif",
        source_mimes=("image/avif",),
        source_extensions=(".avif",),
        output_extension=".avif",
        target=True,
        native_inputs=frozenset({"image/avif", "image/png"}),
        decoder="avifdec",
        knobs=(
            Knob("avif-lossy-level", "level", 70, _("Lossy"), _QUALITY_HINT, 0, 100),
            Knob("avif-lossless-level", "level", 6, _("Lossless"), _level_hint(10), 0, 10),
        ),
    ),
    FormatSpec(
        key="jxl",
        display="JXL",
        title="JXL",
        compressor_key="jxl",
        source_mimes=("image/jxl",),
        source_extensions=(".jxl",),
        output_extension=".jxl",
        target=True,
        native_inputs=frozenset({"image/jxl", "image/png"}),
        decoder="djxl",
        knobs=(
            Knob("jxl-lossy-level", "level", 70, _("Lossy"), _QUALITY_HINT, 1, 100),
            Knob("jxl-lossless-level", "level", 6, _("Lossless"), _level_hint(10), 1, 10),
        ),
    ),
    FormatSpec(
        key="gif",
        display="GIF",
        title="GIF",
        compressor_key="gif",
        source_mimes=("image/gif",),
        source_extensions=(".gif",),
        output_extension=".gif",
        target=False,
        native_inputs=frozenset(),
        decoder=None,
        knobs=(
            Knob("gif-lossy-level", "level", 80, _("Lossy"), _QUALITY_HINT, 1, 100),
            Knob("gif-lossless-level", "level", 2, _("Lossless"), _level_hint(3), 1, 3),
        ),
    ),
    FormatSpec(
        key="svg",
        display="SVG",
        title="SVG",
        compressor_key="svg",
        source_mimes=("image/svg+xml",),
        source_extensions=(".svg",),
        output_extension=".svg",
        target=False,
        native_inputs=frozenset(),
        decoder=None,
        knobs=(
            Knob(
                "svg-maximum-level",
                "flag",
                False,
                _("Maximum Compression Level"),
                _("Enable maximum cleaning of SVG images; can be more destructive."),
            ),
        ),
    ),
    FormatSpec(
        key="bmp",
        display="BMP",
        title="BMP",
        compressor_key="webp",
        source_mimes=("image/bmp",),
        source_extensions=(".bmp",),
        output_extension=".webp",
        target=False,
        native_inputs=frozenset(),
        decoder=None,
    ),
    FormatSpec(
        key="tiff",
        display="TIFF",
        title="TIFF",
        compressor_key="webp",
        source_mimes=("image/tiff",),
        source_extensions=(".tiff", ".tif"),
        output_extension=".webp",
        target=False,
        native_inputs=frozenset(),
        decoder=None,
    ),
)

FORMAT_BY_KEY: dict[str, FormatSpec] = {spec.key: spec for spec in FORMAT_SPECS}

MIME_TO_FORMAT: dict[str, FormatSpec] = {
    mime: spec for spec in FORMAT_SPECS for mime in spec.source_mimes
}

ALLOWED_MIME_TYPES: frozenset[str] = frozenset(MIME_TO_FORMAT)

# MIME -> (compressor type, output extension override). Re-encoded formats
# (BMP/TIFF -> WebP) carry an override; every other format keeps its own.
MIME_TO_COMPRESSOR: dict[str, tuple[str, str | None]] = {
    mime: (
        spec.compressor_key,
        spec.output_extension if spec.compressor_key != spec.key else None,
    )
    for spec in FORMAT_SPECS
    for mime in spec.source_mimes
}

OUTPUT_EXTENSIONS: dict[str, str] = {
    mime: extension
    for mime, (_compressor, extension) in MIME_TO_COMPRESSOR.items()
    if extension is not None
}

CONFIGURED_COMPRESSOR_TYPES: frozenset[str] = frozenset(
    spec.compressor_key for spec in FORMAT_SPECS
)

# Conversion targets in the order shown in the format selector (alphabetical).
TARGET_SPECS: tuple[FormatSpec, ...] = tuple(
    sorted((spec for spec in FORMAT_SPECS if spec.target), key=lambda spec: spec.display)
)
TARGET_FORMATS: tuple[str, ...] = tuple(spec.key for spec in TARGET_SPECS)
TARGET_EXTENSIONS: dict[str, str] = {spec.key: spec.output_extension for spec in TARGET_SPECS}
NATIVE_INPUTS: dict[str, frozenset[str]] = {spec.key: spec.native_inputs for spec in TARGET_SPECS}


def _build_decoder_tools() -> dict[str, str]:
    tools: dict[str, str] = {}
    for spec in FORMAT_SPECS:
        if spec.decoder is not None:
            for mime in spec.source_mimes:
                tools[mime] = spec.decoder
    return tools


DECODER_TOOLS: dict[str, str] = _build_decoder_tools()

IMAGE_EXTENSIONS: tuple[str, ...] = tuple(
    extension for spec in FORMAT_SPECS for extension in spec.source_extensions
)

FORMAT_KNOB_KEYS: frozenset[str] = frozenset(
    knob.key for spec in FORMAT_SPECS for knob in spec.knobs
)
FORMAT_DEFAULT_KNOBS: dict[str, int | bool] = {
    knob.key: knob.default for spec in FORMAT_SPECS for knob in spec.knobs
}


def is_converting(target: str) -> bool:
    """True when the target selects a real conversion format."""
    return target in TARGET_FORMATS


def native_inputs(target: str) -> frozenset[str]:
    """Source MIME types the target encoder can consume without a pre-decode."""
    return NATIVE_INPUTS.get(target, frozenset())


def image_filter() -> str:
    """File dialog filter string built from the format table."""
    all_extensions = " ".join(f"*{ext}" for ext in IMAGE_EXTENSIONS)
    per_format = ";;".join(
        f"{spec.display} ({' '.join(f'*{ext}' for ext in spec.source_extensions)})"
        for spec in FORMAT_SPECS
    )
    return _(f"Images ({all_extensions});;" + per_format + ";;All files (*)")
