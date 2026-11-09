"""The queue must tell the window when a removal changes the current file."""

from pathlib import Path

from imslim.queue_view import QueueView
from imslim.result_item import ResultItem

_THUMBNAILS = "thumbnails"


class _Settings:
    """The two settings QueueView reads."""

    view_mode = _THUMBNAILS
    thumbnail_size = 64


def _item(tmp_path: Path, name: str) -> ResultItem:
    path = tmp_path / name
    path.write_bytes(b"")
    return ResultItem(filename=str(path), size=1)


def test_clearing_the_queue_clears_the_size_label(tmp_path: Path) -> None:
    view = QueueView(_Settings())  # type: ignore[arg-type]
    view.add_items([_item(tmp_path, "a.png")])

    view.clear()

    assert view.size_label.text() == ""


def test_removing_the_current_thumbnail_emits_the_new_selection(tmp_path: Path) -> None:
    view = QueueView(_Settings())  # type: ignore[arg-type]
    first = _item(tmp_path, "a.png")
    second = _item(tmp_path, "b.png")
    view.add_items([first, second])
    view._set_selection([first, second], anchor=second)
    emitted: list[ResultItem | None] = []
    view.selection_changed.connect(emitted.append)

    view._remove_items([second])

    assert view.selected_item() is first
    assert emitted == [first]
