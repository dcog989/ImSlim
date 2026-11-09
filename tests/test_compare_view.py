"""The comparison pane's zoom, pan and decode-queue rules."""

import os
from pathlib import Path

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtGui import QImage

from imslim.compare_view import (
    _MIN_ZOOM,
    _VIEWPORT_AREA_BUDGET,
    CompareView,
    ImagePane,
    _PreviewTask,
)

_PANE_WIDTH = 400
_PANE_HEIGHT = 300
_IMAGE_SIDE = 1000


def _image() -> QImage:
    return QImage(_IMAGE_SIDE, _IMAGE_SIDE, QImage.Format.Format_ARGB32)


def _pane() -> ImagePane:
    pane = ImagePane("empty")
    pane.resize(_PANE_WIDTH, _PANE_HEIGHT)
    pane.set_image(_image())
    return pane


def test_a_loaded_image_fits_the_pane() -> None:
    pane = _pane()

    assert pane.zoom == _MIN_ZOOM


def test_zoom_never_exceeds_the_viewport_budget_or_the_maximum() -> None:
    pane = _pane()
    pane.set_zoom(1_000.0)

    displayed_side = _IMAGE_SIDE * pane._fit_scale() * pane.zoom
    viewport_area = _PANE_WIDTH * _PANE_HEIGHT
    assert displayed_side**2 <= _VIEWPORT_AREA_BUDGET * viewport_area + 1
    assert pane.zoom == pytest.approx(pane.max_zoom())

    pane.set_zoom(0.0)
    assert pane.zoom == _MIN_ZOOM


def test_pan_stops_at_the_image_edge() -> None:
    pane = _pane()
    pane.set_zoom(pane.max_zoom())
    pane.set_pan(QPointF(1_000.0, -1_000.0))

    scale = pane._fit_scale() * pane.zoom
    half_width = max(0.0, (_IMAGE_SIDE - _PANE_WIDTH / scale) / 2)
    half_height = max(0.0, (_IMAGE_SIDE - _PANE_HEIGHT / scale) / 2)
    assert pane._pan.x() == pytest.approx(half_width)
    assert pane._pan.y() == pytest.approx(-half_height)


def test_a_new_selection_waits_for_the_running_decode(monkeypatch: pytest.MonkeyPatch) -> None:
    started: list[_PreviewTask] = []
    monkeypatch.setattr("imslim.compare_view.start_task", started.append)
    view = CompareView()

    view.show_original("/tmp/first.png")
    view.show_original("/tmp/second.png")
    assert len(started) == 1

    view._on_loaded(started[0]._token, None)
    assert len(started) == 2
    assert started[1]._path == "/tmp/second.png"


def test_the_source_is_not_decoded_twice_for_the_processed_pane(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started: list[_PreviewTask] = []
    monkeypatch.setattr("imslim.compare_view.start_task", started.append)
    view = CompareView()

    view.show_original("/tmp/source.png")
    view._on_loaded(started[0]._token, _image())
    view.show_processed("/tmp/source.png")

    assert len(started) == 1
    assert view._processed.has_image()


def test_a_rewritten_output_is_decoded_again(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    started: list[_PreviewTask] = []
    monkeypatch.setattr("imslim.compare_view.start_task", started.append)
    view = CompareView()
    output = tmp_path / "photo.png"
    output.write_bytes(b"first")

    view.show_processed(str(output))
    view._on_loaded(started[-1]._token, _image())
    view.show_processed(str(output))
    assert len(started) == 1

    # An in-place overwrite keeps the path but replaces the pixels.
    output.write_bytes(b"second")
    os.utime(output, (1_600_000_000, 1_600_000_000))
    view.show_processed(str(output))

    assert len(started) == 2
