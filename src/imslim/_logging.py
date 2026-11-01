import atexit
import logging
import logging.handlers
import queue
from pathlib import Path

from .settings_manager import SettingsManager, log_file_path

_LOG_LEVEL_VALUES: dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}
LOG_LEVELS: tuple[str, ...] = ("NONE", *_LOG_LEVEL_VALUES)
_LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"

_listener: logging.handlers.QueueListener | None = None


def _stop_listener() -> None:
    """Flush queued records before the interpreter shuts the file handler down."""
    if _listener is not None:
        _listener.stop()


_res = atexit.register(_stop_listener)


def configure_logging(settings: SettingsManager | None = None) -> None:
    """Install console and rotating-file handlers from the log settings.

    Re-entrant: runs at startup and again whenever the log settings change in
    the settings dialog, so those changes take effect without a restart. Any
    previously installed handlers are removed (file handlers closed) first;
    a level of NONE disables logging entirely.

    Records reach the handlers through a queue: worker threads log while the
    settings dialog may be closing the old file handler, and writing to a
    closed stream from another thread raises.

    ``settings`` may be passed in to reuse the live SettingsManager instance
    (whose writes are not synced to disk until close); a fresh instance reads
    stale values mid-edit.
    """
    global _listener

    settings = settings or SettingsManager()

    root = logging.getLogger()
    if _listener is not None:
        _listener.stop()
        _listener = None
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()
    root.setLevel(logging.WARNING)

    if settings.log_level == "NONE":
        return
    level = _LOG_LEVEL_VALUES.get(settings.log_level, logging.INFO)

    log_path = log_file_path()
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(_LOG_FORMAT)

    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=settings.log_max_size * 1024 * 1024,
        backupCount=settings.log_backups,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    records: queue.SimpleQueue[logging.LogRecord] = queue.SimpleQueue()
    queue_handler = logging.handlers.QueueHandler(records)
    queue_handler.setLevel(level)
    _listener = logging.handlers.QueueListener(
        records, file_handler, console_handler, respect_handler_level=True
    )
    _listener.start()

    root.setLevel(level)
    root.addHandler(queue_handler)
