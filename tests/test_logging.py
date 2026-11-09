import logging
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
