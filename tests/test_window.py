"""The window's preview bookkeeping: only the newest selection reaches the pane."""

from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from imslim.batch_flow import BatchFlow
from imslim.composition import AppContext
from imslim.result_item import ResultItem, ResultState
from imslim.settings_manager import SettingsManager
from imslim.window import ImSlimWindow


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point QSettings at a throwaway file so the window never touches the real config."""
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))

    class _ScopedSettings(QSettings):
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            super().__init__(
                QSettings.Format.IniFormat, QSettings.Scope.UserScope, "ImSlim", "ImSlim"
            )

    monkeypatch.setattr("imslim.settings_manager.QSettings", _ScopedSettings)


class _Manager:
    """A compression manager that never starts a batch."""

    def compress(self, *_args: object) -> None:
        raise AssertionError("a preview test must not start a batch")

    def cancel(self) -> None:
        pass

    def shutdown(self) -> None:
        pass


def _window(app: QApplication) -> ImSlimWindow:
    settings = SettingsManager()
    flow = BatchFlow(settings, _Manager())  # type: ignore[arg-type]
    return ImSlimWindow(app, AppContext(settings=settings, flow=flow))


def test_a_cancelled_preview_cannot_replace_the_new_selection(
    _qt_app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started: list[object] = []
    monkeypatch.setattr("imslim.window.start_task", started.append)
    # Decoding the source itself is not what this test checks.
    monkeypatch.setattr("imslim.compare_view.start_task", lambda _task: None)
    window = _window(_qt_app)
    try:
        first = ResultItem(filename=str(tmp_path / "a.png"), mime_type="image/png", size=10)
        second = ResultItem(filename=str(tmp_path / "b.png"), mime_type="image/png", size=10)

        window._on_selection_changed(first)
        window._start_preview()
        stale_token = window._preview_token
        assert started

        # The user moves on before the first preview lands; its token is void.
        window._on_selection_changed(second)
        stale_result = ResultItem(
            filename=first.filename,
            new_filename=str(tmp_path / "preview.png"),
            state=ResultState.DONE,
            size=10,
            new_size=5,
        )
        window._on_preview_ready(stale_token, stale_result)

        assert window.compare.processed_path.text() == ""
    finally:
        window.close()
        window.deleteLater()
