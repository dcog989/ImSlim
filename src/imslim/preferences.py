from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
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

        self.toggle_new_file = QCheckBox(_("Save the compressed image in a new file"))
        self.toggle_backup = QCheckBox(_("Save original file to [filename].bak.[ext]"))
        self.toggle_recursive = QCheckBox(_("Enable or disable compression through subdirectories"))
        self.toggle_metadata = QCheckBox(_("Keep metadata chunks that do not affect rendering"))
        self.toggle_file_attributes = QCheckBox(
            _("Ensure the new file has the same permissions and timestamps")
        )

        self.combo_naming_mode = QComboBox()
        self.combo_naming_mode.addItems([_("Suffix"), _("Prefix")])

        self.entry_suffix_prefix = QLineEdit()

        self.spin_timeout = QSpinBox()
        self.spin_timeout.setRange(1, 300)
        self.spin_timeout.setSuffix(_(" s"))

        form.addRow(_("Safe Mode"), self.toggle_new_file)
        form.addRow(_("Backup Original File"), self.toggle_backup)
        form.addRow(_("Naming Mode"), self.combo_naming_mode)
        form.addRow(_("New File Suffix/Prefix"), self.entry_suffix_prefix)
        form.addRow(_("Recursive Compression"), self.toggle_recursive)
        form.addRow(_("Keep Metadata"), self.toggle_metadata)
        form.addRow(_("Keep File Attributes When Possible"), self.toggle_file_attributes)
        form.addRow(_("Compression Timeout"), self.spin_timeout)

        self.toggle_new_file.toggled.connect(self.on_new_file_changed)
        self.toggle_backup.toggled.connect(self.on_backup_changed)
        self.combo_naming_mode.currentIndexChanged.connect(self.on_naming_changed)
        self.entry_suffix_prefix.textChanged.connect(self.on_suffix_changed)
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
        self.toggle_new_file.setChecked(s.new_file)
        self.toggle_backup.setChecked(s.backup)
        self.toggle_recursive.setChecked(s.recursive)
        self.toggle_metadata.setChecked(s.metadata)
        self.toggle_file_attributes.setChecked(s.file_attributes)
        self.combo_naming_mode.setCurrentIndex(s.naming_mode)
        self.entry_suffix_prefix.setText(s.suffix_prefix)
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

        self._apply_mutual_exclusion()

    def _apply_mutual_exclusion(self):
        new_file = self.settings.new_file
        self.combo_naming_mode.setEnabled(new_file)
        self.entry_suffix_prefix.setEnabled(new_file)
        self.toggle_backup.setEnabled(not new_file)

    def on_new_file_changed(self, checked):
        self.settings.new_file = checked
        if checked and self.settings.backup:
            self.settings.backup = False
            self.toggle_backup.blockSignals(True)
            self.toggle_backup.setChecked(False)
            self.toggle_backup.blockSignals(False)
        self.window.set_saving_subtitle(checked)
        self._apply_mutual_exclusion()

    def on_backup_changed(self, checked):
        if checked and self.settings.new_file:
            self.settings.new_file = False
            self.toggle_new_file.blockSignals(True)
            self.toggle_new_file.setChecked(False)
            self.toggle_new_file.blockSignals(False)
            self.window.set_saving_subtitle(False)
            self._apply_mutual_exclusion()
        else:
            self.settings.backup = checked
            self.window.set_saving_subtitle()

    def on_naming_changed(self, index):
        self.settings.naming_mode = index
        if not index:
            self.settings.reset("naming-mode")
        self.window.set_saving_subtitle()

    def on_suffix_changed(self, text):
        self.settings.suffix_prefix = text
        if not text:
            self.settings.reset("suffix-prefix")
        self.window.set_saving_subtitle()

    def on_bool_changed(self, key):
        def handler(checked):
            self.settings.set_boolean(key, checked)

        return handler

    def on_int_changed(self, key):
        def handler(value):
            self.settings.set_int(key, value)

        return handler
