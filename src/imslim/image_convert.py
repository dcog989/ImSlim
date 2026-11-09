import os
import sys


def to_png(filename: str, output: str) -> None:
    """Decode any QImage-readable image to a PNG file.

    Used as a pre-processing step for formats that the bundled encoders
    cannot read directly (e.g. BMP and TIFF fed to cwebp). Runs in its own
    process (see conversion.py) so cancel and timeout can stop it.
    """
    # Imported lazily: QtGui needs system GL libraries that a headless test or
    # lint environment may lack, and importing this module must not require them.
    from PySide6.QtGui import QImageReader

    # The default 256 MB limit rejects large scans; the caller's decode slots
    # bound how many full-size images may be in memory at once.
    QImageReader.setAllocationLimit(0)
    reader = QImageReader(filename)
    reader.setAutoTransform(True)  # apply EXIF orientation, unlike QImage(path)
    image = reader.read()
    if image.isNull():
        raise RuntimeError(f"Failed to load image: {filename}: {reader.errorString()}")
    # PySide6's stub types `format` as bytes, but the runtime requires str.
    if not image.save(output, "PNG"):  # pyright: ignore[reportCallIssue, reportArgumentType]
        raise RuntimeError(f"Failed to write PNG: {output}")


if __name__ == "__main__":
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtGui import QGuiApplication

    _app = QGuiApplication(sys.argv[:1])
    to_png(sys.argv[1], sys.argv[2])
