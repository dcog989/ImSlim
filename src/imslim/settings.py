from collections.abc import Callable
from typing import cast, override

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QCloseEvent, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from ._i18n import _
from .settings_manager import SettingsManager, log_file_path
from .system_info import static_about_pairs, system_info_pairs
from .widgets import apply_muted_palette, combo_stylesheet, imslim_icon, input_background_color
from .workers import VersionProbeWorker

_LOG_LEVELS = ("NONE", "DEBUG", "INFO", "WARNING", "ERROR")
_LOG_LEVEL_LABELS = ("None", "Debug", "Info", "Warning", "Error")


def _separator() -> QFrame:
    """A 28px-tall horizontal divider whose line color is derived from the
    palette. A plain QFrame HLine draws with the WindowText role, which on
    dark themes is near-white, so the line is recolored to a subtle muted tone
    instead.
    """
    separator = QFrame()
    separator.setFrameShape(QFrame.Shape.HLine)
    separator.setFixedHeight(28)
    apply_muted_palette(
        separator,
        factor=0.6,
        fg_role=QPalette.ColorRole.WindowText,
        bg_role=QPalette.ColorRole.Window,
    )
    return separator


def _form_stylesheet() -> str:
    """Stylesheet for the settings form.

    Input backgrounds are derived from the live palette: some dark schemes
    give input fields a Base darker than the surrounding window, which renders
    as near-black holes. Those fields are lifted just above the window color
    so text stays readable; light themes keep their Base untouched.
    """
    input_bg = input_background_color()
    return (
        combo_stylesheet()
        + f"QSpinBox {{ padding: 0px 6px; min-height: 22px; background-color: {input_bg}; }}"
        + f"QLineEdit {{ padding: 5px 10px; background-color: {input_bg}; }}"
        + "QPushButton { padding: 6px 16px; }"
        + "QCheckBox, QRadioButton { spacing: 8px; }"
    )


