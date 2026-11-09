import struct

from PySide6.QtCore import QSize
from PySide6.QtGui import QImage

from imslim.image_utils import create_thumbnail_qimage, is_animated_image

_BOX = 16


def _save(tmp_path, width: int, height: int) -> str:
    path = tmp_path / f"{width}x{height}.png"
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(0x336699)
    assert image.save(str(path), "PNG")
    return str(path)


def test_thumbnail_is_square_for_a_wide_source(tmp_path) -> None:
    thumbnail = create_thumbnail_qimage(_save(tmp_path, 40, 20), _BOX, _BOX)
    assert thumbnail is not None
    assert thumbnail.size() == QSize(_BOX, _BOX)


def test_thumbnail_is_square_for_a_tall_source(tmp_path) -> None:
    thumbnail = create_thumbnail_qimage(_save(tmp_path, 20, 40), _BOX, _BOX)
    assert thumbnail is not None
    assert thumbnail.size() == QSize(_BOX, _BOX)


def test_static_png_is_not_animated(tmp_path) -> None:
    assert not is_animated_image(_save(tmp_path, 8, 8), "image/png")


def test_png_actl_chunk_marks_it_animated(tmp_path) -> None:
    path = tmp_path / "animated.png"
    actl = struct.pack(">I", 8) + b"acTL" + struct.pack(">II", 2, 0) + b"\x00\x00\x00\x00"
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + actl)

    assert is_animated_image(str(path), "image/png")
