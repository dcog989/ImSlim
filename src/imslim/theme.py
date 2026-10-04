from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QMenu, QWidget


def input_background_color() -> str:
    """Background for input fields, lifted just above the window color.

    Some dark schemes give input fields a Base darker than the surrounding
    window, which renders as near-black holes. Those fields are lifted above
    the window color so text stays readable; light themes keep their Base.
    """
    palette = QApplication.palette()
    base = palette.color(QPalette.ColorRole.Base)
    window = palette.color(QPalette.ColorRole.Window)
    if base.lightness() < window.lightness():
        return window.lighter(115).name()
    return base.name()


def combo_stylesheet() -> str:
    """QComboBox styling shared by the settings form and the home page.

    Setting a background color forces the stylesheet renderer to draw the
    combo, which is required for the internal padding to shift the text.
    """
    return (
        f"QComboBox {{ padding: 3px 12px 5px 12px; background-color: {input_background_color()}; }}"
    )


def muted_color(fg: QColor, bg: QColor, factor: float = 0.5) -> QColor:
    """Blend the foreground color `factor` toward `bg`.

    Used for muted but readable text on both light and dark themes instead of
    a hardcoded gray. `factor` is the weight given to `bg`; 0.0 keeps `fg`
    unchanged, 1.0 yields `bg` exactly.
    """
    return QColor(
        round(fg.red() * (1.0 - factor) + bg.red() * factor),
        round(fg.green() * (1.0 - factor) + bg.green() * factor),
        round(fg.blue() * (1.0 - factor) + bg.blue() * factor),
    )


def style_menu(menu: QMenu) -> None:
    """Give a context menu an outlined, rounded appearance on any theme.

    A popup is its own top-level window, so a translucent background is
    required: without it the area outside the rounded border is filled with a
    hard rectangle of the menu background instead of showing through.
    """
    palette = QApplication.palette()
    background = palette.color(QPalette.ColorRole.Base)
    border = muted_color(palette.color(QPalette.ColorRole.Text), background, factor=0.7)
    highlight = palette.color(QPalette.ColorRole.Highlight)
    highlighted_text = palette.color(QPalette.ColorRole.HighlightedText)
    menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    menu.setStyleSheet(
        "QMenu {"
        + f" background-color: {background.name()};"
        + f" border: 1px solid {border.name()};"
        + " border-radius: 8px;"
        + " padding: 4px;"
        + " }"
        + " QMenu::item {"
        + " padding: 5px 18px 5px 12px;"
        + " border-radius: 4px;"
        + " }"
        + " QMenu::item:selected {"
        + f" background-color: {highlight.name()};"
        + f" color: {highlighted_text.name()};"
        + " }"
        + " QMenu::separator {"
        + " height: 1px;"
        + " margin: 4px 8px;"
        + f" background-color: {border.name()};"
        + " }"
    )


def apply_muted_palette(
    widget: QWidget,
    factor: float = 0.5,
    *,
    fg_role: QPalette.ColorRole = QPalette.ColorRole.Text,
    bg_role: QPalette.ColorRole = QPalette.ColorRole.Base,
) -> None:
    """Recolor a widget's text roles to a muted blend of its own palette.

    Muted but readable on both light and dark themes instead of a hardcoded
    gray. Blends `fg_role` toward `bg_role` and applies the result to the
    Text and WindowText roles.
    """
    palette = widget.palette()
    muted = muted_color(palette.color(fg_role), palette.color(bg_role), factor)
    palette.setColor(QPalette.ColorRole.Text, muted)
    palette.setColor(QPalette.ColorRole.WindowText, muted)
    widget.setPalette(palette)
