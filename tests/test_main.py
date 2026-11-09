import os
import sys
from pathlib import Path

import pytest

from imslim import main


def test_local_paths_ignores_the_now_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir("/")
    assert main._local_paths(["--now", "photo.png"]) == ["/photo.png"]  # pyright: ignore[reportPrivateUsage]


def test_local_paths_keeps_a_name_that_is_not_valid_utf8(tmp_path: Path) -> None:
    # QUrl.fromUserInput() drops undecodable bytes, so this used to become
    # "/photo_.png": a different file, or "doesn't exist".
    path = tmp_path / os.fsdecode(b"photo_\xff.png")
    path.write_bytes(b"x")

    assert main._local_paths([str(path)]) == [str(path)]  # pyright: ignore[reportPrivateUsage]


def test_has_display_reports_missing_session(monkeypatch: pytest.MonkeyPatch) -> None:
    if sys.platform == "win32":
        pytest.skip("Windows always has a display")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.delenv("DISPLAY", raising=False)
    assert not main._has_display()  # pyright: ignore[reportPrivateUsage]


def test_has_display_accepts_wayland(monkeypatch: pytest.MonkeyPatch) -> None:
    if sys.platform == "win32":
        pytest.skip("Windows always has a display")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    assert main._has_display()  # pyright: ignore[reportPrivateUsage]


def test_usage_documents_the_now_flag() -> None:
    assert "--now" in main._USAGE  # pyright: ignore[reportPrivateUsage]


def test_help_wins_over_now() -> None:
    assert main._info_request(["--now", "--help"]) is not None  # pyright: ignore[reportPrivateUsage]
