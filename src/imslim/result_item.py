from dataclasses import dataclass
from enum import Enum, auto
from typing import override


class ResultState(Enum):
    IDLE = auto()
    RUNNING = auto()
    DONE = auto()
    SKIPPED = auto()
    CANCELLED = auto()
    ERROR = auto()


@dataclass(eq=False, repr=False)
class ResultItem:
    mime_type: str = ""
    filename: str = ""
    new_filename: str = ""
    backup_filename: str = ""
    tmp_filename: str = ""
    size: int = 0
    new_size: int = 0
    atime: float = -1.0
    mtime: float = -1.0
    mode: int = -1
    state: ResultState = ResultState.IDLE
    error_message: str = ""
    error_details_message: str = ""
    warning_message: str = ""

    def set_error(self, error: str, details: str = "") -> None:
        self.state = ResultState.ERROR
        self.error_message = error
        self.error_details_message = details

    @override
    def __repr__(self) -> str:
        return self.filename
