"""Composition root: assemble the application's object graph."""

from dataclasses import dataclass

from .batch_flow import BatchFlow
from .compression_manager import create_compression_manager
from .settings_manager import SettingsManager


@dataclass(frozen=True)
class AppContext:
    settings: SettingsManager
    flow: BatchFlow


def build_app_context() -> AppContext:
    settings = SettingsManager()
    flow = BatchFlow(settings, create_compression_manager())
    return AppContext(settings=settings, flow=flow)
