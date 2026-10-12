import logging
import os
import sys
import sysconfig
import time
from collections.abc import Callable
from typing import cast

from PySide6.QtCore import QLockFile, QObject, QStandardPaths, QTimer, QUrl
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

from . import __version__
from ._i18n import _
from ._logging import configure_logging
from .binary_resolver import KNOWN_TOOLS, resolve_tool
from .composition import build_app_context
from .system_info import static_about_pairs, system_info_pairs
from .window import ImSlimWindow

logger = logging.getLogger(__name__)

# Native-desktop integration comes from a Qt platform theme plugin read during
# QApplication construction, so pick one before the app object is built.
# With a bundled PySide6 the desktop's plugin (e.g. KDE plasma-integration)
# often can't load, so in a graphical desktop session the freedesktop portal
# theme is the default: it forwards file dialogs to the desktop's native
# picker via xdg-desktop-portal. An explicit QT_QPA_PLATFORMTHEME always wins.
_PLATFORM_THEME_ENV = "QT_QPA_PLATFORMTHEME"
_PORTAL_THEME = "xdgdesktopportal"


def _configure_platform_theme() -> None:
    """Ensure a native-capable Qt platform theme is selected on startup.

    With a bundled PySide6, Qt only looks in the wheel's plugin directory, so
    the desktop's platform theme (e.g. KDE plasma-integration) is missing and
    QFileDialog falls back to Qt's own dialog. Qt runs the platform theme name
    when XDG_CURRENT_DESKTOP lists KDE, but if that theme can't load (e.g. the
    bundled Qt's private-API version no longer matches the system theme), Qt
    silently falls back to no native dialogs. Setting the portal theme as the
    default in desktop sessions makes native dialogs work regardless, while
    letting an explicit QT_QPA_PLATFORMTHEME win.
    """
    if os.environ.get(_PLATFORM_THEME_ENV):
        return
    # Only force the portal inside a graphical desktop session; without one
    # (bare X11, CI, ssh -X) no portal exists and Qt would warn about a
    # missing platform theme before falling back to its own dialog.
    if not os.environ.get("XDG_CURRENT_DESKTOP"):
        return
    os.environ[_PLATFORM_THEME_ENV] = _PORTAL_THEME


def _log_startup() -> None:
    """Record a session opener so the log is never empty just from launching."""
    logger.info("ImSlim %s starting", __version__)
    if not logger.isEnabledFor(logging.DEBUG):
        return
    for label, value in (*static_about_pairs(), *system_info_pairs()):
        logger.debug("%s: %s", label, value)
    for tool in KNOWN_TOOLS:
        try:
            path = resolve_tool(tool)
        except OSError as err:
            logger.debug("%s: unavailable (%s)", tool, err)
        else:
            logger.debug("%s: %s", tool, path)


def _system_plugin_roots() -> list[str]:
    """Common system Qt plugin roots across distro layouts."""
    multiarch = cast(str | int | None, sysconfig.get_config_var("MULTIARCH"))
    roots = [
        "/usr/lib64/qt6/plugins",
        "/usr/lib/qt6/plugins",
        "/usr/lib64/qt/plugins",
        "/usr/lib/qt/plugins",
    ]
    if multiarch:
        roots.insert(0, f"/usr/lib/{multiarch}/qt6/plugins")
    return roots


def _extend_plugin_paths() -> None:
    """Push the system Qt plugin roots ahead of PySide6's bundled ones.

    When the app bundles its own PySide6, Qt only searches the wheel's plugin
    directory, so platform theme plugins shipped with the desktop (e.g. KDE's
    plasma-integration) and the native style plugins are never found. Each
    entry in the plugin path is a root whose <type> subdir is scanned, so the
    system plugin root itself is what must be inserted; the bundled root is
    left on the path as a fallback. Plugin paths are read lazily, so this may
    run after the QApplication is constructed.
    """
    current = QApplication.libraryPaths()
    for root in _system_plugin_roots():
        if root not in current:
            current.insert(0, root)
    QApplication.setLibraryPaths(current)


_APP_NAME = "ImSlim"
SOCKET_NAME = _APP_NAME.lower()
_CONNECT_TIMEOUT_MS = 1000
_WRITE_TIMEOUT_MS = 500
# Stale-connection sweep: a client that connects but never sends data (and so
# never triggers readChannelFinished) must not hold a buffer entry forever.
_SWEEP_INTERVAL_MS = 5000
_IDLE_TIMEOUT_MS = 10000
# Cap how much data one connection may buffer: a same-user local process could
# otherwise stream without end and grow the app's memory until the sweep fires.
# A real launch sends newline-free, \0-separated paths, so a few MB is ample.
_MAX_PAYLOAD_BYTES = 4 * 1024 * 1024
# A launch that lost the primary race waits this long for the winner's socket,
# which appears a few statements after it takes the lock.
_PRIMARY_WAIT_SECONDS = 2.0
_PRIMARY_POLL_SECONDS = 0.05
# Never block on the primary lock: a held lock means another launch owns the app.
_LOCK_TIMEOUT_MS = 0

