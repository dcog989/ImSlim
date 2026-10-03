"""Composition root: assemble the application's object graph."""

from dataclasses import dataclass

from .batch_flow import BatchFlow
from .compression_manager import CompressionManager, create_compression_manager
from .settings_manager import SettingsManager


@dataclass(frozen=True)
class AppContext:
    settings: SettingsManager
    manager: CompressionManager
    flow: BatchFlow


def build_app_context() -> AppContext:
    settings = SettingsManager()
    manager = create_compression_manager()
    flow = BatchFlow(settings, manager)
    return AppContext(settings=settings, manager=manager, flow=flow)
