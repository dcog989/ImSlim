import atexit
import logging
import logging.handlers
import os
import queue
from datetime import date
from pathlib import Path
from typing import override

from .settings_manager import LOG_FILE_NAME, SettingsManager, log_file_path

# shortcut: two --now runs share and rotate this one file, so a rollover racing
# another run can lose a log line; give each PID its own file if --now ever runs
# in parallel by design.
NOW_LOG_FILE_NAME = "imslim-now.log"

_LOG_LEVEL_VALUES: dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}
LOG_LEVELS: tuple[str, ...] = ("NONE", *_LOG_LEVEL_VALUES)
_LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"

logger = logging.getLogger(__name__)

_listener: logging.handlers.QueueListener | None = None


class _DailyRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """Rotate at the size limit and on the first record of a new day.

    A session that only logs a few lines would otherwise keep one file for
    weeks; the day check makes the daily file predictable without a restart.
    """

    def __init__(
        self, filename: str, *, max_bytes: int, backup_count: int, encoding: str = "utf-8"
    ) -> None:
        super().__init__(filename, maxBytes=max_bytes, backupCount=backup_count, encoding=encoding)
        try:
            # A file left by an earlier run may already be from yesterday; the
            # first record today must roll it instead of appending for weeks.
            self._day: date = date.fromtimestamp(os.path.getmtime(filename))
        except OSError:
            self._day = date.today()

    @override
    def shouldRollover(self, record: logging.LogRecord) -> bool:
        if date.today() != self._day:
            return True
        return bool(super().shouldRollover(record))

    @override
    def doRollover(self) -> None:
        self._day = date.today()
        super().doRollover()


def _stop_listener() -> None:
    """Flush queued records before the interpreter shuts the file handler down."""
    if _listener is not None:
        _listener.stop()


_res = atexit.register(_stop_listener)


def configure_logging(
    settings: SettingsManager | None = None, *, log_name: str = LOG_FILE_NAME
) -> None:
    """Install console and rotating-file handlers from the log settings.

    Re-entrant: a second call replaces the handlers, which keeps tests and the
    ImSlimNow entry point from stacking output. Any previously installed
    handlers are removed (file handlers closed) first; a level of NONE disables
    logging entirely.

    Records reach the handlers through a queue: worker threads log while the
    old file handler is being closed, and writing to a closed stream from
    another thread raises.
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

    if settings.log_level == "NONE":
        # A handler keeps logging.lastResort from printing WARNING+ to stderr.
        root.addHandler(logging.NullHandler())
        root.setLevel(logging.CRITICAL + 1)
        return
    level = _LOG_LEVEL_VALUES.get(settings.log_level, logging.INFO)

    formatter = logging.Formatter(_LOG_FORMAT)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    handlers: list[logging.Handler] = [console_handler]

    file_error: OSError | None = None
    try:
        log_path = log_file_path(log_name)
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        file_handler = _DailyRotatingFileHandler(
            log_path,
            max_bytes=settings.log_max_size * 1024 * 1024,
            backup_count=settings.log_backups,
        )
    except OSError as err:
        # Logging must never stop the app from starting: keep the console only.
        file_error = err
    else:
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        handlers.insert(0, file_handler)

    records: queue.SimpleQueue[logging.LogRecord] = queue.SimpleQueue()
    queue_handler = logging.handlers.QueueHandler(records)
    queue_handler.setLevel(level)
    _listener = logging.handlers.QueueListener(records, *handlers, respect_handler_level=True)
    _listener.start()

    root.setLevel(level)
    root.addHandler(queue_handler)
    if file_error is not None:
        logger.warning("Log file unavailable, logging to the console only: %s", file_error)
