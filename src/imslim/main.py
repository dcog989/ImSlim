import os
import sys
import sysconfig

try:
    import gettext

    gettext.install("imslim")
except ImportError:
    pass

from PySide6.QtCore import QUrl
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

from .window import ImSlimWindow

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


def _system_plugin_roots() -> list[str]:
    """Common system Qt plugin roots across distro layouts."""
    multiarch = sysconfig.get_config_var("MULTIARCH")
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


SOCKET_NAME = "imslim"


def _local_paths(argv) -> list[str]:
    paths = []
    for arg in argv[1:]:
        url = QUrl.fromUserInput(arg)
        path = url.toLocalFile() or arg
        if path:
            paths.append(path)
    return paths


class ImSlimApp(QApplication):
    def __init__(self, argv):
        _configure_platform_theme()
        super().__init__(argv)
        _extend_plugin_paths()
        self.setApplicationName("ImSlim")
        self.setOrganizationName("ImSlim")
        self.setApplicationDisplayName("ImSlim")
        self.win: ImSlimWindow | None = None
        self.server: QLocalServer | None = None
        self._conn_buffer: dict[QLocalSocket, bytearray] = {}

    def is_primary(self) -> bool:
        self.server = QLocalServer(self)
        self.server.removeServer(SOCKET_NAME)
        if self.server.listen(SOCKET_NAME):
            self.server.newConnection.connect(self._on_new_connection)
            return True
        return False

    def _on_new_connection(self):
        conn = self.server.nextPendingConnection()
        if conn is None:
            return
        self._conn_buffer[conn] = bytearray()
        conn.readyRead.connect(lambda: self._read_more(conn))
        conn.readChannelFinished.connect(lambda: self._finish_connection(conn))
        self._read_more(conn)

    def _read_more(self, conn):
        buffer = self._conn_buffer.get(conn)
        if buffer is None:
            return
        buffer.extend(bytes(conn.readAll()))

    def _finish_connection(self, conn):
        buffer = self._conn_buffer.get(conn)
        if buffer is None:
            return
        buffer.extend(bytes(conn.readAll()))
        self._conn_buffer.pop(conn, None)
        conn.disconnectFromServer()
        data = bytes(buffer)
        if not data:
            return
        paths = data.decode("utf-8").split("\0")
        if self.win is not None:
            self.win.show()
            self.win.raise_()
            self.win.activateWindow()
            self.win.compress_files(paths)

    def send_to_existing(self, paths) -> None:
        socket = QLocalSocket(self)
        socket.connectToServer(SOCKET_NAME)
        if not socket.waitForConnected(1000):
            return
        socket.write("\0".join(paths).encode("utf-8"))
        socket.waitForBytesWritten(500)
        socket.disconnectFromServer()

    def run(self):
        paths = _local_paths(sys.argv)

        if not self.is_primary():
            self.send_to_existing(paths)
            return 0

        self.win = ImSlimWindow(self)
        self.win.show()
        if paths:
            self.win.show_view("loading")
            self.win.compress_files(paths)

        self.win.check_version_update()
        return self.exec()


def main():
    app = ImSlimApp(sys.argv)
    sys.exit(app.run())


if __name__ == "__main__":
    main()
