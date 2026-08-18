from PySide6.QtCore import QObject, Signal


class ResultItem(QObject):
    updated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.file = None
        self.mime_type = ""
        self.name = ""
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
        self.running = True
        self.skipped = False
        self.error = False
        self.error_message = ""
        self.error_details = False
        self.error_details_message = ""

    def set_error(self, error: str) -> None:
        self.error = True
        self.error_message = error

    def __repr__(self):
        return str(self.name)
