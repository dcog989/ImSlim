# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for ImSlim (Linux).

Builds a self-contained onedir bundle carrying the per-platform compression
tools (src/imslim/bin/<platform>/) alongside the Python + PySide6 runtime.
The onedir output is packaged into an AppImage by scripts/package_linux.sh.
"""

from pathlib import Path

from PyInstaller.building.datastruct import TOC

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
    (str(project_root / "src" / "imslim" / "locale"), "imslim/locale"),
]

# Qt modules this app never imports. The PySide6 hooks only collect what is
# imported, so these guard against a stray import dragging QML, WebEngine or the
# multimedia stack into the bundle.
excludes = [
    "tkinter",
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DRender",
    "PySide6.QtBluetooth",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtDesigner",
    "PySide6.QtHelp",
    "PySide6.QtLocation",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtNfc",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtPositioning",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.QtQuickWidgets",
    "PySide6.QtRemoteObjects",
    "PySide6.QtScxml",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtSql",
    "PySide6.QtStateMachine",
    "PySide6.QtTest",
    "PySide6.QtUiTools",
    "PySide6.QtWebChannel",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebSockets",
]

# The Qt hooks collect every plugin belonging to an imported module, and a
# plugin drags in its whole dependency closure. Two of them are dead weight
# here, as verified with a dependency walk over the built bundle (each name
# below is reachable *only* through the plugin):
#   platformthemes/libqgtk3.so            -> GTK3 stack + the host ICU 78 (~60 MB)
#     The app selects the xdg-desktop-portal theme at startup (main.py), so the
#     GTK theme plugin is never the one that loads.
#   platforminputcontexts/libqtvirtualkeyboardplugin.so -> Qt Quick/QML (~20 MB)
#     Raises the on-screen keyboard for touch input; this is a desktop app.
_DROPPED_PREFIXES = (
    # virtual keyboard -> Qt Quick/QML
    "libqtvirtualkeyboardplugin.so",
    "libQt6VirtualKeyboard",
    "libQt6Quick",
    "libQt6Qml",
    # GTK3 platform theme -> GTK, its text stack, and the host's ICU 78
    "libqgtk3.so",
    "libgtk-3.so.0",
    "libgdk-3.so.0",
    "libgdk_pixbuf-2.0.so.0",
    "libglycin-2.so.0",
    "libatk-1.0.so.0",
    "libatk-bridge-2.0.so.0",
    "libatspi.so.0",
    "libcairo.so.2",
    "libcairo-gobject.so.2",
    "libpixman-1.so.0",
    "libpango-1.0.so.0",
    "libpangocairo-1.0.so.0",
    "libpangoft2-1.0.so.0",
    "libharfbuzz.so.0",
    "libfribidi.so.0",
    "libgraphite2.so.3",
    "libthai.so.0",
    "libdatrie.so.1",
    "libepoxy.so.0",
    "libsqlite3.so.0",
    "libxml2.so.16",
    "libjson-glib-1.0.so.0",
    "libcloudproviders.so.0",
    "libtinysparql-3.0.so.0",
    "libseccomp.so.2",
    "libicuuc.so.78",
    "libicui18n.so.78",
    "libicudata.so.78",
    "libXcomposite.so.1",
    "libXcursor.so.1",
    "libXdamage.so.1",
    "libXext.so.6",
    "libXfixes.so.3",
    "libXi.so.6",
    "libXinerama.so.1",
    "libXrandr.so.2",
    "libXrender.so.1",
)


def is_dropped(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return name.startswith(_DROPPED_PREFIXES)


a = Analysis(
    [str(project_root / "entrypoint.py")],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    # Strip asserts and docstrings from the bundled bytecode.
    optimize=1,
)

# Drop the excluded plugins and their now-unreferenced libraries. The same
# filter runs over datas, which is what carries the PySide6/Qt/lib copies and
# the compatibility symlinks pointing at them.
a.binaries = TOC([entry for entry in a.binaries if not is_dropped(entry[0])])
a.datas = TOC([entry for entry in a.datas if not is_dropped(entry[0])])

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ImSlim",
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=True,
    upx=False,
    name="ImSlim",
)
