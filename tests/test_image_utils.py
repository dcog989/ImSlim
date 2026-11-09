import struct

from PySide6.QtCore import QSize
from PySide6.QtGui import QImage

from imslim.image_utils import (
    create_thumbnail_qimage,
    get_image_paths_from_folder,
    is_animated_image,
)

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


def test_static_svg_with_reduced_motion_is_not_animated(tmp_path) -> None:
    path = tmp_path / "static.svg"
    path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg">'
        "<style>@media (prefers-reduced-motion){*{animation:none}}</style>"
        '<rect width="10" height="10"/></svg>'
    )

    assert not is_animated_image(str(path), "image/svg+xml")


def test_svg_animation_tag_is_detected(tmp_path) -> None:
    path = tmp_path / "animated.svg"
    path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<rect width="10" height="10"><animate attributeName="x" to="5" dur="1s"/></rect>'
        "</svg>"
    )

    assert is_animated_image(str(path), "image/svg+xml")


def test_folder_scan_filters_and_recurses(tmp_path) -> None:
    (tmp_path / "a.png").write_bytes(b"")
    (tmp_path / "note.txt").write_text("")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "b.jpg").write_bytes(b"")

    assert get_image_paths_from_folder(str(tmp_path)) == [str(tmp_path / "a.png")]
    assert get_image_paths_from_folder(str(tmp_path), recursive=True) == [
        str(tmp_path / "a.png"),
        str(nested / "b.jpg"),
    ]


def test_folder_scan_skips_symlinked_directories(tmp_path) -> None:
    scan = tmp_path / "scan"
    scan.mkdir()
    target = tmp_path / "target"
    target.mkdir()
    (target / "inside.png").write_bytes(b"")
    (scan / "link").symlink_to(target, target_is_directory=True)

    assert get_image_paths_from_folder(str(scan), recursive=True) == []


def test_folder_scan_stops_when_cancelled(tmp_path) -> None:
    (tmp_path / "a.png").write_bytes(b"")

    assert get_image_paths_from_folder(str(tmp_path), is_cancelled=lambda: True) == []
