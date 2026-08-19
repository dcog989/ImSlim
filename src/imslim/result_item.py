from PySide6.QtCore import QObject, Signal


class ResultItem(QObject):
    updated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.mime_type = ""
        self.filename = ""
        self.new_filename = ""
        self.backup_filename = ""
        self.tmp_filename = ""
        self.size = 0
        self.new_size = 0
        self.atime = -1.0
        self.mtime = -1.0
        self.subtitle_label = ""
        self.savings = ""
        self.running = False
        self.skipped = False
        self.error = False
        self.error_message = ""
        self.error_details = False
        self.error_details_message = ""

    def set_error(self, error: str, details: str = "") -> None:
        self.error = True
        self.error_message = error
        self.error_details = bool(details)
        self.error_details_message = details
        self.running = False
        self.savings = ""

    def __repr__(self) -> str:
        return self.filename
