import os

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session", autouse=True)
def _qt_app() -> QApplication:
    """One application for the whole run: widget tests need QApplication, not QGuiApplication."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    assert isinstance(app, QApplication)
    return app


@pytest.fixture(autouse=True)
def _stub_tool_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    """Resolve every bundled tool to its bare name.

    Compressor tests assert exact argv, which must not depend on whether the
    binaries were built on this host (CI has none) or are on PATH. `resolve_tool`
    calls this module-level `_resolve`, so one patch covers every compressor.
    """
    monkeypatch.setattr("imslim.binary_resolver._resolve", lambda name: name)
