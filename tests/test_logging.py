import logging
import os
import time
from datetime import date, timedelta
from pathlib import Path

from imslim._logging import _DailyRotatingFileHandler


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
