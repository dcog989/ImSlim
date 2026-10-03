from collections.abc import Mapping
from dataclasses import dataclass

from .formats import FORMAT_KNOB_KEYS
from .settings_manager import SettingsManager


@dataclass(frozen=True)
class BatchOptions:
    """Immutable settings snapshot for one analyze→compress batch.

    Captured on the UI thread at batch start so worker and pool threads never
    read the live QSettings-backed SettingsManager, and so a settings edit
    mid-batch cannot desync an output name/extension from the encoder that
    produced it. Per-format knobs are keyed by their table-defined names.
    """

    save_method: int
    target_format: str
    output_folder: str
    recursive: bool
    lossy: bool
    metadata: bool
    file_attributes: bool
    compression_timeout: int
    knobs: Mapping[str, int | bool]

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
            compression_timeout=settings.compression_timeout,
            knobs={key: settings.knob(key) for key in FORMAT_KNOB_KEYS},
        )

    def flag(self, key: str) -> bool:
        return bool(self.knobs[key])

    def level(self, key: str) -> int:
        return int(self.knobs[key])
