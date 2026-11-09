from pathlib import Path

from imslim.clipboard_intake import ClipboardIntake


def _intake(directory: Path) -> ClipboardIntake:
    intake = ClipboardIntake(None)  # pyright: ignore[reportArgumentType]
    intake._paste_temp_dir = str(directory)  # pyright: ignore[reportPrivateUsage]
    return intake


def test_cleanup_keeps_the_dir_while_a_queued_path_is_inside(tmp_path: Path) -> None:
    intake = _intake(tmp_path)
    pasted = tmp_path / "pasted-1.png"
    pasted.write_bytes(b"image")

    intake.cleanup_unless_used([str(pasted)])

    assert tmp_path.exists()


def test_cleanup_removes_the_dir_when_nothing_uses_it(tmp_path: Path) -> None:
    intake = _intake(tmp_path)
    (tmp_path / "pasted-1.png").write_bytes(b"image")

    intake.cleanup_unless_used(["/somewhere/else.png"])

    assert not tmp_path.exists()
