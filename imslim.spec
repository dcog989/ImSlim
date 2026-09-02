# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for ImSlim (Linux).

Builds a self-contained onedir bundle carrying the per-platform compression
tools (src/imslim/bin/<platform>/) alongside the Python + PySide6 runtime.
The onedir output is packaged into an AppImage by scripts/package_linux.sh.
"""

from pathlib import Path

project_root = Path(SPECPATH)

PLATFORM_DIR = "linux-x86_64"

BIN_DIR = project_root / "src" / "imslim" / "bin" / PLATFORM_DIR
if not BIN_DIR.is_dir():
    raise SystemExit(
        f"No bundled tools for {PLATFORM_DIR} at {BIN_DIR}. "
        "Run scripts/build_tools.sh first."
    )

datas = [
    (str(BIN_DIR), "imslim/bin"),
    (str(project_root / "src" / "imslim" / "assets"), "imslim/assets"),
]

a = Analysis(
    [str(project_root / "entrypoint.py")],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ImSlim",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="ImSlim",
)