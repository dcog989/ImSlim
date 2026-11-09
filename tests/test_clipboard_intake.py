from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtGui import QImage

from imslim import clipboard_intake
from imslim.clipboard_intake import ClipboardIntake


def test_paste_directory_is_stable_and_created(tmp_path: Path, monkeypatch) -> None:
    class _Pictures:
        StandardLocation = QStandardPaths.StandardLocation

        @staticmethod
        def writableLocation(_location: QStandardPaths.StandardLocation) -> str:
            return str(tmp_path)

    monkeypatch.setattr(clipboard_intake, "QStandardPaths", _Pictures)
    intake = ClipboardIntake(None)  # pyright: ignore[reportArgumentType]

    first = intake._paste_directory()  # pyright: ignore[reportPrivateUsage]
    second = intake._paste_directory()  # pyright: ignore[reportPrivateUsage]

    assert first == second == str(tmp_path / "ImSlim")
    assert Path(first).is_dir()


def test_saved_paste_is_a_png(tmp_path: Path) -> None:
    intake = ClipboardIntake(None)  # pyright: ignore[reportArgumentType]
    intake._paste_directory = lambda: str(tmp_path)  # pyright: ignore[reportPrivateUsage]
    image = QImage(4, 4, QImage.Format.Format_RGB32)
    image.fill(0x336699)

    path = intake._save_image(image)  # pyright: ignore[reportPrivateUsage]

    assert path is not None
    assert Path(path).is_file()
    assert path.endswith(".png")
