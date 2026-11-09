"""Column 1: the queue of files waiting to be processed."""

import os
from collections.abc import Callable
from functools import partial
from typing import cast, override

from PySide6.QtCore import (
    QEvent,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QPoint,
    QRect,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QContextMenuEvent,
    QIcon,
    QImage,
    QKeySequence,
    QPainter,
    QPalette,
    QPen,
    QPixmap,
    QShortcut,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ._i18n import _
from .format import sizeof_fmt
from .formats import ALLOWED_MIME_TYPES
from .icons import (
    circle_minus_icon,
    circle_x_icon,
    download_icon,
    folder_tree_icon,
    image_icon,
    layout_grid_icon,
    list_collapse_icon,
)
from .image_utils import create_thumbnail_qimage
from .item_menu import build_item_menu
from .result_item import ResultItem
from .result_item_row import ResultItemRow, item_summary
from .settings_manager import SettingsManager
from .theme import accent_color, accent_colors, apply_muted_palette, muted_color, style_menu
from .widgets import plain_tooltip
from .workers import TASK_PRIORITY_LOW, Task, start_task

# Rows are built in small timer-driven chunks so adding a huge folder does not
# block the UI thread building thousands of widgets in one event-loop iteration.
_ROW_CHUNK_SIZE = 50
# One widget per file does not scale to folders with tens of thousands of
# images; the rest are still counted, just not listed.
_MAX_ROWS = 500
# A thumbnail costs a full decode; only the rows a user is likely to look at
# get one.
_MAX_THUMBNAILS = 100
_THUMBNAIL_SIZE_MIN = 32
_THUMBNAIL_SIZE_MAX = 256
_THUMBNAIL_STEP = 16
# A held Ctrl+wheel arrives as many steps; rebuild once it settles instead of
# starting a decode for every step.
_REBUILD_DELAY_MS = 150
_SELECTION_BORDER_WIDTH = 4

_VIEW_DETAILS = "details"
_VIEW_THUMBNAILS = "thumbnails"


class _GridThumbnail(Task):
    """Decode one grid thumbnail off the UI thread."""

    loaded: Signal = Signal(object)

    def __init__(self, filename: str, size: int) -> None:
        super().__init__()
        self._filename: str = filename
        self._size: int = size

    @override
    def run(self) -> None:
        try:
            self.loaded.emit(create_thumbnail_qimage(self._filename, self._size, self._size))
        finally:
            self.finished.emit()


class _ThumbnailDelegate(QStyledItemDelegate):
    """Mark a selected thumbnail with a border instead of the native style's
    underline below the icon."""

    @override
    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        icon = cast(object, index.data(Qt.ItemDataRole.DecorationRole))
        if not isinstance(icon, QIcon):
            super().paint(painter, option, index)
            return
        size = option.decorationSize
        rect = QRect(option.rect.center() - QPoint(size.width() // 2, size.height() // 2), size)
        icon.paint(painter, rect, Qt.AlignmentFlag.AlignCenter)
        if option.state & QStyle.StateFlag.State_Selected:
            half = _SELECTION_BORDER_WIDTH // 2
            painter.setPen(QPen(accent_color(), _SELECTION_BORDER_WIDTH))
            # Inset by half the pen so the border sits outside the image.
            painter.drawRect(rect.adjusted(-half, -half, half, half))


class QueueView(QWidget):
    """The persistent file queue: add, remove, select, and show per-file state."""

    add_files_requested: Signal = Signal()
    add_directory_requested: Signal = Signal()
    selection_changed: Signal = Signal(object)

    def __init__(self, settings: SettingsManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings: SettingsManager = settings
        self._items: list[ResultItem] = []
        self._total_size: int = 0
        self._seen: set[str] = set()
        self._rows: dict[ResultItem, ResultItemRow] = {}
        self._grid_entries: dict[ResultItem, QListWidgetItem] = {}
        self._pending_rows: list[ResultItem] = []
        # Ordered selection; the last entry is the one the comparison pane shows.
        self._selected: list[ResultItem] = []
        self._anchor: int | None = None
        # The file the window was last told to show; repeated clicks on the same
        # row must not re-run the preview encode.
        self._reported_selection: ResultItem | None = None
        self._busy: bool = False
        # Set while this view updates the grid itself, so the grid's selection
        # signals do not overwrite the selection being applied.
        self._syncing_selection: bool = False
        self._apply_background()
        self._build()
        self._build_empty_page()

        self._row_timer: QTimer = QTimer(self)
        self._row_timer.setSingleShot(True)
        self._row_timer.setInterval(0)
        _res = self._row_timer.timeout.connect(self._flush_rows)

        self._rebuild_timer: QTimer = QTimer(self)
        self._rebuild_timer.setSingleShot(True)
        self._rebuild_timer.setInterval(_REBUILD_DELAY_MS)
        _res = self._rebuild_timer.timeout.connect(self._rebuild_view)

        delete = QShortcut(QKeySequence.StandardKey.Delete, self)
        _res = delete.activated.connect(self.remove_selected)

    # ------------------------------------------------------------------ build
    def _apply_background(self) -> None:
        """Give the queue a shade distinct from the options column."""
        # Read the application palette, not our own: a previously applied tint
        # would otherwise be blended into itself on every theme refresh.
        palette = QPalette(QApplication.palette())
        window = palette.color(QPalette.ColorRole.Window)
        base = palette.color(QPalette.ColorRole.Base)
        palette.setColor(QPalette.ColorRole.Window, muted_color(window, base, 0.8))
        self.setPalette(palette)
        self.setAutoFillBackground(True)

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        icon_color = self.palette().color(self.palette().ColorRole.WindowText)
        accent_icon_color = self.palette().color(self.palette().ColorRole.HighlightedText)
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 8, 10, 6)
        header_layout.setSpacing(6)

        self.add_files_button: QToolButton
        self.add_files_glyph: QLabel
        self.add_files_button, self.add_files_glyph = self._make_add_button(
            image_icon(accent_icon_color, 22), _("Add files"), self.add_files_requested.emit
        )
        self.add_directory_button: QToolButton
        self.add_directory_glyph: QLabel
        self.add_directory_button, self.add_directory_glyph = self._make_add_button(
            folder_tree_icon(accent_icon_color, 22),
            _("Add a directory"),
            self.add_directory_requested.emit,
        )
        self.view_button: QToolButton = self._make_button(
            QIcon(), self._view_tooltip(), self._toggle_view, size=30, icon_size=20
        )
        self.remove_button: QToolButton = self._make_button(
            circle_minus_icon(icon_color, 18),
            _("Remove selected files from queue"),
            self.remove_selected,
        )
        self.clear_button: QToolButton = self._make_button(
            circle_x_icon(icon_color, 18),
            _("Clear entire queue"),
            self.clear,
        )
        header_layout.addWidget(self.add_files_button)
        header_layout.addWidget(self.add_directory_button)
        header_layout.addStretch(1)
        header_layout.addWidget(self.view_button)
        header_layout.addWidget(self.remove_button)
        header_layout.addWidget(self.clear_button)
        layout.addWidget(header)

        self.stack: QStackedWidget = QStackedWidget()
        self.empty_page: QWidget = QWidget()
        self.list_page: QWidget = QWidget()

        self.rows_container: QWidget = QWidget()
        self.rows_layout: QVBoxLayout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(8, 0, 8, 8)
        self.rows_layout.setSpacing(2)
        self.rows_layout.addStretch(1)

        self.scroll_area: QScrollArea = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        # Rows elide; a horizontal scrollbar would only hide the names.
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setWidget(self.rows_container)
        self.scroll_area.viewport().setAutoFillBackground(True)
        self.scroll_area.viewport().setBackgroundRole(QPalette.ColorRole.Window)
        self.scroll_area.viewport().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        _res = self.scroll_area.viewport().customContextMenuRequested.connect(
            self._on_viewport_context_menu
        )

        list_layout = QVBoxLayout(self.list_page)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.addWidget(self.scroll_area)
        self.limit_label: QLabel = QLabel()
        self.limit_label.setWordWrap(True)
        self.limit_label.setContentsMargins(12, 0, 12, 8)
        self.limit_label.hide()

        self.grid: QListWidget = QListWidget()
        self.grid.setViewMode(QListWidget.ViewMode.IconMode)
        self.grid.setMovement(QListWidget.Movement.Static)
        self.grid.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.grid.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.grid.setWordWrap(True)
        self.grid.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.grid.setFrameShape(QFrame.Shape.NoFrame)
        self.grid.setStyleSheet("QListWidget { background-color: transparent; }")
        self.grid.setItemDelegate(_ThumbnailDelegate(self.grid))
        self.grid.viewport().setAutoFillBackground(False)
        self.grid.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.grid.viewport().installEventFilter(self)
        _res = self.grid.customContextMenuRequested.connect(self._on_grid_menu)
        _res = self.grid.itemSelectionChanged.connect(self._on_grid_selection)

        _res = self.stack.addWidget(self.empty_page)
        _res = self.stack.addWidget(self.list_page)
        _res = self.stack.addWidget(self.grid)
        layout.addWidget(self.stack, 1)
        # Outside the pages so the row cap is visible in both list and grid.
        layout.addWidget(self.limit_label)

        status = QWidget()
        status_layout = QHBoxLayout(status)
        status_layout.setContentsMargins(12, 4, 12, 8)
        self.count_label: QLabel = QLabel()
        self.size_label: QLabel = QLabel()
        apply_muted_palette(self.count_label)
        apply_muted_palette(self.size_label)
        status_layout.addWidget(self.count_label)
        status_layout.addStretch(1)
        status_layout.addWidget(self.size_label)
        layout.addWidget(status)

        self.setMinimumWidth(260)
        self._refresh_view_button()
        self._apply_grid_metrics()

    def _build_empty_page(self) -> None:
        layout = QVBoxLayout(self.empty_page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.addStretch(1)

        self.empty_icon: QLabel = QLabel()
        self.empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty_icon)
        self._refresh_empty_icon()

        prompt = QLabel(_("Drop or paste files or directory here to compress."))
        prompt_font = prompt.font()
        prompt_font.setBold(True)
        prompt.setFont(prompt_font)
        prompt.setWordWrap(True)
        prompt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(prompt)
        layout.addStretch(1)

    def _make_add_button(
        self, icon: QIcon, tooltip: str, handler: Callable[[], None]
    ) -> tuple[QToolButton, QLabel]:
        """'Add' then the glyph: Qt's text-beside-icon paints the opposite order."""
        button = QToolButton()
        layout = QHBoxLayout(button)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        label = QLabel(_("Add"))
        glyph = QLabel()
        glyph.setPixmap(icon.pixmap(22))
        for widget in (label, glyph):
            widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            layout.addWidget(widget)
        button.setToolTip(tooltip)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        # QToolButton sizes itself from its text/icon, not from a child layout.
        button.setFixedSize(layout.sizeHint())
        self._apply_add_button_style(button)
        _res = button.clicked.connect(handler)
        return button, glyph

    @staticmethod
    def _apply_add_button_style(button: QToolButton) -> None:
        accent, accent_hover, accent_pressed = accent_colors()
        button.setStyleSheet(
            "QToolButton {"
            + f" background-color: {accent.name()};"
            + " border: none;"
            + f" border-radius: {button.height() // 2}px;"
            + "}"
            + f"QToolButton:hover {{ background-color: {accent_hover.name()}; }}"
            + f"QToolButton:pressed {{ background-color: {accent_pressed.name()}; }}"
            + "QLabel { color: palette(highlighted-text); background: transparent; }"
        )

    @staticmethod
    def _make_button(
        icon: QIcon,
        tooltip: str,
        handler: Callable[[], None],
        *,
        size: int = 28,
        icon_size: int = 18,
    ) -> QToolButton:
        button = QToolButton()
        button.setIcon(icon)
        button.setIconSize(QSize(icon_size, icon_size))
        button.setToolTip(tooltip)
        button.setFixedSize(size, size)
        _res = button.clicked.connect(handler)
        return button

    def _refresh_painted_icons(self) -> None:
        """Repaint the glyphs whose colors were baked into a pixmap at build time."""
        window_text = self.palette().color(QPalette.ColorRole.WindowText)
        highlighted_text = self.palette().color(QPalette.ColorRole.HighlightedText)
        self.add_files_glyph.setPixmap(image_icon(highlighted_text, 22).pixmap(22))
        self.add_directory_glyph.setPixmap(folder_tree_icon(highlighted_text, 22).pixmap(22))
        self.remove_button.setIcon(circle_minus_icon(window_text, 18))
        self.clear_button.setIcon(circle_x_icon(window_text, 18))

    def _refresh_empty_icon(self) -> None:
        bg = self.palette().color(QPalette.ColorRole.Window)
        color = muted_color(accent_color(), bg, factor=0.8)
        self.empty_icon.setPixmap(download_icon(color, 220).pixmap(220))

    # ------------------------------------------------------------------ view
    def refresh_theme(self) -> None:
        """Re-apply colors baked into palettes, pixmaps and stylesheets."""
        self._apply_background()
        self._refresh_view_button()
        self._refresh_painted_icons()
        self._refresh_empty_icon()
        for label in (self.count_label, self.size_label):
            apply_muted_palette(label)
        self._apply_add_button_style(self.add_files_button)
        self._apply_add_button_style(self.add_directory_button)
        for row in self._rows.values():
            row.refresh_theme()

    @property
    def items(self) -> list[ResultItem]:
        return list(self._items)

    def selected_item(self) -> ResultItem | None:
        return self._selected[-1] if self._selected else None

    def selected_items(self) -> list[ResultItem]:
        return list(self._selected)

    def _has_selection(self) -> bool:
        return bool(self._selected)

    def _view_mode(self) -> str:
        return _VIEW_THUMBNAILS if self.settings.view_mode == _VIEW_THUMBNAILS else _VIEW_DETAILS

    def _thumbnail_size(self) -> int:
        return max(_THUMBNAIL_SIZE_MIN, min(_THUMBNAIL_SIZE_MAX, self.settings.thumbnail_size))

    def _view_tooltip(self) -> str:
        if self._view_mode() == _VIEW_DETAILS:
            return _("List view; click for thumbnails")
        return _("Thumbnail view; click for a list")

    def _refresh_view_button(self) -> None:
        icon_color = self.palette().color(self.palette().ColorRole.WindowText)
        icon = (
            list_collapse_icon(icon_color, 20)
            if self._view_mode() == _VIEW_DETAILS
            else layout_grid_icon(icon_color, 20)
        )
        self.view_button.setIcon(icon)
        self.view_button.setToolTip(self._view_tooltip())

    def _toggle_view(self) -> None:
        self.settings.view_mode = (
            _VIEW_DETAILS if self._view_mode() == _VIEW_THUMBNAILS else _VIEW_THUMBNAILS
        )
        self._refresh_view_button()
        self._rebuild_view()
        self._update_chrome()

    def _zoom(self, delta: int) -> None:
        if self._view_mode() != _VIEW_THUMBNAILS:
            return
        current = self._thumbnail_size()
        size = max(_THUMBNAIL_SIZE_MIN, min(_THUMBNAIL_SIZE_MAX, current + delta))
        if size == current:
            return
        self.settings.thumbnail_size = size
        # Resize the tiles now; re-decode once the wheel settles so a burst of
        # steps does not start a decode for every step.
        self._apply_grid_metrics()
        self._rebuild_timer.start()

    @override
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if (
            isinstance(event, QWheelEvent)
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            # Touchpads and smooth scrolling report less than one wheel notch.
            delta = event.angleDelta().y() or event.pixelDelta().y()
            if delta:
                steps = abs(delta) // 120 or 1
                self._zoom((steps if delta > 0 else -steps) * _THUMBNAIL_STEP)
                return True
        return super().eventFilter(watched, event)

    # ----------------------------------------------------------- context menu
    def _on_viewport_context_menu(self, position: QPoint) -> None:
        self._show_area_menu(self.scroll_area.viewport().mapToGlobal(position))

    @override
    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        self._show_area_menu(event.globalPos())
        event.accept()

    def _show_area_menu(self, global_pos: QPoint) -> None:
        menu = QMenu(self)
        style_menu(menu)
        add_files = QAction(_("Add Files…"), menu)
        _res = add_files.triggered.connect(self.add_files_requested.emit)
        add_directory = QAction(_("Add Directory…"), menu)
        _res = add_directory.triggered.connect(self.add_directory_requested.emit)
        menu.addAction(add_files)
        menu.addAction(add_directory)
        if self._items:
            _res = menu.addSeparator()
            remove = QAction(_("Remove from Queue"), menu)
            remove.setEnabled(not self._busy and self._has_selection())
            _res = remove.triggered.connect(self.remove_selected)
            clear = QAction(_("Clear Queue"), menu)
            clear.setEnabled(not self._busy)
            _res = clear.triggered.connect(self.clear)
            menu.addAction(remove)
            menu.addAction(clear)
        _res = menu.exec(global_pos)

    def _on_grid_menu(self, position: QPoint) -> None:
        entry = self.grid.itemAt(position)
        global_pos = self.grid.viewport().mapToGlobal(position)
        item = self._grid_item(entry)
        if item is None:
            self._show_area_menu(global_pos)
            return
        menu = build_item_menu(item, self)
        if not menu.isEmpty():
            _res = menu.exec(global_pos)

    # ----------------------------------------------------------------- items
    def add_items(self, items: list[ResultItem]) -> None:
        added = False
        for item in items:
            key = os.path.normcase(os.path.realpath(item.filename))
            if key in self._seen:
                continue
            self._seen.add(key)
            self._items.append(item)
            self._total_size += item.size
            if self._view_mode() == _VIEW_THUMBNAILS:
                self._add_grid_entry(item)
            else:
                self._queue_row(item)
            added = True
        if added:
            self._update_chrome()

    def _queue_row(self, item: ResultItem) -> None:
        if len(self._rows) + len(self._pending_rows) >= _MAX_ROWS:
            self._show_row_limit()
            return
        self._pending_rows.append(item)
        if not self._row_timer.isActive():
            self._row_timer.start()

    def _show_row_limit(self) -> None:
        # Adding thousands of files calls this per item; only touch the label once.
        if not self.limit_label.isHidden():
            return
        self.limit_label.setText(
            _("Showing only the first %d files; all of them are still processed.") % _MAX_ROWS
        )
        self.limit_label.show()

    def _flush_rows(self) -> None:
        if not self._pending_rows:
            return
        batch = self._pending_rows[:_ROW_CHUNK_SIZE]
        del self._pending_rows[:_ROW_CHUNK_SIZE]
        self.rows_container.setUpdatesEnabled(False)
        try:
            for item in batch:
                row = self._build_row(item, len(self._rows))
                self.rows_layout.insertWidget(self.rows_layout.count() - 1, row)
                self._rows[item] = row
        finally:
            self.rows_container.setUpdatesEnabled(True)
        if self._pending_rows:
            self._row_timer.start()

    def _build_row(self, item: ResultItem, index: int) -> ResultItemRow:
        row = ResultItemRow(item)
        row.set_alternate(index % 2 == 1)
        row.set_selected(item in self._selected)
        _res = row.clicked.connect(partial(self._on_row_clicked, item))
        return row

    def _rebuild_view(self) -> None:
        """Recreate the active view after a view or thumbnail-size change."""
        self._rebuild_timer.stop()
        selected = self.selected_items()
        self._pending_rows.clear()
        self._row_timer.stop()
        self._clear_rows()
        # grid.clear() emits itemSelectionChanged; without the guard it would
        # overwrite the selection this rebuild is about to restore.
        self._syncing_selection = True
        try:
            self.grid.clear()
        finally:
            self._syncing_selection = False
        self._grid_entries.clear()
        self._selected = [item for item in selected if item in self._items]
        self.limit_label.hide()
        if self._view_mode() == _VIEW_THUMBNAILS:
            self._apply_grid_metrics()
            for item in self._items[:_MAX_ROWS]:
                self._add_grid_entry(item)
            if len(self._items) > _MAX_ROWS:
                self._show_row_limit()
        else:
            # Reuse the chunked path: a synchronous rebuild of 500 rows freezes the UI.
            for item in self._items:
                self._queue_row(item)
        self._restore_selection()

    def _apply_grid_metrics(self) -> None:
        size = self._thumbnail_size()
        self.grid.setIconSize(QSize(size, size))
        self.grid.setGridSize(QSize(size + 16, size + 16))
        for entry in self._grid_entries.values():
            entry.setSizeHint(QSize(size + 16, size + 16))

    def _add_grid_entry(self, item: ResultItem) -> None:
        if len(self._grid_entries) >= _MAX_ROWS:
            self._show_row_limit()
            return
        entry = QListWidgetItem()
        size = self._thumbnail_size()
        entry.setSizeHint(QSize(size + 16, size + 16))
        entry.setData(Qt.ItemDataRole.UserRole, item)
        entry.setToolTip(plain_tooltip(item.filename))
        self.grid.addItem(entry)
        self._grid_entries[item] = entry
        self._refresh_grid_entry(item)
        if len(self._grid_entries) <= _MAX_THUMBNAILS:
            task = _GridThumbnail(item.filename, size)
            _res = task.loaded.connect(partial(self._set_grid_icon, item, size))
            start_task(task, TASK_PRIORITY_LOW)

    def _set_grid_icon(self, item: ResultItem, size: int, image: object) -> None:
        entry = self._grid_entries.get(item)
        if entry is None or size != self._thumbnail_size():
            return
        if isinstance(image, QImage):
            entry.setIcon(QIcon(QPixmap.fromImage(image)))
        else:
            entry.setIcon(QIcon())
        # The item was inserted without an icon, so its size hint is text-only
        # until the delegate sees one.
        self.grid.scheduleDelayedItemsLayout()

    def _refresh_grid_entry(self, item: ResultItem) -> None:
        entry = self._grid_entries.get(item)
        if entry is None:
            return
        entry.setToolTip(plain_tooltip(f"{item.filename}\n{item_summary(item)}"))

    def _on_grid_selection(self) -> None:
        if self._syncing_selection:
            return
        selected = [self._grid_item(entry) for entry in self.grid.selectedItems()]
        self._selected = [item for item in selected if item is not None]
        current: QListWidgetItem | None = self.grid.currentItem()
        current_item = self._grid_item(current)
        if current_item is not None and current_item in self._items:
            self._anchor = self._items.index(current_item)
        if current_item is not None and current_item in self._selected:
            self._report_selection(current_item)
        elif self._selected:
            self._report_selection(self._selected[-1])
        else:
            self._report_selection(None)
        self._update_buttons()

    @staticmethod
    def _grid_item(entry: QListWidgetItem | None) -> ResultItem | None:
        if entry is None:
            return None
        item = cast(object, entry.data(Qt.ItemDataRole.UserRole))
        return item if isinstance(item, ResultItem) else None

    def _sync_grid_selection(self) -> None:
        """Apply `_selected` to the grid without its signals overwriting it."""
        self._syncing_selection = True
        try:
            self.grid.clearSelection()
            for item in self._selected:
                entry = self._grid_entries.get(item)
                if entry is not None:
                    entry.setSelected(True)
            current_item = self.selected_item()
            current = self._grid_entries.get(current_item) if current_item is not None else None
            if current is not None:
                self.grid.setCurrentItem(current)
        finally:
            self._syncing_selection = False

    def _restore_selection(self) -> None:
        current = self.selected_item()
        if current is None:
            return
        if self._view_mode() == _VIEW_THUMBNAILS:
            self._sync_grid_selection()
        else:
            row = self._rows.get(current)
            if row is not None:
                row.set_selected(True)

    def _clear_rows(self) -> None:
        while self.rows_layout.count() > 1:
            layout_item = self.rows_layout.takeAt(0)
            if layout_item is None:
                continue
            widget = layout_item.widget()
            if widget is None:
                continue
            widget.deleteLater()
        self._rows.clear()

    def update_item(self, item: ResultItem) -> None:
        row = self._rows.get(item)
        if row is not None:
            row.refresh()
        self._refresh_grid_entry(item)

    def _update_chrome(self) -> None:
        count = len(self._items)
        self.count_label.setText(
            _("1 file") if count == 1 else _("{count} files").format(count=count)
        )
        self.size_label.setText(sizeof_fmt(self._total_size) if self._total_size else "")
        if not self._items:
            self.stack.setCurrentWidget(self.empty_page)
        elif self._view_mode() == _VIEW_THUMBNAILS:
            self.stack.setCurrentWidget(self.grid)
        else:
            self.stack.setCurrentWidget(self.list_page)
        self._update_buttons()

    def _update_buttons(self) -> None:
        has_items = bool(self._items)
        self.add_files_button.setEnabled(not self._busy)
        self.add_directory_button.setEnabled(not self._busy)
        self.remove_button.setEnabled(has_items and not self._busy and self._has_selection())
        self.clear_button.setEnabled(has_items and not self._busy)

    # ------------------------------------------------------------- selection
    def select(self, item: ResultItem) -> None:
        self._set_selection([item], anchor=item)
        if self._view_mode() == _VIEW_THUMBNAILS:
            self._sync_grid_selection()

    def _on_row_clicked(self, item: ResultItem) -> None:
        modifiers = QApplication.keyboardModifiers()
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            selection = [entry for entry in self._selected if entry is not item]
            if len(selection) == len(self._selected):
                selection.append(item)
            self._set_selection(selection, anchor=item)
            return
        if (
            modifiers & Qt.KeyboardModifier.ShiftModifier
            and self._anchor is not None
            and item in self._items
        ):
            end = self._items.index(item)
            span = self._items[min(self._anchor, end) : max(self._anchor, end) + 1]
            self._set_selection(list(span), anchor=None, emit=item)
            return
        self.select(item)

    def _set_selection(
        self,
        selection: list[ResultItem],
        *,
        anchor: ResultItem | None,
        emit: ResultItem | None = None,
    ) -> None:
        self._selected = selection
        # The clicked item is the one the comparison pane shows, so make it the
        # last entry even when a backwards Shift-click built the range ascending.
        if emit is not None and emit in self._selected:
            self._selected.remove(emit)
            self._selected.append(emit)
        if anchor is not None and anchor in self._items:
            self._anchor = self._items.index(anchor)
        for entry, row in self._rows.items():
            row.set_selected(entry in selection)
        current = emit if emit is not None else self.selected_item()
        self._report_selection(current)
        self._update_buttons()

    def _report_selection(self, current: ResultItem | None) -> None:
        """Tell the window which file to show, once per real change."""
        if current is self._reported_selection:
            return
        self._reported_selection = current
        self.selection_changed.emit(current)

    def _select_fallback(self) -> None:
        if not self._items:
            self._selected = []
            self._report_selection(None)
            return
        self.select(self._items[0])

    # --------------------------------------------------------------- removal
    def remove_selected(self) -> None:
        selected = self.selected_items()
        if not selected or self._busy:
            return
        self._remove_items(selected)

    def _remove_items(self, items: list[ResultItem]) -> None:
        remove = set(items)
        if not remove:
            return
        self._items = [item for item in self._items if item not in remove]
        self._total_size -= sum(item.size for item in remove)
        # takeItem() emits itemSelectionChanged; without the guard it would
        # clear _selected before the fallback below can pick a neighbour.
        self._syncing_selection = True
        try:
            for item in remove:
                self._seen.discard(os.path.normcase(os.path.realpath(item.filename)))
                row = self._rows.pop(item, None)
                if row is not None:
                    row.deleteLater()
                entry = self._grid_entries.pop(item, None)
                if entry is not None:
                    _res = self.grid.takeItem(self.grid.row(entry))
        finally:
            self._syncing_selection = False
        if remove.intersection(self._selected):
            self._selected = [entry for entry in self._selected if entry not in remove]
            if self._selected:
                if self._view_mode() == _VIEW_THUMBNAILS:
                    self._restore_selection()
                else:
                    self._set_selection(self._selected, anchor=self.selected_item())
            else:
                self._select_fallback()
            self._report_selection(self.selected_item())
        # Removing a row shifts every later index; restripe the survivors so the
        # shading stays alternating instead of repeating a shade.
        for index, row in enumerate(self._rows.values()):
            row.set_alternate(index % 2 == 1)
        # Rows hidden by the cap become visible again when a removal frees space.
        if len(self._items) <= _MAX_ROWS:
            self.limit_label.hide()
        if self._view_mode() == _VIEW_THUMBNAILS:
            for item in self._items:
                if len(self._grid_entries) >= _MAX_ROWS:
                    break
                if item not in self._grid_entries:
                    self._add_grid_entry(item)
        else:
            for item in self._items:
                if len(self._rows) + len(self._pending_rows) >= _MAX_ROWS:
                    break
                if item not in self._rows and item not in self._pending_rows:
                    self._queue_row(item)
        self._update_chrome()

    def clear(self) -> None:
        if self._busy:
            return
        self._items = []
        self._total_size = 0
        self._seen.clear()
        self._pending_rows.clear()
        self._row_timer.stop()
        self._rebuild_timer.stop()
        self._clear_rows()
        self._syncing_selection = True
        try:
            self.grid.clear()
        finally:
            self._syncing_selection = False
        self._grid_entries.clear()
        self.limit_label.hide()
        self._selected = []
        self._anchor = None
        self._update_chrome()
        self._report_selection(None)

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._update_buttons()

    @property
    def has_processable_items(self) -> bool:
        return any(item.mime_type in ALLOWED_MIME_TYPES for item in self._items)
