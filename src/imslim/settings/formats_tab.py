from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .._i18n import _
from ..formats import FORMAT_BY_COMPRESSOR, FORMAT_SPECS, FormatSpec, Knob
from ..settings_manager import SettingsManager
from .style import hint_label
from .tab import SettingsTab


class FormatsTab(SettingsTab):
    def __init__(self, settings: SettingsManager, parent: QWidget | None = None) -> None:
        super().__init__(settings, parent)
        self._spins: list[tuple[QSpinBox, str]] = []
        self._checks: list[tuple[QCheckBox, str]] = []
        self._build()
        with self._suspend_signals():
            self._load_values()

    def _build(self) -> None:
        grid = QGridLayout(self)
        grid.setContentsMargins(12, 12, 12, 12)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)

        format_specs = [spec for spec in FORMAT_SPECS if spec.knobs]
        for index, spec in enumerate(format_specs):
            row, column = divmod(index, 2)
            grid.addWidget(self._build_format_group(spec), row, column)
        for column in range(2):
            grid.setColumnStretch(column, 1)
        for row in range((len(format_specs) + 1) // 2):
            grid.setRowStretch(row, 1)

        note_specs = [spec for spec in FORMAT_SPECS if spec.compressor_key.value != spec.key.value]
        if note_specs:
            note_row = (len(format_specs) + 1) // 2
            grid.addWidget(self._build_note_group(note_specs), note_row, 0, 1, 2)

    def _build_format_group(self, spec: FormatSpec) -> QGroupBox:
        group = QGroupBox(spec.title)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        for knob in spec.knobs:
            if knob.kind == "level":
                layout.addLayout(self._spin_row(knob))
            else:
                check = QCheckBox(knob.label)
                check.toggled.connect(self._bool_handler(knob.key))
                self._checks.append((check, knob.key))
                layout.addWidget(check)
                layout.addWidget(hint_label(knob.hint))

        return group

    def _build_note_group(self, note_specs: list[FormatSpec]) -> QGroupBox:
        title = " / ".join(spec.display for spec in note_specs)
        target = FORMAT_BY_COMPRESSOR[note_specs[0].compressor_key]
        text = _(
            "{formats} images are always converted to {target}: they are decoded and "
            + "re-encoded with the {target} settings above. The original file is never "
            + "modified and the compressed result is saved as a new {extension} file."
        ).format(
            formats=title,
            target=target.display,
            extension=target.output_extension,
        )
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 12, 12, 12)
        note = QLabel(text)
        note.setWordWrap(True)
        layout.addWidget(note)
        return group

    def _spin_row(self, knob: Knob) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setSpacing(2)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        label_widget = QLabel(knob.label)
        label_widget.setMinimumWidth(110)
        spin = QSpinBox()
        spin.setRange(knob.lower, knob.upper)
        spin.valueChanged.connect(self._int_handler(knob.key))
        self._spins.append((spin, knob.key))
        row.addWidget(label_widget)
        row.addStretch(1)
        row.addWidget(spin)
        column.addLayout(row)

        column.addWidget(hint_label(knob.hint))

        return column

    def _load_values(self) -> None:
        for spin, key in self._spins:
            spin.setValue(int(self.settings.knob(key)))
        for check, key in self._checks:
            check.setChecked(bool(self.settings.knob(key)))
