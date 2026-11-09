from PySide6.QtGui import QImage

from imslim.properties import image_details
from imslim.result_item import ResultItem


def test_image_details_reports_exact_size_and_dimensions(tmp_path) -> None:
    path = tmp_path / "photo.png"
    image = QImage(40, 30, QImage.Format.Format_RGB32)
    image.fill(0x336699)
    assert image.save(str(path), "PNG")

    item = ResultItem(filename=str(path), mime_type="image/png", size=path.stat().st_size)
    details = dict(image_details(item))

    assert details["Name"] == "photo.png"
    assert details["Dimensions"] == "40 × 30 px"
    assert details["Type"] == "image/png · .png"
    assert str(path.stat().st_size) in details["Size"]


def test_image_details_uses_the_decoder_size_when_qt_cannot_read(tmp_path, monkeypatch) -> None:
    path = tmp_path / "photo.jxl"
    path.write_bytes(b"not a Qt image")
    item = ResultItem(filename=str(path), mime_type="image/jxl", size=path.stat().st_size)
    monkeypatch.setattr(
        "imslim.properties.read_exif_and_size",
        lambda _path, _mime: ((5000, 4000), []),
    )

    details = dict(image_details(item))

    assert details["Dimensions"] == "5000 × 4000 px"


def test_image_details_flags_a_missing_file(tmp_path) -> None:
    item = ResultItem(filename=str(tmp_path / "gone.png"), mime_type="image/png", size=10)
    details = dict(image_details(item))

    assert details["Status"] == "File is missing"
    assert "Dimensions" not in details
