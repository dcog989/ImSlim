from PySide6.QtGui import QImage


def to_png(filename: str, output: str) -> None:
    """Decode any QImage-readable image to a PNG file.

    Used as a pre-processing step for formats that the bundled encoders
    cannot read directly (e.g. BMP and TIFF fed to cwebp).
    """
    image = QImage(filename)
    if image.isNull():
        raise RuntimeError(f"Failed to load image: {filename}")
    if not image.save(output, "PNG"):
        raise RuntimeError(f"Failed to write PNG: {output}")
