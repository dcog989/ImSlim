import pytest

from imslim.batch_options import BatchOptions
from imslim.formats import Format
from imslim.result_item import ResultItem
from imslim.result_item_manager import ResultItemManager, is_generated_output
from imslim.settings_manager import (
    SAVE_BACKUP_OVERWRITE,
    SAVE_NEXT_TO_ORIGINAL,
    SAVE_OUTPUT_FOLDER,
)

_TIMESTAMP = "20240102030405"


@pytest.fixture
def frozen_timestamp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("imslim.result_item_manager.time.strftime", lambda _fmt: _TIMESTAMP)


def _options(
    save_method: int = SAVE_NEXT_TO_ORIGINAL,
    output_folder: str = "",
    *,
    timestamp_dir: bool = False,
    target_format: Format = Format.KEEP,
) -> BatchOptions:
    return BatchOptions(
        save_method=save_method,
        target_format=target_format,
        output_folder=output_folder,
        recursive=False,
        lossy=True,
        metadata=True,
        file_attributes=True,
        compression_timeout=60,
        knobs={},
        timestamp_dir=timestamp_dir,
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


def test_timestamp_dir_holds_plain_output_names(tmp_path, frozen_timestamp: None) -> None:
    source = tmp_path / "photo.png"
    source.write_bytes(b"x")
    manager = ResultItemManager(_options(timestamp_dir=True))
    assert manager.begin_batch()

    item = manager.build(str(source))
    manager.prepare(item)

    stamp_dir = tmp_path / f"imslim-{_TIMESTAMP}"
    assert item.new_filename == str(stamp_dir / "photo.png")
    assert stamp_dir.is_dir()
    assert is_generated_output(item.new_filename)


def test_timestamp_dir_is_ignored_when_overwriting_in_place(tmp_path) -> None:
    source = tmp_path / "photo.png"
    source.write_bytes(b"x")
    manager = ResultItemManager(_options(SAVE_BACKUP_OVERWRITE, timestamp_dir=True))
    assert manager.begin_batch()

    item = manager.build(str(source))
    manager.prepare(item)

    assert item.new_filename == str(source)


def test_conversion_overwrite_keeps_the_original_stem(tmp_path) -> None:
    source = tmp_path / "photo.tiff"
    manager = ResultItemManager(_options(SAVE_BACKUP_OVERWRITE, target_format=Format.WEBP))

    assert manager.create_new_filename(str(source), "image/tiff") == str(tmp_path / "photo.webp")


def test_reencoded_overwrite_keeps_the_original_stem(tmp_path) -> None:
    source = tmp_path / "photo.tiff"
    manager = ResultItemManager(_options(SAVE_BACKUP_OVERWRITE))

    assert manager.create_new_filename(str(source), "image/tiff") == str(tmp_path / "photo.webp")


def test_conversion_overwrite_reuses_the_source_path(tmp_path) -> None:
    source = tmp_path / "photo.webp"
    manager = ResultItemManager(_options(SAVE_BACKUP_OVERWRITE, target_format=Format.WEBP))

    assert manager.create_new_filename(str(source), "image/webp") == str(source)


def test_conversion_overwrite_avoids_an_unrelated_file(tmp_path) -> None:
    source = tmp_path / "photo.tiff"
    (tmp_path / "photo.webp").write_bytes(b"existing")
    manager = ResultItemManager(_options(SAVE_BACKUP_OVERWRITE, target_format=Format.WEBP))

    assert manager.create_new_filename(str(source), "image/tiff") == str(tmp_path / "photo-1.webp")


def test_backup_is_created_only_when_overwriting_the_source(tmp_path) -> None:
    options = _options(SAVE_BACKUP_OVERWRITE, target_format=Format.WEBP)
    same = ResultItem(filename=str(tmp_path / "photo.webp"), mime_type="image/webp")
    ResultItemManager(options).prepare(same)
    converted = ResultItem(filename=str(tmp_path / "photo.tiff"), mime_type="image/tiff")
    ResultItemManager(options).prepare(converted)

    assert same.new_filename == same.filename
    assert same.backup_filename
    assert converted.new_filename == str(tmp_path / "photo.webp")
    assert converted.backup_filename == ""
