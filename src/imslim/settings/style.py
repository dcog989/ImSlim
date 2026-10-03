"""Shared visual helpers for the settings tabs."""

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy

from ..theme import apply_muted_palette, combo_stylesheet, input_background_color


def separator() -> QFrame:
    """A 28px-tall horizontal divider whose line color is derived from the
    palette. A plain QFrame HLine draws with the WindowText role, which on
    dark themes is near-white, so the line is recolored to a subtle muted tone
    instead.
    """
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFixedHeight(28)
    apply_muted_palette(
        line,
        factor=0.6,
        fg_role=QPalette.ColorRole.WindowText,
        bg_role=QPalette.ColorRole.Window,
    )
    return line


def form_stylesheet() -> str:
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


def hint_label(hint: str) -> QLabel:
    label = QLabel(hint)
    label.setWordWrap(True)
    label.setMinimumHeight(label.fontMetrics().height() + 4)
    label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

    # Muted but readable on both light and dark themes: blend the text
    # color toward the background instead of a hardcoded gray.
    apply_muted_palette(label)

    hint_font = label.font()
    hint_font.setPointSizeF(hint_font.pointSizeF() * 0.9)
    label.setFont(hint_font)

    return label
