#!/usr/bin/env python3
"""Render the ImSlim SVG logo into raster PNGs for the Linux AppImage.

Output (under build/icon/):
  imslim-<size>.png - 16, 32, 64, 128, 256 and 512 square PNGs

Run from the repository root:
  python3 scripts/make_icons.py
"""

import sys
from pathlib import Path

from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parent.parent
SVG_PATH = ROOT / "src" / "imslim" / "assets" / "imslim.svg"
OUT_DIR = ROOT / "build" / "icon"
SIZES = (16, 32, 64, 128, 256, 512)


def render_png(size: int = 512) -> QImage:
    renderer = QSvgRenderer(str(SVG_PATH))
    image = QImage(size, size, QImage.Format_ARGB32)  # pyright: ignore[reportAttributeAccessIssue]
    image.fill(0x00000000)
    painter = QPainter(image)
    _res = renderer.render(painter)
    _res = painter.end()
    return image


def write_png(image: QImage, path: Path) -> None:
    if not image.save(str(path), "PNG"):  # pyright: ignore[reportCallIssue, reportArgumentType]
        raise RuntimeError(f"Failed to write {path}")


def main() -> int:
    if not SVG_PATH.is_file():
        print(f"SVG not found: {SVG_PATH}", file=sys.stderr)
        return 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for size in SIZES:
        write_png(render_png(size), OUT_DIR / f"imslim-{size}.png")
    print(f"icons written to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
