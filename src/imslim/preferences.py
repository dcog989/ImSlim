from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .settings_manager import SettingsManager


class PreferencesDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(_("Preferences"))
        self.settings = SettingsManager()
        self.window = parent
        self.build_ui()

    def build_ui(self):
        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        tabs.addTab(self._build_general_tab(), _("General"))
        tabs.addTab(self._build_formats_tab(), _("Formats"))
        layout.addWidget(tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)

        self._load_values()

    def _build_general_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)

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
        layout = QVBoxLayout(tab)

        layout.addWidget(
            self._build_format_group(
                "PNG",
                [
                    ("png_lossy_level", _("Lossy Compression"), "png-lossy-level", 0, 100),
                    ("png_lossless_level", _("Lossless Compression"), "png-lossless-level", 0, 6),
                ],
            )
        )
        layout.addWidget(self._build_jpg_group())
        layout.addWidget(
            self._build_format_group(
                "WebP",
                [
                    ("webp_lossy_level", _("Lossy Compression"), "webp-lossy-level", 0, 100),
                    ("webp_lossless_level", _("Lossless Compression"), "webp-lossless-level", 0, 6),
                ],
            )
        )
        layout.addWidget(
            self._build_format_group(
                "AVIF",
                [
                    ("avif_lossy_level", _("Lossy Compression"), "avif-lossy-level", 0, 100),
                    (
                        "avif_lossless_level",
                        _("Lossless Compression"),
                        "avif-lossless-level",
                        0,
                        10,
                    ),
                ],
            )
        )
        layout.addWidget(
            self._build_format_group(
                "GIF",
                [
                    ("gif_lossy_level", _("Lossy Compression"), "gif-lossy-level", 1, 100),
                    ("gif_lossless_level", _("Lossless Compression"), "gif-lossless-level", 1, 3),
                ],
            )
        )
        layout.addWidget(self._build_svg_group())
        layout.addStretch(1)
        return tab

    def _build_format_group(self, title, rows):
        group = QGroupBox(title)
        form = QFormLayout(group)
        for attr_name, label, key, lower, upper in rows:
            spin = QSpinBox()
            spin.setRange(lower, upper)
            spin.valueChanged.connect(self.on_int_changed(key))
            setattr(self, f"spin_{attr_name}", spin)
            form.addRow(label, spin)
        return group

    def _build_jpg_group(self) -> QWidget:
        group = QGroupBox("JPG")
        form = QFormLayout(group)
        self.spin_jpg_lossy_level = QSpinBox()
        self.spin_jpg_lossy_level.setRange(0, 100)
        self.spin_jpg_lossy_level.valueChanged.connect(self.on_int_changed("jpg-lossy-level"))
        self.toggle_jpg_progressive = QCheckBox(_("Progressive Encode"))
        self.toggle_jpg_progressive.toggled.connect(self.on_bool_changed("jpg-progressive"))
        form.addRow(_("Lossy Compression"), self.spin_jpg_lossy_level)
        form.addRow(_("Progressive Encode"), self.toggle_jpg_progressive)
        return group

    def _build_svg_group(self) -> QWidget:
        group = QGroupBox("SVG")
        form = QFormLayout(group)
        self.toggle_svg_maximum_level = QCheckBox(
            _("Enable maximum cleaning of SVG images. This can be more destructive.")
        )
        self.toggle_svg_maximum_level.toggled.connect(self.on_bool_changed("svg-maximum-level"))
        form.addRow(_("Maximum Compression Level"), self.toggle_svg_maximum_level)
        return group

    def _load_values(self):
        s = self.settings
        self.combo_save_method.setCurrentIndex(s.save_method)
        self.entry_output_folder.setText(s.output_folder)
        self.toggle_recursive.setChecked(s.recursive)
        self.toggle_metadata.setChecked(s.metadata)
        self.toggle_file_attributes.setChecked(s.file_attributes)
        self.spin_timeout.setValue(s.compression_timeout)

        self.spin_png_lossy_level.setValue(s.png_lossy_level)
        self.spin_png_lossless_level.setValue(s.png_lossless_level)
        self.spin_jpg_lossy_level.setValue(s.jpg_lossy_level)
        self.toggle_jpg_progressive.setChecked(s.jpg_progressive)
        self.spin_webp_lossy_level.setValue(s.webp_lossy_level)
        self.spin_webp_lossless_level.setValue(s.webp_lossless_level)
        self.spin_avif_lossy_level.setValue(s.avif_lossy_level)
        self.spin_avif_lossless_level.setValue(s.avif_lossless_level)
        self.spin_gif_lossy_level.setValue(s.gif_lossy_level)
        self.spin_gif_lossless_level.setValue(s.gif_lossless_level)
        self.toggle_svg_maximum_level.setChecked(s.svg_maximum_level)

    def on_save_method_changed(self, index):
        self.settings.save_method = index
        self.window.set_saving_subtitle()

    def on_output_folder_changed(self, text):
        self.settings.output_folder = text.strip()
        self.window.set_saving_subtitle()

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
