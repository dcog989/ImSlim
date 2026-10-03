from PySide6.QtCore import Qt, QUrl
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QWidget,
)

from .._i18n import _
from .._logging import LOG_LEVELS
from ..settings_manager import SettingsManager, log_file_path
from .style import separator
from .tab import SettingsTab

_LOG_LEVEL_LABELS = tuple(level.capitalize() for level in LOG_LEVELS)
_LOG_LEVEL_INDEX = {level: index for index, level in enumerate(LOG_LEVELS)}


class GeneralTab(SettingsTab):
    def __init__(self, settings: SettingsManager, parent: QWidget | None = None) -> None:
        super().__init__(settings, parent)
        self.combo_save_method: QComboBox = QComboBox()
        self.entry_output_folder: QLineEdit = QLineEdit()
        self.btn_output_folder: QPushButton = QPushButton()
        self.btn_clear_output_folder: QPushButton = QPushButton()
        self.entry_default_directory: QLineEdit = QLineEdit()
        self.btn_default_directory: QPushButton = QPushButton()
        self.btn_clear_default_directory: QPushButton = QPushButton()
        self.check_recursive: QCheckBox = QCheckBox()
        self.spin_timeout: QSpinBox = QSpinBox()
        self.combo_log_level: QComboBox = QComboBox()
        self.spin_log_max_size: QSpinBox = QSpinBox()
        self.spin_log_backups: QSpinBox = QSpinBox()
        self._build()
        with self._suspend_signals():
            self._load_values()

    def _build(self) -> None:
        form = QFormLayout(self)
        form.setContentsMargins(16, 16, 16, 16)
        form.setVerticalSpacing(16)

        self.combo_save_method.addItems(
            [_("Save to a new file"), _("Save to original after backup")]
        )

        self.entry_output_folder.setPlaceholderText(_("Same folder as the original files"))

        self.btn_output_folder.setText(_("Browse…"))
        self.btn_output_folder.clicked.connect(self._browse_output_folder)

        self.btn_clear_output_folder.setText("✕")
        self.btn_clear_output_folder.setToolTip(_("Clear the output folder"))
        self.btn_clear_output_folder.setFixedWidth(36)
        self.btn_clear_output_folder.setStyleSheet("QPushButton { padding: 6px 10px; }")
        self.btn_clear_output_folder.clicked.connect(self._clear_output_folder)

        output_row = QHBoxLayout()
        output_row.addWidget(self.entry_output_folder, 1)
        output_row.addWidget(self.btn_output_folder)
        output_row.addWidget(self.btn_clear_output_folder)

        self.entry_default_directory.setPlaceholderText(_("User's home directory"))

        self.btn_default_directory.setText(_("Browse…"))
        self.btn_default_directory.clicked.connect(self._browse_default_directory)

        self.btn_clear_default_directory.setText("✕")
        self.btn_clear_default_directory.setToolTip(_("Clear the default open directory"))
        self.btn_clear_default_directory.setFixedWidth(36)
        self.btn_clear_default_directory.setStyleSheet("QPushButton { padding: 6px 10px; }")
        self.btn_clear_default_directory.clicked.connect(self._clear_default_directory)

        default_directory_row = QHBoxLayout()
        default_directory_row.addWidget(self.entry_default_directory, 1)
        default_directory_row.addWidget(self.btn_default_directory)
        default_directory_row.addWidget(self.btn_clear_default_directory)

        self.check_recursive.setText(_("Compress sub-directories"))
        self.check_recursive.toggled.connect(self._bool_handler("recursive"))

        self.spin_timeout.setRange(1, 300)
        self.spin_timeout.setSuffix("s")
        self.spin_timeout.setToolTip(
            _(
                "Maximum seconds a single compression tool may run on one image "
                + "before it is stopped. Raise this for very large or slow-to-compress "
                + "images (e.g. AVIF); lower it to fail faster on unresponsive tools."
            )
        )

        form.addRow(_("Save Method"), self.combo_save_method)
        form.addRow(_("Output Folder"), output_row)
        form.addRow(_("Open Dialog Directory"), default_directory_row)
        form.addRow(_("Directory Recurse"), self.check_recursive)
        form.addRow(_("Compression Timeout"), self.spin_timeout)

        form.addRow(separator())

        self.combo_log_level.addItems([_(label) for label in _LOG_LEVEL_LABELS])
        self.combo_log_level.setToolTip(
            _("Verbosity of the log file. Debug includes the exact commands run.")
        )

        self.spin_log_max_size.setRange(1, 100)
        self.spin_log_max_size.setSuffix(" MB")
        self.spin_log_max_size.setToolTip(_("Maximum size of the log file before it is rotated."))

        self.spin_log_backups.setRange(1, 20)
        self.spin_log_backups.setToolTip(
            _("Number of rotated log files to keep alongside the current one.")
        )

        form.addRow(_("Log Level"), self.combo_log_level)
        form.addRow(_("Log Max Size"), self.spin_log_max_size)
        form.addRow(_("Log Backups"), self.spin_log_backups)
        form.addRow(self._build_log_link())

        self.combo_save_method.currentIndexChanged.connect(self._on_save_method_changed)
        self.entry_output_folder.textChanged.connect(self._on_output_folder_changed)
        self.entry_default_directory.textChanged.connect(self._on_default_directory_changed)
        self.spin_timeout.valueChanged.connect(self._int_handler("compression-timeout"))
        self.combo_log_level.currentIndexChanged.connect(self._on_log_level_changed)
        self.spin_log_max_size.valueChanged.connect(self._int_handler("log-max-size"))
        self.spin_log_backups.valueChanged.connect(self._int_handler("log-backups"))

    @staticmethod
    def _build_log_link() -> QLabel:
        label = QLabel()
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setOpenExternalLinks(True)
        url = QUrl.fromLocalFile(log_file_path()).toString()
        label.setText('<a href="{}">{}</a>'.format(url, _("Open the latest log file")))
        return label

    def _load_values(self) -> None:
        s = self.settings
        self.combo_save_method.setCurrentIndex(s.save_method)
        self.entry_output_folder.setText(s.output_folder)
        self.entry_default_directory.setText(s.default_open_dialog_directory)
        self.spin_timeout.setValue(s.compression_timeout)
        log_level = s.log_level if s.log_level in _LOG_LEVEL_INDEX else "INFO"
        self.combo_log_level.setCurrentIndex(_LOG_LEVEL_INDEX[log_level])
        self._set_log_controls_state(log_level)
        self.spin_log_max_size.setValue(s.log_max_size)
        self.spin_log_backups.setValue(s.log_backups)
        self.check_recursive.setChecked(s.recursive)

    def _on_save_method_changed(self, index: int) -> None:
        self.settings.save_method = index
        self.settings_changed.emit()

    def _on_output_folder_changed(self, text: str) -> None:
        self.settings.output_folder = text.strip()
        self.settings_changed.emit()

    def _on_default_directory_changed(self, text: str) -> None:
        self.settings.default_open_dialog_directory = text.strip()
        self.settings_changed.emit()

    def _browse_default_directory(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            _("Select Default Open Dialog Directory"),
            self.entry_default_directory.text() or "",
        )
        if folder:
            self.entry_default_directory.setText(folder)

    def _clear_default_directory(self) -> None:
        self.entry_default_directory.setText("")

    def _browse_output_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            _("Select Output Folder"),
            self.entry_output_folder.text() or "",
        )
        if folder:
            self.entry_output_folder.setText(folder)

    def _clear_output_folder(self) -> None:
        self.entry_output_folder.setText("")

    def _on_log_level_changed(self, index: int) -> None:
        self.settings.log_level = LOG_LEVELS[index]
        self._set_log_controls_state(LOG_LEVELS[index])
        self.settings_changed.emit()

    def _set_log_controls_state(self, level: str) -> None:
        enabled = level != "NONE"
        self.spin_log_max_size.setEnabled(enabled)
        self.spin_log_backups.setEnabled(enabled)
