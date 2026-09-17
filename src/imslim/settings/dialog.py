from typing import cast, override

from PySide6.QtCore import Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTabWidget, QVBoxLayout, QWidget

from .._i18n import _
from ..settings_manager import SettingsManager
from .about_tab import AboutTab
from .formats_tab import FormatsTab
from .general_tab import GeneralTab
from .style import form_stylesheet


class SettingsDialog(QDialog):
    settings_changed: Signal = Signal()

    def __init__(self, settings: SettingsManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("Settings"))
        self.settings: SettingsManager = settings
        self.setStyleSheet(form_stylesheet())

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        self.general_tab = GeneralTab(settings)
        self.formats_tab = FormatsTab(settings)
        self.about_tab = AboutTab(settings)
        tabs.addTab(self.general_tab, _("General"))
        tabs.addTab(self.formats_tab, _("Formats"))
        self._about_index = tabs.addTab(self.about_tab, _("About"))
        tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)

        self.general_tab.settings_changed.connect(self.settings_changed.emit)
        self.formats_tab.settings_changed.connect(self.settings_changed.emit)

    def _on_tab_changed(self, index: int) -> None:
        if index == self._about_index:
            self.about_tab.populate()

    @override
    def closeEvent(self, event: object) -> None:
        # Settings are written live by each tab; closing only needs to flush.
        self.settings.sync()
        super().closeEvent(cast(QCloseEvent, event))
