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
        super().__init__(argv)
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
