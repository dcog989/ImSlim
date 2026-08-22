from collections.abc import Callable
from typing import cast, override

from PySide6.QtCore import Signal
from PySide6.QtGui import QCloseEvent, QColor
from PySide6.QtWidgets import (
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

from ._i18n import _
from .settings_manager import SettingsManager

_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")
_LOG_LEVEL_LABELS = ("Debug", "Info", "Warning", "Error")

_FORM_STYLESHEET = (
    "QPushButton { padding: 6px 16px; }"
    "QComboBox { padding: 5px 12px; }"
    "QSpinBox { padding: 0px 6px; min-height: 22px; }"
    "QLineEdit { padding: 5px 10px; }"
    "QCheckBox, QRadioButton { spacing: 8px; }"
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
        self.radio_recursive: QWidget = QWidget()
        self.radio_compression_method: QWidget = QWidget()
        self.radio_metadata: QWidget = QWidget()
        self.radio_file_attributes: QWidget = QWidget()
        self.spin_timeout: QSpinBox = QSpinBox()
        self.combo_log_level: QComboBox = QComboBox()
        self.spin_log_max_size: QSpinBox = QSpinBox()
        self.spin_log_backups: QSpinBox = QSpinBox()
        self.build_ui()

    def build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.setStyleSheet(_FORM_STYLESHEET)

        tabs = QTabWidget()
        _res = tabs.addTab(self._build_general_tab(), _("General"))
        _res = tabs.addTab(self._build_formats_tab(), _("Formats"))
        layout.addWidget(tabs)

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
        form.addRow(_("Directory Recurse"), self.radio_recursive)
        form.addRow(_("Compression Timeout"), self.spin_timeout)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFixedHeight(28)
        form.addRow(separator)

        self.radio_compression_method = self._radio_row(
            _("Lossy"), _("Lossless"), "lossy", reverse=True
        )
        self.radio_metadata = self._radio_row(_("Keep metadata"), _("Remove metadata"), "metadata")
        self.radio_file_attributes = self._radio_row(
            _("Keep attr"), _("Reset attr"), "file-attributes"
        )

        form.addRow(_("Compression Method"), self.radio_compression_method)
        form.addRow(_("Metadata Retention"), self.radio_metadata)
        form.addRow(_("File Attributes"), self.radio_file_attributes)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFixedHeight(28)
        form.addRow(separator)

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

        _res = self.combo_save_method.currentIndexChanged.connect(self.on_save_method_changed)
        _res = self.entry_output_folder.textChanged.connect(self.on_output_folder_changed)
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
        palette = hint_label.palette()
        fg = palette.color(palette.ColorRole.Text)
        bg = palette.color(palette.ColorRole.Base)
        muted = QColor(
            round(fg.red() * 0.5 + bg.red()),
            round(fg.green() * 0.5 + bg.green()),
            round(fg.blue() * 0.5 + bg.blue()),
        )
        palette.setColor(palette.ColorRole.Text, muted)
        palette.setColor(palette.ColorRole.WindowText, muted)
        hint_label.setPalette(palette)

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
        self.spin_timeout.setValue(s.compression_timeout)
        self.combo_log_level.setCurrentIndex(_LOG_LEVELS.index(s.log_level))
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
        self.settings_changed.emit()
