from PySide6.QtCore import QSize
from PySide6.QtGui import QImage

from imslim.image_utils import create_thumbnail_qimage

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
