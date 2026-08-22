from typing import override

from PySide6.QtCore import QObject, Signal


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
        self.subtitle_label: str = ""
        self.savings: str = ""
        self.running: bool = False
        self.skipped: bool = False
        self.cancelled: bool = False
        self.error: bool = False
        self.error_message: str = ""
        self.error_details: bool = False
        self.error_details_message: str = ""

    def set_error(self, error: str, details: str = "") -> None:
        self.error = True
        self.error_message = error
        self.error_details = bool(details)
        self.error_details_message = details
        self.running = False
        self.savings = ""

    @override
    def __repr__(self) -> str:
        return self.filename
