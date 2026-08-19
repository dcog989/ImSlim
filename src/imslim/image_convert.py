import sys

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


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python -m imslim.image_convert <input> <output.png>", file=sys.stderr)
        return 2
    try:
        to_png(argv[0], argv[1])
    except Exception as err:
        print(str(err), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
