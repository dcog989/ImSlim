from pathlib import Path

import pytest

from imslim.batch_options import BatchOptions
from imslim.formats import Format
from imslim.result_item import ResultItem, ResultState
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


def test_a_generated_directory_can_be_scanned_from_its_own_root() -> None:
    root = "/images/imslim-20240102030405-1234"

    assert is_generated_output(f"{root}/photo.png")
    assert not is_generated_output(f"{root}/photo.png", root=root)
    assert is_generated_output(f"{root}/imslim-20250101000000-1/photo.png", root=root)


def test_output_path_counter_keeps_names_unique(tmp_path, frozen_timestamp: None) -> None:
    source = tmp_path / "photo.png"
    source.write_bytes(b"x")
    manager = ResultItemManager(_options())
    manager.begin_batch()

    first = manager._output_path(str(source), "imslim", "image/png")
    second = manager._output_path(str(source), "imslim", "image/png")

    stamp = manager._batch_timestamp
    assert first == str(tmp_path / f"photo.imslim.{stamp}.png")
    assert second == str(tmp_path / f"photo.imslim.{stamp}-1.png")


def test_output_path_skips_existing_files(tmp_path, frozen_timestamp: None) -> None:
    source = tmp_path / "photo.png"
    source.write_bytes(b"x")
    manager = ResultItemManager(_options())
    manager.begin_batch()
    stamp = manager._batch_timestamp
    (tmp_path / f"photo.imslim.{stamp}.png").write_bytes(b"existing")

    assert manager._output_path(str(source), "imslim", "image/png") == str(
        tmp_path / f"photo.imslim.{stamp}-1.png"
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

    assert path == str(output_folder / f"photo.imslim.{manager._batch_timestamp}.png")


def test_begin_batch_reports_unwritable_output_folder(tmp_path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_bytes(b"x")
    manager = ResultItemManager(_options(SAVE_OUTPUT_FOLDER, str(blocker / "nested")))

    assert manager.begin_batch() is False


def test_begin_batch_reports_a_missing_output_folder(tmp_path) -> None:
    manager = ResultItemManager(_options(SAVE_OUTPUT_FOLDER, ""))

    assert manager.begin_batch() is False


def test_timestamp_dir_holds_plain_output_names(tmp_path, frozen_timestamp: None) -> None:
    source = tmp_path / "photo.png"
    source.write_bytes(b"x")
    manager = ResultItemManager(_options(timestamp_dir=True))
    assert manager.begin_batch()

    item = manager.build(str(source))
    manager.prepare(item)

    stamp_dir = tmp_path / f"imslim-{manager._batch_timestamp}"
    assert item.new_filename == str(stamp_dir / "photo.png")
    assert stamp_dir.is_dir()
    assert is_generated_output(item.new_filename)


def test_destination_folder_includes_the_timestamp_dir_without_creating_it(tmp_path) -> None:
    manager = ResultItemManager(_options(timestamp_dir=True))

    folder = manager.destination_folder(str(tmp_path / "photo.png"))

    assert folder == str(tmp_path / f"imslim-{manager._batch_timestamp}")
    assert not Path(folder).exists()
    assert manager.destination_folder(str(tmp_path / "photo.png"), timestamp=False) == str(tmp_path)
    assert manager.destination_hint(str(tmp_path / "photo.png")) == str(tmp_path / "imslim-…")


def test_planned_filename_shows_the_file_inside_the_timestamp_hint(tmp_path) -> None:
    manager = ResultItemManager(_options(timestamp_dir=True))

    planned = manager.planned_filename(str(tmp_path / "photo.png"), "image/png")

    assert planned == str(tmp_path / "imslim-…" / "photo.png")


def test_planned_filename_carries_the_target_extension(tmp_path) -> None:
    manager = ResultItemManager(_options(timestamp_dir=True, target_format=Format.WEBP))

    planned = manager.planned_filename(str(tmp_path / "photo.tiff"), "image/tiff")

    assert planned == str(tmp_path / "imslim-…" / "photo.webp")


def test_planned_filename_marks_the_generic_batch_timestamp(tmp_path) -> None:
    manager = ResultItemManager(_options())

    planned = manager.planned_filename(str(tmp_path / "photo.png"), "image/png")

    assert planned == str(tmp_path / "photo.imslim.….png")


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
    (tmp_path / "photo.webp").write_bytes(b"x")
    (tmp_path / "scan.tiff").write_bytes(b"x")
    same = ResultItem(filename=str(tmp_path / "photo.webp"), mime_type="image/webp")
    ResultItemManager(options).prepare(same)
    converted = ResultItem(filename=str(tmp_path / "scan.tiff"), mime_type="image/tiff")
    ResultItemManager(options).prepare(converted)

    assert same.new_filename == same.filename
    assert same.backup_filename
    assert converted.new_filename == str(tmp_path / "scan.webp")
    assert converted.backup_filename == ""


def test_same_format_overwrite_keeps_the_source_extension(tmp_path) -> None:
    source = tmp_path / "photo.jpeg"
    source.write_bytes(b"x")
    manager = ResultItemManager(_options(SAVE_BACKUP_OVERWRITE, target_format=Format.JPEG))

    item = manager.build(str(source))
    manager.prepare(item)

    assert item.new_filename == str(source)
    assert item.backup_filename


def test_prepare_reports_a_source_that_disappeared(tmp_path) -> None:
    source = tmp_path / "photo.png"
    source.write_bytes(b"x")
    manager = ResultItemManager(_options())
    item = manager.build(str(source))
    source.unlink()

    manager.prepare(item)

    assert item.state is ResultState.ERROR
    assert not item.new_filename


def test_prepare_reports_a_timestamp_dir_that_cannot_be_created(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "photo.png"
    source.write_bytes(b"x")
    manager = ResultItemManager(_options(timestamp_dir=True))
    assert manager.begin_batch()
    item = manager.build(str(source))

    def fail(*_args: object, **_kwargs: object) -> None:
        raise OSError("read-only")

    monkeypatch.setattr("imslim.result_item_manager.os.makedirs", fail)
    manager.prepare(item)

    assert item.state is ResultState.ERROR
    assert not item.new_filename


@pytest.mark.parametrize(
    ("mime", "target", "warns"),
    [
        ("image/gif", Format.KEEP, False),
        ("image/gif", Format.WEBP, True),
        ("image/png", Format.KEEP, False),
        ("image/png", Format.PNG, False),
        ("image/png", Format.JPEG, True),
        ("image/webp", Format.KEEP, True),
        ("image/svg+xml", Format.KEEP, False),
        ("image/svg+xml", Format.PNG, True),
    ],
)
def test_animated_warning_matches_the_target(mime: str, target: Format, warns: bool) -> None:
    item = ResultItem(filename="photo", mime_type=mime, is_animated=True)

    warning = ResultItemManager(_options(target_format=target))._animation_warning(item)

    assert bool(warning) is warns


def test_no_animation_warning_for_a_still_image() -> None:
    item = ResultItem(filename="photo", mime_type="image/webp")

    assert ResultItemManager(_options())._animation_warning(item) == ""
