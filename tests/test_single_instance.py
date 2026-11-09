import time
import uuid
from collections.abc import Callable

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtNetwork import QLocalServer

from imslim.main import SingleInstance


def _unique_name() -> str:
    return f"imslim-test-{uuid.uuid4().hex}"


def _wait_for(predicate: Callable[[], bool], timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    return False


def _primary(name: str, received: list[list[str]]) -> SingleInstance:
    primary = SingleInstance(name, received.append)
    assert primary.become_primary([])
    return primary


def _close(primary: SingleInstance) -> None:
    # The accepted sockets are deleted with deleteLater(); run those deletes
    # while the server still owns them, before the test drops the server.
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert primary._server is not None  # pyright: ignore[reportPrivateUsage]
    primary._server.close()  # pyright: ignore[reportPrivateUsage]
    QLocalServer.removeServer(primary._socket)  # pyright: ignore[reportPrivateUsage]


def test_second_instance_forwards_its_paths() -> None:
    received: list[list[str]] = []
    name = _unique_name()
    primary = _primary(name, received)
    try:
        second = SingleInstance(name, lambda _paths: None)
        assert not second.become_primary(["/tmp/a.png", "/tmp/b.png"])
        assert _wait_for(lambda: received == [["/tmp/a.png", "/tmp/b.png"]])
    finally:
        _close(primary)


def test_bare_relaunch_forwards_no_paths() -> None:
    received: list[list[str]] = []
    name = _unique_name()
    primary = _primary(name, received)
    try:
        second = SingleInstance(name, lambda _paths: None)
        assert not second.become_primary([])
        assert _wait_for(lambda: received == [[]])
    finally:
        _close(primary)
