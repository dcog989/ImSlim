from ._i18n import _
from .tools import sizeof_fmt


class BatchSummary:
    """Tracks per-batch counters and renders the progress summary line."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.total: int = 0
        self.done: int = 0
        self.compressed: int = 0
        self.skipped: int = 0
        self.failed: int = 0
        self.saved_bytes: int = 0

    def record_added(self) -> None:
        self.total += 1

    def record_done(self) -> None:
        self.done += 1

    def record_compressed(self, saved_bytes: int) -> None:
        self.compressed += 1
        self.saved_bytes += saved_bytes

    def record_skipped(self) -> None:
        self.skipped += 1

    def record_failed(self) -> None:
        self.failed += 1

    def text(self) -> str:
        text = (
            _("%d of %d images done") % (self.done, self.total)
            + " · "
            + _("%d compressed") % self.compressed
            + " · "
            + _("%s saved") % sizeof_fmt(self.saved_bytes)
        )
        if self.skipped:
            text += " · " + _("%d skipped") % self.skipped
        if self.failed:
            text += " · " + _("%d failed") % self.failed
        return text
