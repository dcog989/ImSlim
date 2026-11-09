import logging
import os
import time
from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path

import pytest

from imslim import _logging
from imslim._logging import _DailyRotatingFileHandler


class _Settings:
    def __init__(self, level: str = "INFO") -> None:
        self.log_level = level
        self.log_max_size = 1
        self.log_backups = 2


@pytest.fixture(autouse=True)
def _restore_logging() -> Iterator[None]:
    """Undo configure_logging's edits to the shared root logger after each test."""
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    yield
    _logging._stop_listener()
    _logging._listener = None
    for handler in root.handlers[:]:
        if handler not in saved_handlers:
            root.removeHandler(handler)
            handler.close()
    for handler in saved_handlers:
        if handler not in root.handlers:
            root.addHandler(handler)
    root.setLevel(saved_level)


def test_none_level_stays_silent(capsys: pytest.CaptureFixture[str]) -> None:
    _logging.configure_logging(_Settings("NONE"))  # type: ignore[arg-type]
    logging.getLogger("imslim-test-none").warning("must not reach stderr")
    assert capsys.readouterr().err == ""


def test_unwritable_log_dir_keeps_console_logging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    if os.geteuid() == 0:
        pytest.skip("root can write into a 0500 directory")
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    blocked.chmod(0o500)
    monkeypatch.setattr(_logging, "log_file_path", lambda name="imslim.log": str(blocked / name))

    _logging.configure_logging(_Settings())  # type: ignore[arg-type]
    logging.getLogger("imslim-test-fallback").warning("console still works")
    _logging._stop_listener()
    _logging._listener = None
    assert "console still works" in capsys.readouterr().err


def test_rotates_on_new_day(tmp_path: Path) -> None:
    log_path = tmp_path / "imslim.log"
    handler = _DailyRotatingFileHandler(str(log_path), max_bytes=1024 * 1024, backup_count=9)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger = logging.getLogger("imslim-test-daily")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    try:
        logger.info("first")
        # Pretend the last rollover happened yesterday: the next record must roll.
        handler._day = date.today() - timedelta(days=1)
        logger.info("second")
    finally:
        logger.removeHandler(handler)
        handler.close()

    assert (tmp_path / "imslim.log.1").exists()


def test_rotates_a_file_left_by_an_earlier_day(tmp_path: Path) -> None:
    log_path = tmp_path / "imslim.log"
    log_path.write_text("old\n")
    old = time.time() - 2 * 24 * 60 * 60
    os.utime(log_path, (old, old))
    handler = _DailyRotatingFileHandler(str(log_path), max_bytes=1024 * 1024, backup_count=9)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger = logging.getLogger("imslim-test-old-day")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    try:
        logger.info("new")
    finally:
        logger.removeHandler(handler)
        handler.close()

    assert "new" in log_path.read_text()
    assert "old" in (tmp_path / "imslim.log.1").read_text()