class SettingsDialog(QDialog):
    settings_changed: Signal = Signal()

    def __init__(self, settings: SettingsManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("Settings"))
        self.settings: SettingsManager = settings
        self._format_spins: list[tuple[QSpinBox, str]] = []
        self._format_checks: list[tuple[QCheckBox, str]] = []
        self._radio_pairs: list[tuple[QRadioButton, QRadioButton, str]] = []
        self.combo_save_method: QComboBox = QComboBox()
        self.entry_output_folder: QLineEdit = QLineEdit()
        self.btn_output_folder: QPushButton = QPushButton()
        self.btn_clear_output_folder: QPushButton = QPushButton()
        self.entry_default_directory: QLineEdit = QLineEdit()
        self.btn_default_directory: QPushButton = QPushButton()
        self.btn_clear_default_directory: QPushButton = QPushButton()
        self.radio_recursive: QWidget = QWidget()
        self.spin_timeout: QSpinBox = QSpinBox()
        self.combo_log_level: QComboBox = QComboBox()
        self.spin_log_max_size: QSpinBox = QSpinBox()
        self.spin_log_backups: QSpinBox = QSpinBox()
        self._about_tool_pairs: list[tuple[str, str]] = []
        self._about_index: int = 0
        self._about_populated: bool = False
        self.build_ui()

    def build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.setStyleSheet(_form_stylesheet())

        tabs = QTabWidget()
        _res = tabs.addTab(self._build_general_tab(), _("General"))
        _res = tabs.addTab(self._build_formats_tab(), _("Formats"))
        self._about_index = tabs.addTab(self._build_about_tab(), _("About"))
        layout.addWidget(tabs)
        _res = tabs.currentChanged.connect(self._on_tab_changed)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        _res = buttons.rejected.connect(self.close)
        layout.addWidget(buttons)

        self._load_values()

    def _build_general_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setContentsMargins(16, 16, 16, 16)
        form.setVerticalSpacing(16)

        self.combo_save_method = QComboBox()
        self.combo_save_method.addItems(
            [_("Save to a new file"), _("Save to original after backup")]
        )

        self.entry_output_folder = QLineEdit()
        self.entry_output_folder.setPlaceholderText(_("Same folder as the original files"))

        self.btn_output_folder = QPushButton(_("Browse…"))
        _res = self.btn_output_folder.clicked.connect(self.on_browse_output_folder)

        self.btn_clear_output_folder = QPushButton("✕")
        self.btn_clear_output_folder.setToolTip(_("Clear the output folder"))
        self.btn_clear_output_folder.setFixedWidth(36)
        self.btn_clear_output_folder.setStyleSheet("QPushButton { padding: 6px 10px; }")
        _res = self.btn_clear_output_folder.clicked.connect(self.on_clear_output_folder)

        output_row = QHBoxLayout()
        output_row.addWidget(self.entry_output_folder, 1)
        output_row.addWidget(self.btn_output_folder)
        output_row.addWidget(self.btn_clear_output_folder)

        self.entry_default_directory = QLineEdit()
        self.entry_default_directory.setPlaceholderText(_("User's home directory"))

        self.btn_default_directory = QPushButton(_("Browse…"))
        _res = self.btn_default_directory.clicked.connect(self.on_browse_default_directory)

        self.btn_clear_default_directory = QPushButton("✕")
        self.btn_clear_default_directory.setToolTip(_("Clear the default open directory"))
        self.btn_clear_default_directory.setFixedWidth(36)
        self.btn_clear_default_directory.setStyleSheet("QPushButton { padding: 6px 10px; }")
        _res = self.btn_clear_default_directory.clicked.connect(self.on_clear_default_directory)

        default_directory_row = QHBoxLayout()
        default_directory_row.addWidget(self.entry_default_directory, 1)
        default_directory_row.addWidget(self.btn_default_directory)
        default_directory_row.addWidget(self.btn_clear_default_directory)

        self.radio_recursive = self._radio_row(
            _("Compress sub-directories"), _("Compress only root"), "recursive"
        )

        self.spin_timeout = QSpinBox()
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
        form.addRow(_("Directory Recurse"), self.radio_recursive)
        form.addRow(_("Compression Timeout"), self.spin_timeout)

        form.addRow(_separator())

        self.combo_log_level = QComboBox()
        self.combo_log_level.addItems([_(label) for label in _LOG_LEVEL_LABELS])
        self.combo_log_level.setToolTip(
            _("Verbosity of the log file. Debug includes the exact commands run.")
        )

        self.spin_log_max_size = QSpinBox()
        self.spin_log_max_size.setRange(1, 100)
        self.spin_log_max_size.setSuffix(" MB")
        self.spin_log_max_size.setToolTip(_("Maximum size of the log file before it is rotated."))

        self.spin_log_backups = QSpinBox()
        self.spin_log_backups.setRange(1, 20)
        self.spin_log_backups.setToolTip(
            _("Number of rotated log files to keep alongside the current one.")
        )

        form.addRow(_("Log Level"), self.combo_log_level)
        form.addRow(_("Log Max Size"), self.spin_log_max_size)
        form.addRow(_("Log Backups"), self.spin_log_backups)
        form.addRow(self._build_log_link())

        _res = self.combo_save_method.currentIndexChanged.connect(self.on_save_method_changed)
        _res = self.entry_output_folder.textChanged.connect(self.on_output_folder_changed)
        _res = self.entry_default_directory.textChanged.connect(self.on_default_directory_changed)
        _res = self.spin_timeout.valueChanged.connect(self.on_int_changed("compression-timeout"))
        _res = self.combo_log_level.currentIndexChanged.connect(self.on_log_level_changed)
        _res = self.spin_log_max_size.valueChanged.connect(self.on_int_changed("log-max-size"))
        _res = self.spin_log_backups.valueChanged.connect(self.on_int_changed("log-backups"))

        return tab

    def _radio_row(
        self, true_label: str, false_label: str, key: str, reverse: bool = False
    ) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        true_radio = QRadioButton(true_label)
        false_radio = QRadioButton(false_label)
        true_radio.setChecked(True)
        _res = true_radio.toggled.connect(self.on_bool_changed(key))
        self._radio_pairs.append((true_radio, false_radio, key))
        first, second = (false_radio, true_radio) if reverse else (true_radio, false_radio)
        layout.addWidget(first)
        layout.addWidget(second)
        return container

    def _build_formats_tab(self) -> QWidget:
        tab = QWidget()
        grid = QGridLayout(tab)
        grid.setContentsMargins(12, 12, 12, 12)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)

        quality_hint = _("Set the quality; 100 is best.")

        def level_hint(max_level: int) -> str:
            return _("Set the level; {} is highest but slowest.").format(max_level)

        formats = (
            (
                "PNG",
                (
                    ("png_lossy_level", _("Lossy"), quality_hint, "png-lossy-level", 0, 100),
                    (
                        "png_lossless_level",
                        _("Lossless"),
                        level_hint(6),
                        "png-lossless-level",
                        0,
                        6,
                    ),
                ),
                (),
            ),
            (
                "JPEG / Jpegli",
                (("jpg_lossy_level", _("Lossy"), quality_hint, "jpg-lossy-level", 0, 100),),
                (
                    (
                        "jpg_progressive",
                        _("Progressive Encode"),
                        _("Render incrementally, from blurry to clear."),
                        "jpg-progressive",
                    ),
                ),
            ),
            (
                "WebP",
                (
                    ("webp_lossy_level", _("Lossy"), quality_hint, "webp-lossy-level", 0, 100),
                    (
                        "webp_lossless_level",
                        _("Lossless"),
                        level_hint(6),
                        "webp-lossless-level",
                        0,
                        6,
                    ),
                ),
                (),
            ),
            (
                "AVIF",
                (
                    ("avif_lossy_level", _("Lossy"), quality_hint, "avif-lossy-level", 0, 100),
                    (
                        "avif_lossless_level",
                        _("Lossless"),
                        level_hint(10),
                        "avif-lossless-level",
                        0,
                        10,
                    ),
                ),
                (),
            ),
            (
                "JXL",
                (
                    ("jxl_lossy_level", _("Lossy"), quality_hint, "jxl-lossy-level", 1, 100),
                    (
                        "jxl_lossless_level",
                        _("Lossless"),
                        level_hint(10),
                        "jxl-lossless-level",
                        1,
                        10,
                    ),
                ),
                (),
            ),
            (
                "GIF",
                (
                    ("gif_lossy_level", _("Lossy"), quality_hint, "gif-lossy-level", 1, 100),
                    (
                        "gif_lossless_level",
                        _("Lossless"),
                        level_hint(3),
                        "gif-lossless-level",
                        1,
                        3,
                    ),
                ),
                (),
            ),
            (
                "SVG",
                (),
                (
                    (
                        "svg_maximum_level",
                        _("Maximum Compression Level"),
                        _("Enable maximum cleaning of SVG images; can be more destructive."),
                        "svg-maximum-level",
                    ),
                ),
            ),
        )

        for index, format_spec in enumerate(formats):
            row, column = divmod(index, 2)
            grid.addWidget(self._build_format_group(*format_spec), row, column)
        for column in range(2):
            grid.setColumnStretch(column, 1)
        for row in range((len(formats) + 1) // 2):
            grid.setRowStretch(row, 1)

        note_row = (len(formats) + 1) // 2
        grid.addWidget(
            self._build_note_group(
                _("BMP / TIFF"),
                _(
                    "BMP and TIFF images are always converted to WebP: they are decoded and "
                    + "re-encoded with the WebP settings above. The original file is never "
                    + "modified and the compressed result is saved as a new .webp file."
                ),
            ),
            note_row,
            0,
            1,
            2,
        )
        return tab

    def _build_log_link(self) -> QLabel:
        label = QLabel()
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setOpenExternalLinks(True)
        url = QUrl.fromLocalFile(log_file_path()).toString()
        label.setText('<a href="{}">{}</a>'.format(url, _("Open the latest log file")))
        return label

    def _build_about_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        icon = QLabel()
        icon.setPixmap(imslim_icon().pixmap(64))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)

        message = QLabel()
        message.setTextFormat(Qt.TextFormat.RichText)
        message.setOpenExternalLinks(True)
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message.setText(
            _(
                "<div style='font-size: 18pt; font-weight: bold;'>ImSlim</div>"
                + "<div style='font-size: 9pt; color: #808080;'>Version {version}</div>"
                + "<div style='margin-top: 10px;'>"
                + "Compress common image formats, lossless or lossy.</div>"
                + "<div style='margin-top: 8px;'>"
                + "<a href='{log_url}'>Open latest log file</a> · "
                + "<a href='https://github.com/dcog989/ImSlim'>GitHub</a></div>"
            ).format(version=__version__, log_url=QUrl.fromLocalFile(log_file_path()).toString())
        )
        layout.addWidget(message)

        self._about_env_label = QLabel()
        self._about_env_label.setWordWrap(True)
        self._about_env_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._about_env_label)

        copy_button = QPushButton(_("Copy Environment"))
        copy_button.setFixedWidth(160)
        _res = copy_button.clicked.connect(self._on_copy_environment)
        layout.addWidget(copy_button, alignment=Qt.AlignmentFlag.AlignHCenter)

        layout.addStretch(1)

        return tab

    def _on_tab_changed(self, index: int) -> None:
        if index == self._about_index:
            self._populate_about()

    def _populate_about(self) -> None:
        if self._about_populated:
            return
        self._about_populated = True
        # System/static info is cheap and synchronous; tool versions spawn
        # subprocesses, so probe them off the UI thread.
        self._about_env_label.setText(self._env_text())
        worker = VersionProbeWorker()
        _res = worker.versions_ready.connect(self._on_about_versions)
        _res = worker.finished.connect(lambda: worker.deleteLater())
        worker.start()

    def _env_text(self) -> str:
        lines: list[str] = []
        lines += [f"{key}: {value}" for key, value in static_about_pairs()]
        lines += [f"{key}: {value}" for key, value in system_info_pairs()]
        qt_platform = QApplication.platformName()
        if qt_platform:
            lines.append(f"Qt Platform: {qt_platform}")
        lines += [f"{key}: {value}" for key, value in self._about_tool_pairs]
        return "\n".join(lines)

    def _on_about_versions(self, tool_pairs: list[tuple[str, str]]) -> None:
        self._about_tool_pairs = tool_pairs
        self._about_env_label.setText(self._env_text())

    def _on_copy_environment(self) -> None:
        QApplication.clipboard().setText(self._env_text())

    def _build_note_group(self, title: str, text: str) -> QWidget:
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 12, 12, 12)
        note = QLabel(text)
        note.setWordWrap(True)
        layout.addWidget(note)
        return group

    def _build_format_group(
        self,
        title: str,
        spins: tuple[tuple[str, str, str, str, int, int], ...],
        checks: tuple[tuple[str, str, str, str], ...],
    ) -> QWidget:
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        for attr_name, label, hint, key, lower, upper in spins:
            layout.addLayout(self._spin_row(attr_name, label, hint, key, lower, upper))

        for attr_name, label, hint, key in checks:
            check = QCheckBox(label)
            _res = check.toggled.connect(self.on_bool_changed(key))
            setattr(self, f"toggle_{attr_name}", check)
            self._format_checks.append((check, key))
            layout.addWidget(check)
            layout.addWidget(self._hint_label(hint))

        return group

    def _hint_label(self, hint: str) -> QLabel:
        hint_label = QLabel(hint)
        hint_label.setWordWrap(True)
        hint_label.setMinimumHeight(hint_label.fontMetrics().height() + 4)
        hint_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        # Muted but readable on both light and dark themes: blend the text
        # color toward the background instead of a hardcoded gray.
        apply_muted_palette(hint_label)

        hint_font = hint_label.font()
        hint_font.setPointSizeF(hint_font.pointSizeF() * 0.9)
        hint_label.setFont(hint_font)

        return hint_label

    def _spin_row(
        self,
        attr_name: str,
        label: str,
        hint: str,
        key: str,
        lower: int,
        upper: int,
    ) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setSpacing(2)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        label_widget = QLabel(label)
        label_widget.setMinimumWidth(110)
        spin = QSpinBox()
        spin.setRange(lower, upper)
        _res = spin.valueChanged.connect(self.on_int_changed(key))
        setattr(self, f"spin_{attr_name}", spin)
        self._format_spins.append((spin, key))
        row.addWidget(label_widget)
        row.addStretch(1)
        row.addWidget(spin)
        column.addLayout(row)

        column.addWidget(self._hint_label(hint))

        return column

    def _load_values(self) -> None:
        s = self.settings
        self.combo_save_method.setCurrentIndex(s.save_method)
        self.entry_output_folder.setText(s.output_folder)
        self.entry_default_directory.setText(s.default_open_dialog_directory)
        self.spin_timeout.setValue(s.compression_timeout)
        self.combo_log_level.setCurrentIndex(_LOG_LEVELS.index(s.log_level))
        self._set_log_controls_state(s.log_level)
        self.spin_log_max_size.setValue(s.log_max_size)
        self.spin_log_backups.setValue(s.log_backups)

        for true_radio, false_radio, key in self._radio_pairs:
            value = cast(bool, getattr(s, key.replace("-", "_")))
            (true_radio if value else false_radio).setChecked(True)

        for spin, key in self._format_spins:
            spin.setValue(cast(int, getattr(s, key.replace("-", "_"))))
        for check, key in self._format_checks:
            check.setChecked(cast(bool, getattr(s, key.replace("-", "_"))))

    @override
    def closeEvent(self, event: object) -> None:
        self._save_all()
        self.settings.sync()
        super().closeEvent(cast(QCloseEvent, event))

    def _save_all(self) -> None:
        s = self.settings
        s.save_method = self.combo_save_method.currentIndex()
        s.output_folder = self.entry_output_folder.text().strip()
        s.default_open_dialog_directory = self.entry_default_directory.text().strip()
        s.compression_timeout = self.spin_timeout.value()
        s.log_level = _LOG_LEVELS[self.combo_log_level.currentIndex()]
        s.log_max_size = self.spin_log_max_size.value()
        s.log_backups = self.spin_log_backups.value()

        for true_radio, _false_radio, key in self._radio_pairs:
            setattr(s, key.replace("-", "_"), true_radio.isChecked())

        for spin, key in self._format_spins:
            setattr(s, key.replace("-", "_"), spin.value())
        for check, key in self._format_checks:
            setattr(s, key.replace("-", "_"), check.isChecked())

    def on_save_method_changed(self, index: int) -> None:
        self.settings.save_method = index
        self.settings_changed.emit()

    def on_output_folder_changed(self, text: str) -> None:
        self.settings.output_folder = text.strip()
        self.settings_changed.emit()

    def on_default_directory_changed(self, text: str) -> None:
        self.settings.default_open_dialog_directory = text.strip()
        self.settings_changed.emit()

    def on_browse_default_directory(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            _("Select Default Open Dialog Directory"),
            self.entry_default_directory.text() or "",
        )
        if folder:
            self.entry_default_directory.setText(folder)

    def on_clear_default_directory(self) -> None:
        self.entry_default_directory.setText("")

    def on_browse_output_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            _("Select Output Folder"),
            self.entry_output_folder.text() or "",
        )
        if folder:
            self.entry_output_folder.setText(folder)

    def on_clear_output_folder(self) -> None:
        self.entry_output_folder.setText("")

    def on_bool_changed(self, key: str) -> Callable[[bool], None]:
        def handler(checked: bool) -> None:
            self.settings.set_boolean(key, checked)
            self.settings_changed.emit()

        return handler

    def on_int_changed(self, key: str) -> Callable[[int], None]:
        def handler(value: int) -> None:
            self.settings.set_int(key, value)
            self.settings_changed.emit()

        return handler

    def on_log_level_changed(self, index: int) -> None:
        self.settings.log_level = _LOG_LEVELS[index]
        self._set_log_controls_state(_LOG_LEVELS[index])
        self.settings_changed.emit()

    def _set_log_controls_state(self, level: str) -> None:
        enabled = level != "NONE"
        self.spin_log_max_size.setEnabled(enabled)
        self.spin_log_backups.setEnabled(enabled)
