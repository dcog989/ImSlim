import pytest

from imslim.batch_options import BatchOptions
from imslim.formats import Format
from imslim.result_item_manager import ResultItemManager, is_generated_output
from imslim.settings_manager import SAVE_NEXT_TO_ORIGINAL, SAVE_OUTPUT_FOLDER

_TIMESTAMP = "20240102030405"


@pytest.fixture
def frozen_timestamp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("imslim.result_item_manager.time.strftime", lambda _fmt: _TIMESTAMP)


def _options(save_method: int = SAVE_NEXT_TO_ORIGINAL, output_folder: str = "") -> BatchOptions:
    return BatchOptions(
        save_method=save_method,
        target_format=Format.KEEP,
        output_folder=output_folder,
        recursive=False,
        lossy=True,
        metadata=True,
        file_attributes=True,
        compression_timeout=60,
        knobs={},
    )


@pytest.mark.parametrize(
    "path",
    [
        "/images/photo.imslim.20240102030405.png",
        "/images/photo.imslim.20240102030405-1.png",
        "/images/photo.BAK.20240102030405.jpg",
        "/images/photo.IMSLIM.20240102030405.webp",
    ],
)
def test_is_generated_output_accepts_app_outputs(path: str) -> None:
    assert is_generated_output(path)


@pytest.mark.parametrize(
    "path",
    [
        "/images/photo.png",
        "/images/photo.imslim.2024.png",  # timestamp too short
        "/images/photo.imslim.20240102030405",  # no extension
        "/images/photo.imslim.20240102030405.png.bak",  # extension has a dot
        "/images/photo.somebak.20240102030405.png",  # unknown marker
    ],
)
def test_is_generated_output_rejects_other_files(path: str) -> None:
    assert not is_generated_output(path)


def test_output_path_counter_keeps_names_unique(tmp_path, frozen_timestamp: None) -> None:
    source = tmp_path / "photo.png"
    source.write_bytes(b"x")
    manager = ResultItemManager(_options())
    manager.begin_batch()

    first = manager._output_path(str(source), "imslim", "image/png")
    second = manager._output_path(str(source), "imslim", "image/png")

    assert first == str(tmp_path / f"photo.imslim.{_TIMESTAMP}.png")
    assert second == str(tmp_path / f"photo.imslim.{_TIMESTAMP}-1.png")


def test_output_path_skips_existing_files(tmp_path, frozen_timestamp: None) -> None:
    source = tmp_path / "photo.png"
    source.write_bytes(b"x")
    (tmp_path / f"photo.imslim.{_TIMESTAMP}.png").write_bytes(b"existing")
    manager = ResultItemManager(_options())
    manager.begin_batch()

    assert manager._output_path(str(source), "imslim", "image/png") == str(
        tmp_path / f"photo.imslim.{_TIMESTAMP}-1.png"
    )


def test_output_path_honours_extension_override(tmp_path, frozen_timestamp: None) -> None:
    source = tmp_path / "photo.png"
    source.write_bytes(b"x")
    manager = ResultItemManager(_options())
    manager.begin_batch()

    assert manager._output_path(str(source), "imslim", "image/png", ".jpg").endswith(".jpg")


def test_output_path_uses_custom_output_folder(tmp_path, frozen_timestamp: None) -> None:
    source = tmp_path / "photo.png"
    source.write_bytes(b"x")
    output_folder = tmp_path / "out"
    manager = ResultItemManager(_options(SAVE_OUTPUT_FOLDER, str(output_folder)))
    assert manager.begin_batch()

    path = manager._output_path(str(source), "imslim", "image/png")

    assert path == str(output_folder / f"photo.imslim.{_TIMESTAMP}.png")


def test_begin_batch_reports_unwritable_output_folder(tmp_path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_bytes(b"x")
    manager = ResultItemManager(_options(SAVE_OUTPUT_FOLDER, str(blocker / "nested")))

    assert manager.begin_batch() is False
