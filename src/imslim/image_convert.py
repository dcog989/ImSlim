import threading

# Decoding happens inside the compression pool, sized for subprocesses. A full
# image is hundreds of MB for a large source, so only a couple may decode at once.
_DECODE_SLOTS = threading.Semaphore(2)


def to_png(filename: str, output: str) -> None:
    """Decode any QImage-readable image to a PNG file.

    Used as a pre-processing step for formats that the bundled encoders
    cannot read directly (e.g. BMP and TIFF fed to cwebp).
    """
    with _DECODE_SLOTS:
        # Imported lazily: QtGui needs system GL libraries that a headless test or
        # lint environment may lack, and importing this module must not require them.
        from PySide6.QtGui import QImage

        image = QImage(filename)
        if image.isNull():
            raise RuntimeError(f"Failed to load image: {filename}")
        # PySide6's stub types `format` as bytes, but the runtime requires str.
        if not image.save(output, "PNG"):  # pyright: ignore[reportCallIssue, reportArgumentType]
            raise RuntimeError(f"Failed to write PNG: {output}")
