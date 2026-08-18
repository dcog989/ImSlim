import html

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .release_notes import RELEASE_NOTES, release_notes_since


class WhatsNewDialog(QDialog):
    def __init__(self, version, last_version="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("What's New"))
        self.resize(420, 480)

        label = QLabel()
        label.setTextFormat(Qt.RichText)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        label.setText(self._build_markup(version, last_version))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        container = QVBoxLayout(content)
        container.addWidget(label)
        container.addStretch(1)
        scroll.setWidget(content)

        layout = QVBoxLayout(self)
        layout.addWidget(scroll)

    @staticmethod
    def _build_markup(current_version, last_version):
        notes = release_notes_since(last_version) if last_version else RELEASE_NOTES
        parts = []
        for release in notes:
            version = html.escape(release["version"])
            if release["version"] == current_version:
                header = f"<b><big>{version}</big></b>"
            else:
                header = f'<span style="font-size:small;">{version}</span>'
            changes = "\n".join(f"• {html.escape(change)}" for change in release["changes"])
            parts.append(f"{header}<br>{changes}")
        return "<br><br>".join(parts)
