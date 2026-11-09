"""The per-file context menu shared by the queue list and the thumbnail grid."""

import os

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QGuiApplication
from PySide6.QtWidgets import QMenu, QWidget

from ._i18n import _
from .properties import PropertiesDialog
from .result_item import ResultItem, ResultState
from .theme import style_menu


def build_item_menu(item: ResultItem, parent: QWidget) -> QMenu:
    """Menu for one queued file; callers position and exec it."""
    menu = QMenu(parent)
    style_menu(menu)
    compressed = bool(item.new_filename) and os.path.exists(item.new_filename)
    original = bool(item.filename) and os.path.exists(item.filename)

    if compressed:
        open_image = QAction(_("Open Image"), menu)
        _res = open_image.triggered.connect(lambda: _open_path(item.new_filename))
        show_in_folder = QAction(_("Show in Folder"), menu)
        _res = show_in_folder.triggered.connect(
            lambda: _open_path(os.path.dirname(item.new_filename))
        )
        menu.addAction(open_image)
        menu.addAction(show_in_folder)
        _res = menu.addSeparator()

    copy_path = QAction(_("Copy File Path"), menu)
    copy_path.setEnabled(bool(item.filename))
    _res = copy_path.triggered.connect(lambda: QGuiApplication.clipboard().setText(item.filename))
    menu.addAction(copy_path)

    if original:
        properties = QAction(_("Properties…"), menu)
        _res = properties.triggered.connect(lambda: _show_properties(item, parent))
        menu.addAction(properties)
        _res = menu.addSeparator()
        show_original = QAction(_("Show Original in Folder"), menu)
        _res = show_original.triggered.connect(lambda: _open_path(os.path.dirname(item.filename)))
        menu.addAction(show_original)

    if item.state is ResultState.ERROR and item.error_details_message:
        copy_error = QAction(_("Copy Error Details"), menu)
        _res = copy_error.triggered.connect(
            lambda: QGuiApplication.clipboard().setText(item.error_details_message)
        )
        menu.addAction(copy_error)

    return menu


def _open_path(path: str) -> None:
    if path:
        _res = QDesktopServices.openUrl(QUrl.fromLocalFile(path))


def _show_properties(item: ResultItem, parent: QWidget) -> None:
    dialog = PropertiesDialog(item, parent)
    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    dialog.show()