_USAGE = _(
    """Usage: imslim [FILES...]

Compress image files and folders. Without any files the main window opens.

  -h, --help     Show this help and exit.
  -V, --version  Show the version and exit."""
)


def _info_request(argv: list[str]) -> str | None:
    """Text to print for the informational flags, or None to open the UI."""
    if any(arg in ("-h", "--help") for arg in argv):
        return _USAGE
    if any(arg in ("-V", "--version") for arg in argv):
        return f"{_APP_NAME} {__version__}"
    return None


def _local_paths(argv: list[str]) -> list[str]:
    """Local paths from the command line, ignoring options."""
    paths: list[str] = []
    for arg in argv:
        # Options are not paths: passing "-x" on would report "This file doesn't
        # exist." for a file named "-x".
        if arg.startswith("-"):
            continue
        url = QUrl.fromUserInput(arg)
        path = url.toLocalFile() or arg
        if path:
            paths.append(path)
    return paths


def _socket_name(name: str) -> str:
    """Resolve the single-instance socket to a per-user private location.

    Prefer $XDG_RUNTIME_DIR (mode 0700) over a predictable file in shared /tmp.
    When it is unavailable, fall back to the temp dir with the uid in the name
    so different users cannot collide. Windows named pipes keep the plain name.
    """
    if sys.platform == "win32":
        return name
    runtime = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.RuntimeLocation)
    if runtime:
        return os.path.join(runtime, name)
    temp = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.TempLocation)
    return os.path.join(temp, f"{name}-{os.getuid()}")


def _lock_path(name: str) -> str:
    """Path of the lock file that serializes the primary decision."""
    if sys.platform == "win32":
        # The socket is a named pipe, not a path, so anchor the lock in temp.
        temp = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.TempLocation)
        return os.path.join(temp, f"{name}.lock")
    return f"{_socket_name(name)}.lock"


