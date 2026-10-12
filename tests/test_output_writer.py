import os
import stat

import pytest

from imslim.batch_options import BatchOptions
from imslim.formats import FORMAT_DEFAULT_KNOBS, Format
from imslim.output_writer import OutputWriter
from imslim.result_item import ResultItem, ResultState
from imslim.settings_manager import (
    SAVE_BACKUP_OVERWRITE,
    SAVE_NEXT_TO_ORIGINAL,
    SAVE_OUTPUT_FOLDER,
)

_ORIGINAL = b"original image bytes"
_COMPRESSED = b"tiny"


def _options(
    save_method: int = SAVE_NEXT_TO_ORIGINAL,
    output_folder: str = "",
    target_format: Format = Format.KEEP,
    file_attributes: bool = False,
) -> BatchOptions:
    return BatchOptions(
        save_method=save_method,
        target_format=target_format,
        output_folder=output_folder,
        recursive=False,
        lossy=True,
        metadata=True,
        file_attributes=file_attributes,
        compression_timeout=60,
        knobs=FORMAT_DEFAULT_KNOBS,
    )


def _item(source, tmp_file, *, new_filename=None, backup=None) -> ResultItem:
    return ResultItem(
        filename=str(source),
        new_filename=str(new_filename if new_filename is not None else source),
        backup_filename="" if backup is None else str(backup),
        tmp_filename=str(tmp_file),
        size=source.stat().st_size,
    )


def _tmp_file(tmp_path, content: bytes = _COMPRESSED):
    path = tmp_path / ".photo.png.tmp"
    path.write_bytes(content)
    return path


def test_finalize_overwrite_backs_up_before_replacing(tmp_path) -> None:
    source = tmp_path / "photo.png"
    source.write_bytes(_ORIGINAL)
    tmp_file = _tmp_file(tmp_path)
    backup = tmp_path / "photo.BAK.20240102030405.png"
    item = _item(source, tmp_file, backup=backup)

    OutputWriter().finalize(item, _options(SAVE_BACKUP_OVERWRITE))

    assert item.state is ResultState.IDLE
    assert backup.read_bytes() == _ORIGINAL
    assert source.read_bytes() == _COMPRESSED
    assert not tmp_file.exists()


def test_finalize_skips_output_that_is_not_smaller(tmp_path) -> None:
    source = tmp_path / "photo.png"
    source.write_bytes(_COMPRESSED)
    tmp_file = _tmp_file(tmp_path, b"a much larger compressed result")
    new_file = tmp_path / "photo.imslim.png"
    item = _item(source, tmp_file, new_filename=new_file)

    OutputWriter().finalize(item, _options(SAVE_NEXT_TO_ORIGINAL))

    assert item.state is ResultState.SKIPPED
    assert source.read_bytes() == _COMPRESSED
    assert not new_file.exists()
    assert tmp_file.exists()


def test_finalize_next_to_original_leaves_source_untouched(tmp_path) -> None:
    source = tmp_path / "photo.png"
    source.write_bytes(_ORIGINAL)
    tmp_file = _tmp_file(tmp_path)
    new_file = tmp_path / "photo.imslim.20240102030405.png"
    item = _item(source, tmp_file, new_filename=new_file)

    OutputWriter().finalize(item, _options(SAVE_NEXT_TO_ORIGINAL))

    assert source.read_bytes() == _ORIGINAL
    assert new_file.read_bytes() == _COMPRESSED
    assert not tmp_file.exists()


def test_finalize_output_folder_leaves_source_untouched(tmp_path) -> None:
    source = tmp_path / "photo.png"
    source.write_bytes(_ORIGINAL)
    output_folder = tmp_path / "out"
    output_folder.mkdir()
    new_file = output_folder / "photo.imslim.20240102030405.png"
    tmp_file = output_folder / ".photo.imslim.20240102030405.png.tmp"
    tmp_file.write_bytes(_COMPRESSED)
    item = _item(source, tmp_file, new_filename=new_file)

    OutputWriter().finalize(item, _options(SAVE_OUTPUT_FOLDER, str(output_folder)))

    assert source.read_bytes() == _ORIGINAL
    assert new_file.read_bytes() == _COMPRESSED
    assert not tmp_file.exists()


def test_finalize_keeps_larger_output_when_converting(tmp_path) -> None:
    source = tmp_path / "photo.png"
    source.write_bytes(_COMPRESSED)
    tmp_file = _tmp_file(tmp_path, b"converted output that grew")
    new_file = tmp_path / "photo.imslim.20240102030405.webp"
    item = _item(source, tmp_file, new_filename=new_file)

    OutputWriter().finalize(item, _options(SAVE_NEXT_TO_ORIGINAL, target_format=Format.WEBP))

    assert item.state is not ResultState.SKIPPED
    assert source.read_bytes() == _COMPRESSED
    assert new_file.read_bytes() == b"converted output that grew"


def test_finalize_raises_when_temp_file_is_missing(tmp_path) -> None:
    source = tmp_path / "photo.png"
    source.write_bytes(_ORIGINAL)
    item = _item(source, tmp_path / "gone.tmp")

    with pytest.raises(FileNotFoundError):
        OutputWriter().finalize(item, _options())

    assert source.read_bytes() == _ORIGINAL


def test_finalize_restores_mode_and_times(tmp_path) -> None:
    source = tmp_path / "photo.png"
    source.write_bytes(_ORIGINAL)
    os.chmod(source, 0o640)
    os.utime(source, (1_700_000_000, 1_700_000_000))
    src_stat = source.stat()
    tmp_file = _tmp_file(tmp_path)
    backup = tmp_path / "photo.BAK.20240102030405.png"
    item = _item(source, tmp_file, backup=backup)
    item.mode = src_stat.st_mode
    item.atime = float(src_stat.st_atime)
    item.mtime = float(src_stat.st_mtime)

    OutputWriter().finalize(item, _options(SAVE_BACKUP_OVERWRITE, file_attributes=True))

    final = source.stat()
    assert stat.S_IMODE(final.st_mode) == 0o640
    assert final.st_atime == pytest.approx(1_700_000_000, abs=1)
    assert final.st_mtime == pytest.approx(1_700_000_000, abs=1)
