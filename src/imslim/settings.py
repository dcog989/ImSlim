from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ._i18n import _


class SettingsDialog(QDialog):
    settings_changed = Signal()

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Settings"))
        self.settings = settings
        self._format_spins: list[tuple[QSpinBox, str]] = []
        self._format_checks: list[tuple[QCheckBox, str]] = []
        self.build_ui()

    def build_ui(self):
        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        tabs.addTab(self._build_general_tab(), _("General"))
        tabs.addTab(self._build_formats_tab(), _("Formats"))
        layout.addWidget(tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)

        self._load_values()

    def _build_general_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setContentsMargins(16, 16, 16, 16)
        form.setVerticalSpacing(16)

        self.combo_save_method = QComboBox()
        self.combo_save_method.addItems(
            [_("Create a new compressed file"), _("Backup original and overwrite")]
        )

        self.entry_output_folder = QLineEdit()
        self.entry_output_folder.setPlaceholderText(_("Same folder as the original files"))

        self.btn_output_folder = QPushButton(_("Browse…"))
        self.btn_output_folder.clicked.connect(self.on_browse_output_folder)

        self.btn_clear_output_folder = QPushButton(_("Clear"))
        self.btn_clear_output_folder.clicked.connect(self.on_clear_output_folder)

        output_row = QHBoxLayout()
        output_row.addWidget(self.entry_output_folder, 1)
        output_row.addWidget(self.btn_output_folder)
        output_row.addWidget(self.btn_clear_output_folder)

        self.toggle_recursive = QCheckBox(_("Enable or disable compression through subdirectories"))
        self.toggle_metadata = QCheckBox(_("Keep metadata chunks that do not affect rendering"))
        self.toggle_file_attributes = QCheckBox(
            _("Ensure the new file has the same permissions and timestamps")
        )

        self.spin_timeout = QSpinBox()
        self.spin_timeout.setRange(1, 300)
        self.spin_timeout.setSuffix(_(" s"))

        form.addRow(_("Save Method"), self.combo_save_method)
        form.addRow(_("Output Folder"), output_row)
        form.addRow(_("Recursive Compression"), self.toggle_recursive)
        form.addRow(_("Keep Metadata"), self.toggle_metadata)
        form.addRow(_("Keep File Attributes When Possible"), self.toggle_file_attributes)
        form.addRow(_("Compression Timeout"), self.spin_timeout)

        self.combo_save_method.currentIndexChanged.connect(self.on_save_method_changed)
        self.entry_output_folder.textChanged.connect(self.on_output_folder_changed)
        self.spin_timeout.valueChanged.connect(self.on_int_changed("compression-timeout"))
        self.toggle_recursive.toggled.connect(self.on_bool_changed("recursive"))
        self.toggle_metadata.toggled.connect(self.on_bool_changed("metadata"))
        self.toggle_file_attributes.toggled.connect(self.on_bool_changed("file-attributes"))

        return tab

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
                    "re-encoded with the WebP settings above. The original file is never "
                    "modified and the compressed result is saved as a new .webp file."
                ),
            ),
            note_row,
            0,
            1,
            2,
        )
        return tab

    def _build_note_group(self, title, text) -> QWidget:
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 12, 12, 12)
        note = QLabel(text)
        note.setWordWrap(True)
        layout.addWidget(note)
        return group

    def _build_format_group(self, title, spins, checks) -> QWidget:
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        for attr_name, label, hint, key, lower, upper in spins:
            layout.addLayout(self._spin_row(attr_name, label, hint, key, lower, upper))

        for attr_name, label, hint, key in checks:
            check = QCheckBox(label)
            check.toggled.connect(self.on_bool_changed(key))
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

    def _spin_row(self, attr_name, label, hint, key, lower, upper) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setSpacing(2)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        label_widget = QLabel(label)
        label_widget.setMinimumWidth(110)
        spin = QSpinBox()
        spin.setRange(lower, upper)
        spin.valueChanged.connect(self.on_int_changed(key))
        setattr(self, f"spin_{attr_name}", spin)
        self._format_spins.append((spin, key))
        row.addWidget(label_widget)
        row.addStretch(1)
        row.addWidget(spin)
        column.addLayout(row)

        column.addWidget(self._hint_label(hint))

        return column

    def _load_values(self):
        s = self.settings
        self.combo_save_method.setCurrentIndex(s.save_method)
        self.entry_output_folder.setText(s.output_folder)
        self.toggle_recursive.setChecked(s.recursive)
        self.toggle_metadata.setChecked(s.metadata)
        self.toggle_file_attributes.setChecked(s.file_attributes)
        self.spin_timeout.setValue(s.compression_timeout)

        for spin, key in self._format_spins:
            spin.setValue(getattr(s, key.replace("-", "_")))
        for check, key in self._format_checks:
            check.setChecked(getattr(s, key.replace("-", "_")))

    def on_save_method_changed(self, index):
        self.settings.save_method = index
        self.settings_changed.emit()

    def on_output_folder_changed(self, text):
        self.settings.output_folder = text.strip()
        self.settings_changed.emit()

    def on_browse_output_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            _("Select Output Folder"),
            self.entry_output_folder.text() or "",
        )
        if folder:
            self.entry_output_folder.setText(folder)

    def on_clear_output_folder(self):
        self.entry_output_folder.setText("")

    def on_bool_changed(self, key):
        def handler(checked):
            self.settings.set_boolean(key, checked)

        return handler

    def on_int_changed(self, key):
        def handler(value):
            self.settings.set_int(key, value)

        return handler