class SingleInstance(QObject):
    """Single-instance gate over a local socket.

    The first process becomes the primary and listens on a named socket;
    later processes forward their command-line paths to it, which the primary
    delivers through the `on_paths` callback. An exclusive lock file makes the
    primary decision atomic, so two simultaneous launches cannot both call
    QLocalServer.removeServer() and unlink each other's socket. A background
    sweep reaps connections that connect but never send data, so a hung or
    malformed client cannot accumulate buffer entries indefinitely; a connection
    whose buffered payload passes _MAX_PAYLOAD_BYTES is dropped outright.
    """

    def __init__(self, name: str, on_paths: Callable[[list[str]], None]) -> None:
        super().__init__()
        self._socket: str = _socket_name(name)
        self._lock: QLockFile = QLockFile(_lock_path(name))
        self._on_paths: Callable[[list[str]], None] = on_paths
        self._server: QLocalServer | None = None
        self._conn_buffer: dict[QLocalSocket, bytearray] = {}
        self._conn_started: dict[QLocalSocket, float] = {}
        self.is_primary: bool = False

        self._sweep_timer: QTimer = QTimer(self)
        self._sweep_timer.setInterval(_SWEEP_INTERVAL_MS)
        _res = self._sweep_timer.timeout.connect(self._sweep_stale_connections)

    def become_primary(self, paths: list[str]) -> bool:
        """Become the primary listener, or forward `paths` to the running one.

        Returns False when another instance accepted the paths, so the caller
        should exit. If the gate cannot be taken but nobody answers, this still
        listens rather than leaving the user with no window at all.
        """
        if self.send_paths(paths):
            return False
        # A lock file serializes the decision: without it two launches that both
        # miss a running primary would each removeServer() the other's socket.
        # QLockFile also clears a lock file left behind by a crashed instance.
        if not self._lock.tryLock(_LOCK_TIMEOUT_MS):
            # Another launch won the race and owns the primary role. Its server
            # may not be up yet, so wait for it before listening, which would
            # unlink its socket.
            if self._forward_when_ready(paths):
                return False
            logger.warning("Primary instance is not answering; listening anyway")
        self._server = QLocalServer()
        _res = self._server.removeServer(self._socket)
        self.is_primary = self._server.listen(self._socket)
        if self.is_primary:
            _res = self._server.newConnection.connect(self._on_new_connection)
        else:
            logger.warning("Could not listen on %s; continuing without it", self._socket)
        return True

    def _forward_when_ready(self, paths: list[str]) -> bool:
        """Forward `paths` once the primary's server is up.

        Polls because QLocalSocket gives up immediately when the socket file is
        missing, so waitForConnected cannot span the winner's startup.
        """
        deadline = time.monotonic() + _PRIMARY_WAIT_SECONDS
        while True:
            if self.send_paths(paths):
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(_PRIMARY_POLL_SECONDS)

    def send_paths(self, paths: list[str]) -> bool:
        socket = QLocalSocket()
        socket.connectToServer(self._socket)
        if not socket.waitForConnected(_CONNECT_TIMEOUT_MS):
            return False
        _res = socket.write("\0".join(paths).encode("utf-8"))
        _res = socket.waitForBytesWritten(_WRITE_TIMEOUT_MS)
        socket.disconnectFromServer()
        return True

    def _on_new_connection(self) -> None:
        if self._server is None:
            return
        conn = cast(QLocalSocket | None, self._server.nextPendingConnection())
        if conn is None:
            return
        self._conn_buffer[conn] = bytearray()
        self._conn_started[conn] = time.monotonic()
        _res = conn.readyRead.connect(lambda: self._read_more(conn))
        _res = conn.readChannelFinished.connect(lambda: self._finish(conn))
        # Sweep only while connections are pending, so an idle primary holds no
        # recurring timer.
        if not self._sweep_timer.isActive():
            self._sweep_timer.start()
        self._read_more(conn)

    def _read_more(self, conn: QLocalSocket) -> None:
        buffer = self._conn_buffer.get(conn)
        if buffer is None:
            return
        buffer.extend(conn.readAll().data())
        if len(buffer) > _MAX_PAYLOAD_BYTES:
            logger.warning("Dropping connection with oversized payload (%d bytes)", len(buffer))
            self._drop_connection(conn)

    def _drop_connection(self, conn: QLocalSocket) -> None:
        """Stop tracking a connection, disconnect it and schedule its deletion."""
        _res = self._conn_buffer.pop(conn, None)
        _res = self._conn_started.pop(conn, None)
        conn.disconnectFromServer()
        conn.deleteLater()
        if not self._conn_started:
            self._sweep_timer.stop()

    def _finish(self, conn: QLocalSocket) -> None:
        buffer = self._conn_buffer.get(conn)
        if buffer is None:
            return
        buffer.extend(conn.readAll().data())
        self._drop_connection(conn)
        data = bytes(buffer)
        paths = data.decode("utf-8").split("\0") if data else []
        self._on_paths(paths)

    def _sweep_stale_connections(self) -> None:
        now = time.monotonic()
        for conn, started in list(self._conn_started.items()):
            if (now - started) * 1000 <= _IDLE_TIMEOUT_MS:
                continue
            self._drop_connection(conn)


class ImSlimApp(QApplication):
    def __init__(self, argv: list[str]) -> None:
        _configure_platform_theme()
        super().__init__(argv)
        _extend_plugin_paths()
        self.setApplicationName(_APP_NAME)
        self.setOrganizationName(_APP_NAME)
        self.setApplicationDisplayName(_APP_NAME)
        # Wayland matches a toplevel to installed .desktop files by name to pick
        # the dock icon and title; without this Qt falls back to the executable
        # basename, which never matches imslim.desktop. On X11 the same value
        # becomes WM_CLASS.
        self.setDesktopFileName(SOCKET_NAME)
        self.win: ImSlimWindow | None = None

    def run(self) -> int:
        paths = _local_paths(self.arguments()[1:])
        single = SingleInstance(SOCKET_NAME, self._on_foreign_paths)
        if not single.become_primary(paths):
            return 0

        # Only the primary process owns the log file; a forwarded launch must
        # not open (or rotate) the same file out from under it.
        configure_logging()
        _log_startup()

        self.win = ImSlimWindow(self, build_app_context())
        self.win.show()
        if paths:
            self.win.compress_files(paths)

        return self.exec()

    def _on_foreign_paths(self, paths: list[str]) -> None:
        if self.win is None:
            return
        # A bare relaunch forwards no paths; focus the existing window either way.
        self.win.show()
        self.win.raise_()
        self.win.activateWindow()
        if paths:
            self.win.compress_files(paths)


def main() -> None:
    info = _info_request(sys.argv[1:])
    if info is not None:
        # Answer before building QApplication: these must work where no window
        # could open at all (ssh, cron, a missing display).
        print(info)
        sys.exit(0)
    app = ImSlimApp(sys.argv)
    sys.exit(app.run())


if __name__ == "__main__":
    main()
