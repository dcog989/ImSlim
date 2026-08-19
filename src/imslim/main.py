import os
import sys

try:
    import gettext

    gettext.install("imslim")
except Exception:
    pass

from PySide6.QtCore import QUrl
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

from .window import ImSlimWindow

# Native-desktop integration comes from a Qt platform theme plugin read during
# QApplication construction, so pick one before the app object is built.
# Preferred is the desktop's own theme (e.g. KDE plasma-integration, which is
# loaded once the system plugin paths are added below). Fall back to the
# freedesktop portal, which forwards file dialogs to the desktop's native
# picker via xdg-desktop-portal, unless the user pinned a specific theme.
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
    default makes native dialogs work regardless, while letting an explicit
    QT_QPA_PLATFORMTHEME win.
    """
    if os.environ.get(_PLATFORM_THEME_ENV):
        return
    os.environ[_PLATFORM_THEME_ENV] = _PORTAL_THEME


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
    for root in ("/usr/lib/qt6/plugins", "/usr/lib/qt/plugins"):
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
        conn.readyRead.connect(lambda: self._read_connection(conn))

    def _read_connection(self, conn):
        data = bytes(conn.readAll())
        conn.disconnectFromServer()
        if not data:
            return
        paths = data.decode("utf-8").split("\n")
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
        socket.write("\n".join(paths).encode("utf-8"))
        socket.waitForBytesWritten(500)
        socket.disconnectFromServer()

    def run(self):
        paths = _local_paths(sys.argv)

        if not self.is_primary():
            self.send_to_existing(paths)
            return 0

        self.win = ImSlimWindow(self)
        if paths:
            self.win.show_view("loading")
            self.win.compress_files(paths)
        else:
            self.win.show()

        self.win.check_version_update()
        return self.exec()


def main():
    app = ImSlimApp(sys.argv)
    sys.exit(app.run())


if __name__ == "__main__":
    main()
