from dataclasses import dataclass

from .settings_manager import SettingsManager


@dataclass(frozen=True)
class BatchOptions:
    """Immutable settings snapshot for one analyze→compress batch.

    Captured on the UI thread at batch start so worker and pool threads never
    read the live QSettings-backed SettingsManager, and so a settings edit
    mid-batch cannot desync an output name/extension from the encoder that
    produced it.
    """

    save_method: int
    target_format: str
    output_folder: str
    recursive: bool
    lossy: bool
    metadata: bool
    file_attributes: bool
    png_lossy_level: int
    png_lossless_level: int
    jpg_lossy_level: int
    jpg_progressive: bool
    webp_lossy_level: int
    webp_lossless_level: int
    avif_lossy_level: int
    avif_lossless_level: int
    jxl_lossy_level: int
    jxl_lossless_level: int
    gif_lossy_level: int
    gif_lossless_level: int
    svg_maximum_level: bool
    compression_timeout: int

    @classmethod
    def from_settings(cls, settings: SettingsManager) -> BatchOptions:
        return cls(
            save_method=settings.save_method,
            target_format=settings.target_format,
            output_folder=settings.output_folder,
            recursive=settings.recursive,
            lossy=settings.lossy,
            metadata=settings.metadata,
            file_attributes=settings.file_attributes,
            png_lossy_level=settings.png_lossy_level,
            png_lossless_level=settings.png_lossless_level,
            jpg_lossy_level=settings.jpg_lossy_level,
            jpg_progressive=settings.jpg_progressive,
            webp_lossy_level=settings.webp_lossy_level,
            webp_lossless_level=settings.webp_lossless_level,
            avif_lossy_level=settings.avif_lossy_level,
            avif_lossless_level=settings.avif_lossless_level,
            jxl_lossy_level=settings.jxl_lossy_level,
            jxl_lossless_level=settings.jxl_lossless_level,
            gif_lossy_level=settings.gif_lossy_level,
            gif_lossless_level=settings.gif_lossless_level,
            svg_maximum_level=settings.svg_maximum_level,
            compression_timeout=settings.compression_timeout,
        )
