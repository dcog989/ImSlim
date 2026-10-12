from ._i18n import _
from .format import sizeof_fmt


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

    def text(self, converting: bool = False) -> str:
        progress = _("{done} of {total} images done").format(done=self.done, total=self.total)
        if converting:
            text = progress + " · " + _("{count} converted").format(count=self.compressed)
        else:
            text = (
                progress
                + " · "
                + _("{count} compressed").format(count=self.compressed)
                + " · "
                + _("{size} saved").format(size=sizeof_fmt(self.saved_bytes))
            )
        if self.skipped:
            text += " · " + _("{count} skipped").format(count=self.skipped)
        if self.failed:
            text += " · " + _("{count} failed").format(count=self.failed)
        return text
