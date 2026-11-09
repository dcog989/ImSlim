"""Column 2: output options and the Process button."""

import html
from collections.abc import Callable
from functools import partial

from PySide6.QtCore import QSize, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QStandardItemModel
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
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
    START_CUSTOM,
    START_HOME,
    START_LAST,
    START_PICTURES,
    SettingsManager,
)
from .theme import accent_colors, combo_stylesheet, form_stylesheet, spinbox

# (label, save method) in the order the design lists them.
_DESTINATIONS: tuple[tuple[str, int], ...] = (
    (_("Overwrite original"), SAVE_BACKUP_OVERWRITE),
    (_("Next to original"), SAVE_NEXT_TO_ORIGINAL),
    (_("Specified directory"), SAVE_OUTPUT_FOLDER),
)

# (label, start location) in the order shown in the dialog-start combo.
_START_LOCATIONS: tuple[tuple[str, int], ...] = (
    (_("Home"), START_HOME),
    (_("Pictures"), START_PICTURES),
    (_("Last Location"), START_LAST),
    (_("Custom directory"), START_CUSTOM),
)

_BMP_TIFF_NOTE = _(
    "BMP and TIFF images are always decoded and re-encoded to WebP; their "
    + "original format cannot be kept."
)
_SVG_NOTE = _("SVG images are always compressed losslessly.")
_ANIMATION_NOTE = _("Converting an animated image keeps only its first frame.")
_JPEG_NOTE = _("JPEG has no lossless encoder, so it is always compressed lossily.")
_METADATA_NOTE = _("EXIF/XMP metadata is not carried across different formats.")
# Index of each mode in the compression combo.
_LOSSY_INDEX = 0
_LOSSLESS_INDEX = 1


