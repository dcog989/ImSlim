from enum import Enum, auto
from typing import override

from PySide6.QtCore import QObject, Signal


class ResultState(Enum):
    IDLE = auto()
    RUNNING = auto()
    DONE = auto()
    SKIPPED = auto()
    CANCELLED = auto()
    ERROR = auto()


class ResultItem(QObject):
    updated: Signal = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.mime_type: str = ""
        self.filename: str = ""
        self.new_filename: str = ""
        self.backup_filename: str = ""
        self.tmp_filename: str = ""
        self.size: int = 0
        self.new_size: int = 0
        self.atime: float = -1.0
        self.mtime: float = -1.0
        self.mode: int = -1
        self.subtitle_label: str = ""
        self.savings: str = ""
        self.state: ResultState = ResultState.IDLE
        self.error_message: str = ""
        self.error_details_message: str = ""
        self.warning_message: str = ""

    def set_error(self, error: str, details: str = "") -> None:
        self.state = ResultState.ERROR
        self.error_message = error
        self.error_details_message = details
        self.savings = ""

    @override
    def __repr__(self) -> str:
        return self.filename
