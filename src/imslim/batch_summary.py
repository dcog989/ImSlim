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

    def record_added(self) -> None:
        self.total += 1

    def record_done(self) -> None:
        self.done += 1

    def record_compressed(self) -> None:
        self.compressed += 1

    def record_skipped(self) -> None:
        self.skipped += 1

    def record_failed(self) -> None:
        self.failed += 1
