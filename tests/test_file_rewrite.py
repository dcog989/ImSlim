from pathlib import Path

import pytest

from imslim.file_rewrite import rewrite_file


def test_rewrite_replaces_the_file(tmp_path: Path) -> None:
    target = tmp_path / "file.bin"
    target.write_bytes(b"old")

    rewrite_file(str(target), lambda output: output.write(b"new"))

    assert target.read_bytes() == b"new"
    assert not Path(str(target) + ".rewrite").exists()


def test_failed_write_leaves_the_file_untouched(tmp_path: Path) -> None:
    target = tmp_path / "file.bin"
    target.write_bytes(b"old")

    def short_write(output) -> None:
        output.write(b"partial")
        raise OSError("disk full")

    with pytest.raises(OSError):
        rewrite_file(str(target), short_write)

    assert target.read_bytes() == b"old"
    assert not Path(str(target) + ".rewrite").exists()
