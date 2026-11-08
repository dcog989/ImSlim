"""Column 2: output options and the Process button."""

import html
from functools import partial

from PySide6.QtCore import QSize, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ._i18n import _
from .formats import (
    FORMAT_BY_KEY,
    FORMAT_SPECS,
    TARGET_SPECS,
    Format,
    FormatSpec,
    Knob,
    is_converting,
)
from .icons import imslim_icon
from .settings_manager import (
    SAVE_BACKUP_OVERWRITE,
    SAVE_NEXT_TO_ORIGINAL,
    SAVE_OUTPUT_FOLDER,
    SettingsManager,
)
from .theme import accent_colors, combo_stylesheet, form_stylesheet, spinbox

# (label, save method) in the order the design lists them.
_DESTINATIONS: tuple[tuple[str, int], ...] = (
    (_("Overwrite original"), SAVE_BACKUP_OVERWRITE),
    (_("Next to the original"), SAVE_NEXT_TO_ORIGINAL),
    (_("Specified directory"), SAVE_OUTPUT_FOLDER),
)

_BMP_TIFF_NOTE = _(
    "BMP and TIFF images are always decoded and re-encoded to WebP; their "
    + "original format cannot be kept."
)
_SVG_NOTE = _("SVG images are always compressed losslessly.")
_ANIMATION_NOTE = _("Converting an animated image keeps only its first frame.")
_JPEG_NOTE = _("JPEG cannot encode losslessly; Lossless encodes at the highest quality instead.")


def _format_notes(target: Format) -> list[str]:
    """Caveats that apply to the currently selected output format."""
    if target is Format.KEEP:
        return [_BMP_TIFF_NOTE, _SVG_NOTE]
    if target is Format.JPEG:
        return [_JPEG_NOTE, _ANIMATION_NOTE]
    return [_ANIMATION_NOTE]


