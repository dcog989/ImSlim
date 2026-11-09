"""The batch state machine: what reaches the counter and what reaches the encoder."""

import os

import pytest
from PySide6.QtGui import QGuiApplication

from imslim.batch_flow import BatchFlow
from imslim.batch_options import BatchOptions
from imslim.formats import FORMAT_DEFAULT_KNOBS, Format
from imslim.result_item import ResultItem, ResultState
from imslim.settings_manager import SAVE_NEXT_TO_ORIGINAL


class _Settings:
    """The settings BatchOptions.from_settings reads, without QSettings."""

    save_method = SAVE_NEXT_TO_ORIGINAL
    target_format = Format.KEEP
    output_folder = ""
    recursive = False
    lossy = True
    metadata = True
    file_attributes = False
    compression_timeout = 60
    skip_if_larger = True
    timestamp_dir = False

    @staticmethod
    def knob(key: str) -> int | bool:
        return FORMAT_DEFAULT_KNOBS[key]


class _Manager:
    """Records the items handed to the compressor instead of running them."""

    def __init__(self) -> None:
        self.batch: list[ResultItem] | None = None

    def compress(
        self,
        items: list[ResultItem],
        _options: BatchOptions,
        _update: object,
        _enable: object,
    ) -> None:
        self.batch = items

    def cancel(self) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def preview(self, *_args: object) -> None:
        raise AssertionError("preview is not part of a batch")


@pytest.fixture(scope="module", autouse=True)
def _qt_app() -> QGuiApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QGuiApplication.instance() or QGuiApplication([])


def _flow(manager: _Manager) -> BatchFlow:
    return BatchFlow(_Settings(), manager)  # type: ignore[arg-type]


def _item(name: str, state: ResultState = ResultState.IDLE) -> ResultItem:
    return ResultItem(filename=name, mime_type="image/png", state=state)


def test_a_terminal_update_is_counted_once() -> None:
    manager = _Manager()
    flow = _flow(manager)
    item = _item("photo.png")
    flow.start_batch([item])

    item.state = ResultState.RUNNING
    flow.result_updated.emit(item)  # interim refresh, not an outcome
    item.state = ResultState.DONE
    item.new_size = 50
    flow.result_updated.emit(item)
    flow.result_updated.emit(item)  # a queued duplicate arrives after DONE

    assert flow.summary.total == 1
    assert flow.summary.done == 1
    assert flow.summary.compressed == 1


def test_an_analysis_failure_is_counted_without_reaching_the_encoder() -> None:
    manager = _Manager()
    flow = _flow(manager)
    failed = _item("notes.txt", ResultState.ERROR)
    accepted = _item("photo.png")

    flow.start_batch([failed, accepted])

    assert manager.batch == [accepted]
    assert flow.summary.total == 2
    assert flow.summary.done == 1
    assert flow.summary.failed == 1