def _format_notes(target: Format) -> list[str]:
    """Caveats that apply to the currently selected output format."""
    if target is Format.KEEP:
        return [_BMP_TIFF_NOTE, _SVG_NOTE]
    if target is Format.JPEG:
        return [_JPEG_NOTE, _ANIMATION_NOTE, _METADATA_NOTE]
    return [_ANIMATION_NOTE, _METADATA_NOTE]


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
        form.setContentsMargins(8, 12, 8, 12)
        form.setSpacing(8)

        self.combo_format: QComboBox = self._combo(
            (_("Same as input"), *(spec.display for spec in TARGET_SPECS)),
            _("Output format. Keep each file's format, or convert everything to one format."),
        )
        self.combo_format.setCurrentIndex(self._format_index())
        _res = self.combo_format.currentIndexChanged.connect(self._on_format_changed)

        format_widget = QWidget()
        format_layout = QHBoxLayout(format_widget)
        format_layout.setContentsMargins(0, 0, 0, 0)
        format_layout.setSpacing(4)
        format_layout.addWidget(self.combo_format)
        format_layout.addWidget(self._info_button())

        self.combo_destination: QComboBox = self._combo(
            tuple(label for label, _value in _DESTINATIONS),
            _(
                "Where processed files go. Overwriting keeps a timestamped "
                + "backup beside the original."
            ),
        )
        self.combo_destination.setCurrentIndex(self._destination_index())
        _res = self.combo_destination.currentIndexChanged.connect(self._on_destination_changed)

        self.combo_start: QComboBox = self._combo(
            tuple(label for label, _value in _START_LOCATIONS),
            _("Where the Add Files and Add Folder dialogs start."),
        )
        self.combo_start.setCurrentIndex(self._start_index())
        _res = self.combo_start.currentIndexChanged.connect(self._on_start_location_changed)

        self.entry_start_folder: QLineEdit = QLineEdit()
        self.entry_start_folder.setPlaceholderText(_("Choose a folder"))
        self.entry_start_folder.setText(self.settings.default_open_dialog_directory)
        _res = self.entry_start_folder.editingFinished.connect(self._commit_start_folder)
        browse_start = QPushButton(_("Browse…"))
        _res = browse_start.clicked.connect(self._browse_start_folder)
        self.start_folder_row: QWidget = QWidget()
        start_layout = QHBoxLayout(self.start_folder_row)
        start_layout.setContentsMargins(0, 0, 0, 0)
        start_layout.addWidget(self.entry_start_folder, 1)
        start_layout.addWidget(browse_start)

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
        self._timestamp_row: QWidget = self._check_row(
            _("New timestamped directory"), self.check_timestamp_dir
        )

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

        self.combo_compression: QComboBox = self._combo(
            (_("Lossy"), _("Lossless")),
            _("Lossy is much smaller with some quality loss; lossless keeps the pixels exact."),
        )
        self.combo_compression.setCurrentIndex(
            _LOSSY_INDEX if self.settings.lossy else _LOSSLESS_INDEX
        )
        _res = self.combo_compression.currentIndexChanged.connect(self._on_compression_changed)
        self._update_compression_mode()

        self.spin_timeout: QSpinBox = spinbox()
        self.spin_timeout.setRange(1, 300)
        self.spin_timeout.setSuffix(" s")
        self.spin_timeout.setValue(self.settings.compression_timeout)
        self.spin_timeout.setToolTip(
            _(
                "Maximum seconds a single compression tool may run on one image "
                + "before it is stopped."
            )
        )
        _res = self.spin_timeout.valueChanged.connect(self._on_timeout)

        self.knobs_container: QWidget = QWidget()
        self.knobs_layout: QVBoxLayout = QVBoxLayout(self.knobs_container)
        self.knobs_layout.setContentsMargins(0, 0, 0, 0)
        self.knobs_layout.setSpacing(8)

        # Labels on the left, each field at its own width on the right.
        self._grid: QGridLayout = QGridLayout()
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(8)
        self._grid.setVerticalSpacing(6)
        self._grid.setColumnStretch(0, 1)
        self._add_field(_("Output format"), format_widget)
        self._add_field(_("Destination"), self.combo_destination)
        self._add_field("", self.output_folder_row, fill=True)
        self._add_wide(self._divider())
        self._add_wide(self._timestamp_row)
        self._add_wide(self._check_row(_("Include sub-directories"), self.check_recursive))
        self._add_wide(self._check_row(_("Keep EXIF and metadata"), self.check_metadata))
        self._add_wide(self._check_row(_("Keep file attributes"), self.check_attributes))
        self._add_wide(
            self._check_row(
                _("Skip if result is larger"), self.check_skip_if_larger, with_hint=False
            )
        )
        self._add_wide(self._divider())
        self._add_field(_("Open on startup"), self.combo_start)
        self._add_field("", self.start_folder_row, fill=True)
        self._add_wide(self._divider())
        self._add_field(_("Tool timeout"), self.spin_timeout)
        self._add_wide(self._divider())
        self._add_field(_("Compression mode"), self.combo_compression)
        self._add_wide(self.knobs_container)
        form.addLayout(self._grid)

        form.addStretch(1)
        self._update_destination_state()
        self._update_start_state()

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
        # The field column right-aligns each field, so its width must not change
        # with the current item: size to the longest entry instead.
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        return combo

    def _add_field(self, label: str, field: QWidget, *, fill: bool = False) -> None:
        """One label on the left, its field at its own width on the right."""
        row = self._grid.rowCount()
        if label:
            text = QLabel(label)
            self._grid.addWidget(
                text, row, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
        if fill:
            self._grid.addWidget(field, row, 1)
        else:
            self._grid.addWidget(field, row, 1, Qt.AlignmentFlag.AlignRight)

    def _add_wide(self, widget: QWidget) -> None:
        self._grid.addWidget(widget, self._grid.rowCount(), 0, 1, 2)

    @staticmethod
    def _check(label: str) -> QCheckBox:
        """A checkbox whose label sits beside it like every other checkbox."""
        check = QCheckBox()
        check.setAccessibleName(label)
        return check

    def _check_row(self, label: str, check: QCheckBox, *, with_hint: bool = True) -> QWidget:
        """A label, its checkbox and the hint button, with one shared gap."""
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        text = QLabel(label)
        text.setBuddy(check)
        hint = check.toolTip()
        if hint:
            text.setToolTip(hint)
        layout.addWidget(text)
        layout.addStretch(1)
        if hint and with_hint:
            info = self._info_button(label, partial(self._show_note_dialog, label, hint))
            layout.addWidget(info)
        layout.addWidget(check)
        return row

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

    def _info_button(
        self, tooltip: str | None = None, action: Callable[[], None] | None = None
    ) -> QPushButton:
        button = QPushButton("!")
        button.setFixedSize(28, 28)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setToolTip(tooltip or _("Format notes"))
        button.setStyleSheet("QPushButton { padding: 0; }")
        _res = button.clicked.connect(action or self._show_format_notes)
        return button

    def _show_format_notes(self) -> None:
        self._show_note_dialog(
            _("Format notes"), "\n\n".join(_format_notes(self.settings.target_format))
        )

    def _show_note_dialog(self, title_text: str, text: str) -> None:
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
        title = QLabel(title_text)
        font = title.font()
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)
        notes = QLabel(text)
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
            specs = tuple(
                sorted((spec for spec in FORMAT_SPECS if spec.knobs), key=lambda spec: spec.display)
            )

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
            knobs_row.addStretch(1)
            # Flags get their own line unless a single level knob shares it: a
            # checkbox beside two level knobs makes the row wider than the pane.
            level_knobs = [knob for knob in spec.knobs if knob.kind != "flag"]
            flags: list[QWidget] = []
            for knob in spec.knobs:
                widget = self._knob_widget(knob)
                if knob.kind == "flag" and len(level_knobs) != 1:
                    flags.append(widget)
                else:
                    knobs_row.addWidget(widget)
            if knobs_row.count() > 1:
                layout.addLayout(knobs_row)
            for widget in flags:
                layout.addWidget(widget)
            self.knobs_layout.addWidget(group)
            self.knobs_layout.addWidget(self._divider())
        if self._knob_widgets:
            self._update_knob_state()

    def _knob_widget(self, knob: Knob) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addStretch(1)
        if knob.kind == "flag":
            check = QCheckBox()
            check.setAccessibleName(knob.label)
            check.setToolTip(knob.hint)
            check.setChecked(bool(self.settings.knob(knob.key)))
            _res = check.toggled.connect(partial(self._on_knob_flag, knob.key))
            self._knob_widgets.append((check, knob))
            layout.addWidget(self._check_row(knob.label, check))
            return row
        label = QLabel(knob.label)
        label.setToolTip(knob.hint)
        layout.addWidget(label)
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

    def _start_index(self) -> int:
        for index, (_label, value) in enumerate(_START_LOCATIONS):
            if value == self.settings.start_location:
                return index
        return 0

    def _on_format_changed(self, index: int) -> None:
        self.settings.target_format = Format.KEEP if index <= 0 else TARGET_SPECS[index - 1].key
        self._update_compression_mode()
        self._rebuild_knobs()
        self.options_changed.emit()

    def _update_compression_mode(self) -> None:
        """JPEG has no lossless encoder, so Lossless is not offered for it."""
        model = self.combo_compression.model()
        if isinstance(model, QStandardItemModel):
            model.item(_LOSSLESS_INDEX).setEnabled(self.settings.target_format is not Format.JPEG)
        if self.settings.target_format is Format.JPEG:
            self.combo_compression.setCurrentIndex(_LOSSY_INDEX)

    def _on_compression_changed(self, index: int) -> None:
        self.settings.lossy = index == 0
        self._update_knob_state()
        self.options_changed.emit()

    def _on_timestamp_dir(self, checked: bool) -> None:
        self.settings.timestamp_dir = checked
        self.options_changed.emit()

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
        self.options_changed.emit()

    def _update_destination_state(self) -> None:
        custom = self.settings.save_method == SAVE_OUTPUT_FOLDER
        self.output_folder_row.setVisible(custom)
        # A backup is written beside the original, so there is no destination
        # directory for a timestamped one.
        self._timestamp_row.setVisible(self.settings.save_method != SAVE_BACKUP_OVERWRITE)

    def _commit_output_folder(self) -> None:
        text = self.entry_output_folder.text().strip()
        if text != self.settings.output_folder:
            self.settings.output_folder = text
            self.options_changed.emit()

    def _browse_output_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, _("Select Output Folder"), self.entry_output_folder.text() or ""
        )
        if folder:
            self.entry_output_folder.setText(folder)
            self._commit_output_folder()

    def _on_start_location_changed(self, index: int) -> None:
        self.settings.start_location = _START_LOCATIONS[index][1]
        self._update_start_state()

    def _update_start_state(self) -> None:
        self.start_folder_row.setVisible(self.settings.start_location == START_CUSTOM)

    def _commit_start_folder(self) -> None:
        self.settings.default_open_dialog_directory = self.entry_start_folder.text().strip()

    def _browse_start_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, _("Select Startup Folder"), self.entry_start_folder.text() or ""
        )
        if folder:
            self.entry_start_folder.setText(folder)
            self._commit_start_folder()

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