class OptionsView(QWidget):
    """Persistent settings for the queue: format, destination and knobs."""

    process_requested: Signal = Signal()
    about_requested: Signal = Signal()
    options_changed: Signal = Signal()

    def __init__(self, settings: SettingsManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings: SettingsManager = settings
        self._knob_widgets: list[tuple[QSpinBox | QCheckBox, Knob]] = []
        self._build()
        self._rebuild_knobs()

    # ------------------------------------------------------------------ build
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setStyleSheet(form_stylesheet())
        self.setMinimumWidth(320)

        content = QWidget()
        form = QVBoxLayout(content)
        form.setContentsMargins(12, 12, 12, 12)
        form.setSpacing(8)

        self.combo_format: QComboBox = self._combo(
            (_("Same as input"), *(spec.display for spec in TARGET_SPECS)),
            _("Output format. Keep each file's format, or convert everything to one format."),
        )
        self.combo_format.setCurrentIndex(self._format_index())
        _res = self.combo_format.currentIndexChanged.connect(self._on_format_changed)

        format_row = QHBoxLayout()
        format_row.setContentsMargins(0, 0, 0, 0)
        format_row.setSpacing(4)
        format_row.addWidget(self.combo_format, 1)
        format_row.addWidget(self._info_button())

        self.combo_destination: QComboBox = self._combo(
            tuple(label for label, _value in _DESTINATIONS),
            _(
                "Where the compressed files go. Overwriting keeps a timestamped "
                + "backup beside the original."
            ),
        )
        self.combo_destination.setCurrentIndex(self._destination_index())
        _res = self.combo_destination.currentIndexChanged.connect(self._on_destination_changed)

        self.entry_output_folder: QLineEdit = QLineEdit()
        self.entry_output_folder.setPlaceholderText(_("Choose a folder"))
        self.entry_output_folder.setText(self.settings.output_folder)
        _res = self.entry_output_folder.editingFinished.connect(self._commit_output_folder)
        browse = QPushButton(_("Browse…"))
        _res = browse.clicked.connect(self._browse_output_folder)
        self.output_folder_row: QWidget = QWidget()
        folder_layout = QHBoxLayout(self.output_folder_row)
        folder_layout.setContentsMargins(0, 0, 0, 0)
        folder_layout.addWidget(self.entry_output_folder, 1)
        folder_layout.addWidget(browse)

        self.check_timestamp_dir: QCheckBox = QCheckBox()
        self.check_timestamp_dir.setAccessibleName(_("New timestamped directory"))
        self.check_timestamp_dir.setToolTip(
            _("Write the results into an imslim-<timestamp> directory inside the destination.")
        )
        self.check_timestamp_dir.setChecked(self.settings.timestamp_dir)
        _res = self.check_timestamp_dir.toggled.connect(self._on_timestamp_dir)

        fields = self._form_layout()
        fields.addRow(_("Output format"), format_row)
        fields.addRow(_("Destination"), self.combo_destination)
        fields.addRow("", self.output_folder_row)
        form.addLayout(fields)
        self._output_fields: QFormLayout = fields

        timestamp_fields = self._form_layout()
        timestamp_fields.addRow(_("New timestamped directory"), self.check_timestamp_dir)
        form.addLayout(timestamp_fields)
        form.addWidget(self._divider())

        self.check_recursive: QCheckBox = self._check(_("Include sub-directories"))
        self.check_recursive.setChecked(self.settings.recursive)
        _res = self.check_recursive.toggled.connect(self._on_recursive)

        self.check_metadata: QCheckBox = self._check(_("Keep EXIF and metadata"))
        self.check_metadata.setChecked(self.settings.metadata)
        _res = self.check_metadata.toggled.connect(self._on_metadata)

        self.check_attributes: QCheckBox = self._check(_("Keep file attributes"))
        self.check_attributes.setChecked(self.settings.file_attributes)
        _res = self.check_attributes.toggled.connect(self._on_attributes)

        self.check_skip_if_larger: QCheckBox = self._check(_("Skip if result is larger"))
        self.check_skip_if_larger.setToolTip(
            _("Keep the original when compressing would not make the file smaller.")
        )
        self.check_skip_if_larger.setChecked(self.settings.skip_if_larger)
        _res = self.check_skip_if_larger.toggled.connect(self._on_skip_if_larger)

        files = self._form_layout()
        files.addRow(_("Include sub-directories"), self.check_recursive)
        files.addRow(_("Keep EXIF and metadata"), self.check_metadata)
        files.addRow(_("Keep file attributes"), self.check_attributes)
        files.addRow(_("Skip if result is larger"), self.check_skip_if_larger)
        form.addLayout(files)
        form.addWidget(self._divider())

        self.combo_compression: QComboBox = self._combo(
            (_("Lossy"), _("Lossless")),
            _("Lossy is much smaller with some quality loss; lossless keeps the pixels exact."),
        )
        self.combo_compression.setCurrentIndex(0 if self.settings.lossy else 1)
        _res = self.combo_compression.currentIndexChanged.connect(self._on_compression_changed)

        self.spin_timeout: QSpinBox = spinbox()
        self.spin_timeout.setRange(1, 300)
        self.spin_timeout.setSuffix(" s")
        self.spin_timeout.setValue(self.settings.compression_timeout)
        self.spin_timeout.setToolTip(
            _(
                "Maximum seconds a single compression tool may run on one image "
                + "before it is stopped. Raise it for very large AVIF or JXL images."
            )
        )
        _res = self.spin_timeout.valueChanged.connect(self._on_timeout)

        fields = self._form_layout()
        fields.addRow(_("Compression mode"), self.combo_compression)

        self.knobs_container: QWidget = QWidget()
        self.knobs_layout: QVBoxLayout = QVBoxLayout(self.knobs_container)
        self.knobs_layout.setContentsMargins(0, 0, 0, 0)
        self.knobs_layout.setSpacing(8)
        fields.addRow(self.knobs_container)
        fields.addRow(_("Tool timeout"), self.spin_timeout)
        form.addLayout(fields)

        form.addStretch(1)
        self._update_destination_state()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        self.about_button: QPushButton = QPushButton()
        self.about_button.setIcon(imslim_icon())
        self.about_button.setIconSize(QSize(28, 28))
        self.about_button.setFixedSize(48, 48)
        self.about_button.setToolTip(_("About ImSlim"))
        self.about_button.setAccessibleName(_("About ImSlim"))
        self.about_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.about_button.setStyleSheet(
            "QPushButton {"
            + " padding: 0;"
            + " border-radius: 24px;"
            + " border: 1px solid palette(mid);"
            + " background-color: palette(button);"
            + "}"
            + "QPushButton:hover { background-color: palette(midlight); }"
            + "QPushButton:pressed { background-color: palette(mid); }"
        )
        _res = self.about_button.clicked.connect(self.about_requested.emit)

        self.process_button: QPushButton = QPushButton(_("Process"))
        self.process_button.setMinimumHeight(48)
        self.process_button.setCursor(Qt.CursorShape.PointingHandCursor)
        accent, accent_hover, accent_pressed = accent_colors()
        self.process_button.setStyleSheet(
            "QPushButton {"
            + "  border-radius: 24px;"
            + f"  background-color: {accent.name()};"
            + "  color: palette(highlighted-text);"
            + "  border: none;"
            + "  font-size: 15pt;"
            + "  font-weight: bold;"
            + "}"
            + "QPushButton:hover {"
            + f"  background-color: {accent_hover.name()};"
            + "}"
            + "QPushButton:pressed {"
            + f"  background-color: {accent_pressed.name()};"
            + "}"
            + "QPushButton:disabled {"
            + "  background-color: palette(mid);"
            + "  color: palette(light);"
            + "}"
        )
        _res = self.process_button.clicked.connect(self.process_requested.emit)
        bottom = QHBoxLayout()
        bottom.setContentsMargins(12, 8, 12, 12)
        bottom.setSpacing(8)
        bottom.addWidget(self.process_button, 1)
        bottom.addWidget(self.about_button)
        root.addLayout(bottom)
        self.set_process_enabled(False)

    # ----------------------------------------------------------------- widgets
    @staticmethod
    def _combo(items: tuple[str, ...], tooltip: str) -> QComboBox:
        combo = QComboBox()
        combo.addItems(items)
        combo.setStyleSheet(combo_stylesheet())
        combo.setToolTip(f"<div style='width: 280px'>{html.escape(tooltip)}</div>")
        # The pane is narrow: let a combo shrink and elide its current item
        # instead of forcing a horizontal scrollbar on the whole form.
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        combo.setMinimumContentsLength(6)
        return combo

    @staticmethod
    def _form_layout() -> QFormLayout:
        fields = QFormLayout()
        fields.setContentsMargins(0, 0, 0, 0)
        fields.setHorizontalSpacing(8)
        fields.setVerticalSpacing(6)
        fields.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        return fields

    @staticmethod
    def _check(label: str) -> QCheckBox:
        """A checkbox whose text lives in the label column like every option."""
        check = QCheckBox()
        check.setAccessibleName(label)
        return check

    @staticmethod
    def _divider() -> QWidget:
        """A 1 px rule with breathing room above and below."""
        divider = QWidget()
        layout = QVBoxLayout(divider)
        layout.setContentsMargins(0, 6, 0, 6)
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: palette(mid); border: none;")
        layout.addWidget(line)
        return divider

    def _info_button(self) -> QPushButton:
        button = QPushButton("i")
        button.setFixedSize(28, 28)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setToolTip(_("Format notes"))
        button.setStyleSheet("QPushButton { padding: 0; }")
        _res = button.clicked.connect(self._show_format_notes)
        return button

    def _show_format_notes(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        dialog.setModal(True)
        dialog.setStyleSheet(
            "QDialog {"
            + " background-color: palette(window);"
            + " border: 1px solid palette(mid);"
            + "}"
        )
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        title = QLabel(_("Format notes"))
        font = title.font()
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)
        notes = QLabel("\n\n".join(_format_notes(self.settings.target_format)))
        notes.setWordWrap(True)
        notes.setMinimumWidth(280)
        layout.addWidget(notes)
        close = QPushButton(_("Close"))
        close.setDefault(True)
        _res = close.clicked.connect(dialog.accept)
        layout.addWidget(close, 0, Qt.AlignmentFlag.AlignRight)
        _res = dialog.exec()

    # ------------------------------------------------------------------- knobs
    def _rebuild_knobs(self) -> None:
        while self.knobs_layout.count():
            item = self.knobs_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._knob_widgets.clear()

        target = self.settings.target_format
        specs: tuple[FormatSpec, ...]
        if is_converting(target):
            specs = (FORMAT_BY_KEY[target],)
        else:
            # Keeping the source format means any of them can be the output;
            # show every format's knobs, not only the conversion targets.
            specs = tuple(spec for spec in FORMAT_SPECS if spec.knobs)

        if any(spec.knobs for spec in specs):
            self.knobs_layout.addWidget(self._divider())
        for spec in specs:
            if not spec.knobs:
                continue
            group = QWidget()
            layout = QVBoxLayout(group)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(4)
            title = QLabel(spec.title)
            title_font = title.font()
            title_font.setBold(True)
            title.setFont(title_font)
            layout.addWidget(title)
            knobs_row = QHBoxLayout()
            knobs_row.setContentsMargins(0, 0, 0, 0)
            knobs_row.setSpacing(16)
            for knob in spec.knobs:
                knobs_row.addWidget(self._knob_widget(knob))
            knobs_row.addStretch(1)
            layout.addLayout(knobs_row)
            self.knobs_layout.addWidget(group)
            self.knobs_layout.addWidget(self._divider())
        if self._knob_widgets:
            self._update_knob_state()

    def _knob_widget(self, knob: Knob) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        label = QLabel(knob.label)
        label.setToolTip(knob.hint)
        layout.addWidget(label)
        if knob.kind == "flag":
            check = QCheckBox()
            check.setAccessibleName(knob.label)
            check.setToolTip(knob.hint)
            check.setChecked(bool(self.settings.knob(knob.key)))
            _res = check.toggled.connect(partial(self._on_knob_flag, knob.key))
            self._knob_widgets.append((check, knob))
            label.setBuddy(check)
            layout.addWidget(check)
            return row
        spin = spinbox()
        spin.setRange(knob.lower, knob.upper)
        spin.setValue(int(self.settings.knob(knob.key)))
        spin.setToolTip(knob.hint)
        _res = spin.valueChanged.connect(partial(self._on_knob_level, knob.key))
        self._knob_widgets.append((spin, knob))
        label.setBuddy(spin)
        layout.addWidget(spin)
        return row

    def _on_knob_flag(self, key: str, checked: bool) -> None:
        self.settings.set_boolean(key, checked)
        self.options_changed.emit()

    def _on_knob_level(self, key: str, value: int) -> None:
        self.settings.set_int(key, value)
        self.options_changed.emit()

    def _update_knob_state(self) -> None:
        # Lossless skips the quantizer, so its quality knob has no effect. The
        # flag lives on the key the format table already defines.
        lossless = not self.settings.lossy
        for widget, knob in self._knob_widgets:
            widget.setEnabled(not (lossless and knob.key.endswith("-lossy-level")))

    # ---------------------------------------------------------------- handlers
    def _format_index(self) -> int:
        target = self.settings.target_format
        for index, spec in enumerate(TARGET_SPECS):
            if spec.key == target:
                return index + 1
        return 0

    def _destination_index(self) -> int:
        for index, (_label, value) in enumerate(_DESTINATIONS):
            if value == self.settings.save_method:
                return index
        return 1

    def _on_format_changed(self, index: int) -> None:
        self.settings.target_format = Format.KEEP if index <= 0 else TARGET_SPECS[index - 1].key
        self._rebuild_knobs()
        self.options_changed.emit()

    def _on_compression_changed(self, index: int) -> None:
        self.settings.lossy = index == 0
        self._update_knob_state()
        self.options_changed.emit()

    def _on_timestamp_dir(self, checked: bool) -> None:
        self.settings.timestamp_dir = checked

    def _on_recursive(self, checked: bool) -> None:
        self.settings.recursive = checked

    def _on_metadata(self, checked: bool) -> None:
        self.settings.metadata = checked
        self.options_changed.emit()

    def _on_attributes(self, checked: bool) -> None:
        self.settings.file_attributes = checked

    def _on_skip_if_larger(self, checked: bool) -> None:
        self.settings.skip_if_larger = checked

    def _on_timeout(self, value: int) -> None:
        self.settings.compression_timeout = value

    def _on_destination_changed(self, index: int) -> None:
        self.settings.save_method = _DESTINATIONS[index][1]
        self._update_destination_state()

    def _update_destination_state(self) -> None:
        custom = self.settings.save_method == SAVE_OUTPUT_FOLDER
        self._output_fields.setRowVisible(self.output_folder_row, custom)
        # A backup is written beside the original, so there is no destination
        # directory for a timestamped one.
        self.check_timestamp_dir.setEnabled(self.settings.save_method != SAVE_BACKUP_OVERWRITE)

    def _commit_output_folder(self) -> None:
        text = self.entry_output_folder.text().strip()
        if text != self.settings.output_folder:
            self.settings.output_folder = text

    def _browse_output_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, _("Select Output Folder"), self.entry_output_folder.text() or ""
        )
        if folder:
            self.entry_output_folder.setText(folder)
            self._commit_output_folder()

    def set_process_enabled(self, enabled: bool) -> None:
        self.process_button.setEnabled(enabled)

    def set_busy(self, busy: bool) -> None:
        for widget in self.findChildren(QWidget):
            widget.setEnabled(not busy)
        if not busy:
            self._update_destination_state()
            self._update_knob_state()

    def open_output_folder(self, folder: str) -> None:
        if folder:
            _res = QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
