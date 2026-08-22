import logging
import logging.handlers
from pathlib import Path

from .settings_manager import SettingsManager, log_file_path

_LOG_LEVELS: dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}
_LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"

# Last applied (log-level, log-max-size, log-backups); lets configure_logging()
# short-circuit when only unrelated settings changed.
_last_applied: tuple[str, int, int] | None = None


def configure_logging() -> None:
    """Install console and rotating-file handlers from the log settings.

    Re-entrant: runs at startup and again whenever the log settings change in
    the settings dialog, so those changes take effect without a restart. Any
    previously installed handlers are removed (file handlers closed) first;
    a level of NONE disables logging entirely.
    """
    global _last_applied

    settings = SettingsManager()
    config = (settings.log_level, settings.log_max_size, settings.log_backups)
    if config == _last_applied:
        return
    _last_applied = config

    root = logging.getLogger()
    for handler in root.handlers:
        root.removeHandler(handler)
        handler.close()
    root.setLevel(logging.WARNING)

    if settings.log_level == "NONE":
        return
    level = _LOG_LEVELS.get(settings.log_level, logging.INFO)

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

    root.setLevel(level)
    root.addHandler(file_handler)
    root.addHandler(console_handler)
