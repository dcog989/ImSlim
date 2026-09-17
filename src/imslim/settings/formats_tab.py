from typing import cast

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
from ..settings_manager import SettingsManager
from .style import hint_label
from .tab import SettingsTab


class FormatsTab(SettingsTab):
    def __init__(self, settings: SettingsManager, parent: QWidget | None = None) -> None:
        super().__init__(settings, parent)
        self._spins: list[tuple[QSpinBox, str]] = []
        self._checks: list[tuple[QCheckBox, str]] = []
        self._build()
        self._load_values()

    def _build(self) -> None:
        grid = QGridLayout(self)
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
                    (_("Lossy"), quality_hint, "png-lossy-level", 0, 100),
                    (_("Lossless"), level_hint(6), "png-lossless-level", 0, 6),
                ),
                (),
            ),
            (
                "JPEG / Jpegli",
                ((_("Lossy"), quality_hint, "jpg-lossy-level", 0, 100),),
                (
                    (
                        _("Progressive Encode"),
                        _("Render incrementally, from blurry to clear."),
                        "jpg-progressive",
                    ),
                ),
            ),
            (
                "WebP",
                (
                    (_("Lossy"), quality_hint, "webp-lossy-level", 0, 100),
                    (_("Lossless"), level_hint(6), "webp-lossless-level", 0, 6),
                ),
                (),
            ),
            (
                "AVIF",
                (
                    (_("Lossy"), quality_hint, "avif-lossy-level", 0, 100),
                    (_("Lossless"), level_hint(10), "avif-lossless-level", 0, 10),
                ),
                (),
            ),
            (
                "JXL",
                (
                    (_("Lossy"), quality_hint, "jxl-lossy-level", 1, 100),
                    (_("Lossless"), level_hint(10), "jxl-lossless-level", 1, 10),
                ),
                (),
            ),
            (
                "GIF",
                (
                    (_("Lossy"), quality_hint, "gif-lossy-level", 1, 100),
                    (_("Lossless"), level_hint(3), "gif-lossless-level", 1, 3),
                ),
                (),
            ),
            (
                "SVG",
                (),
                (
                    (
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

    def _build_format_group(
        self,
        title: str,
        spins: tuple[tuple[str, str, str, int, int], ...],
        checks: tuple[tuple[str, str, str], ...],
    ) -> QGroupBox:
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        for label, hint, key, lower, upper in spins:
            layout.addLayout(self._spin_row(label, hint, key, lower, upper))

        for label, hint, key in checks:
            check = QCheckBox(label)
            check.toggled.connect(self._bool_handler(key))
            self._checks.append((check, key))
            layout.addWidget(check)
            layout.addWidget(hint_label(hint))

        return group

    def _build_note_group(self, title: str, text: str) -> QGroupBox:
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 12, 12, 12)
        note = QLabel(text)
        note.setWordWrap(True)
        layout.addWidget(note)
        return group

    def _spin_row(
        self,
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
        spin.valueChanged.connect(self._int_handler(key))
        self._spins.append((spin, key))
        row.addWidget(label_widget)
        row.addStretch(1)
        row.addWidget(spin)
        column.addLayout(row)

        column.addWidget(hint_label(hint))

        return column

    def _load_values(self) -> None:
        s = self.settings
        for spin, key in self._spins:
            spin.setValue(cast(int, getattr(s, key.replace("-", "_"))))
        for check, key in self._checks:
            check.setChecked(cast(bool, getattr(s, key.replace("-", "_"))))
