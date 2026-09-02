#!/usr/bin/env bash
# Package the Linux (x86_64) ImSlim AppImage.
#
# Prerequisites:
#   - scripts/build_tools.sh has produced src/imslim/bin/linux-x86_64/
#   - pyinstaller and appimagetool are available (appimagetool is fetched
#     into .build/ if missing)
#
# Output: dist/ImSlim-<version>-linux-x86_64.AppImage
#
# Run from the repository root:
#   ./scripts/package_linux.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$("$ROOT/.venv/bin/python" -c 'import sys; sys.path.insert(0,"src"); print(__import__("imslim").__version__)')"
ARCH="x86_64"
OUT_DIR="$ROOT/dist"
APPIMAGE_NAME="ImSlim-$VERSION-linux-$ARCH.AppImage"
APP_DIR="$OUT_DIR/ImSlim.AppDir"

mkdir -p "$OUT_DIR"
rm -rf "$APP_DIR"

log() { printf '\033[1;36m[package]\033[0m %s\n' "$*"; }

# Raster icon for the AppDir and desktop entry. Force the offscreen Qt
# platform: icon rendering must not require a display (e.g. in CI).
QT_QPA_PLATFORM=offscreen "$ROOT/.venv/bin/python" "$ROOT/scripts/make_icons.py"

# Build the onedir bundle (payload for the AppImage).
IMSLIM_ONE_FILE=0 "$ROOT/.venv/bin/pyinstaller" \
    --noconfirm \
    --clean \
    --distpath "$OUT_DIR/pyinstaller" \
    --workpath "$OUT_DIR/build" \
    "$ROOT/imslim.spec"

# Lay out a standard AppDir around the PyInstaller bundle.
mkdir -p "$APP_DIR/usr/bin"
cp -a "$OUT_DIR/pyinstaller/ImSlim/." "$APP_DIR/usr/bin/"

mkdir -p "$APP_DIR/usr/share/applications"
cp "$ROOT/assets/imslim.desktop" "$APP_DIR/usr/share/applications/imslim.desktop"
# appimagetool requires the .desktop entry at the AppDir root.
cp "$ROOT/assets/imslim.desktop" "$APP_DIR/imslim.desktop"

for size in 16 32 64 128 256 512; do
    dir="$APP_DIR/usr/share/icons/hicolor/${size}x${size}/apps"
    mkdir -p "$dir"
    QT_QPA_PLATFORM=offscreen "$ROOT/.venv/bin/python" - "$ROOT/build/icon/imslim.png" "$dir/imslim.png" "$size" <<'PY'
import sys
from PySide6.QtGui import QImage
src, dst, size = sys.argv[1], sys.argv[2], int(sys.argv[3])
img = QImage(src)
img.scaled(size, size).save(dst)
PY
done
ln -sf "usr/share/icons/hicolor/512x512/apps/imslim.png" "$APP_DIR/imslim.png"

cat > "$APP_DIR/AppRun" <<'EOF'
#!/bin/sh
SELF="$(readlink -f "$0")"
HERE="${SELF%/*}"
exec "$HERE/usr/bin/ImSlim" "$@"
EOF
chmod +x "$APP_DIR/AppRun"

# appimagetool: fetch a pinned release build into .build/ if not already
# present, verifying its sha256 so a corrupt or tampered download fails
# loudly instead of producing a broken AppImage.
APPIMAGETOOL_VERSION="1.9.1"
APPIMAGETOOL_SHA256="ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0"
APPIMAGETOOL="$ROOT/.build/appimagetool"
verify_appimagetool() {
    echo "$APPIMAGETOOL_SHA256  $APPIMAGETOOL" | sha256sum -c --quiet
}
if [[ ! -x "$APPIMAGETOOL" ]] || ! verify_appimagetool 2>/dev/null; then
    log "downloading appimagetool $APPIMAGETOOL_VERSION"
    curl -fsSLo "$APPIMAGETOOL" \
        "https://github.com/AppImage/appimagetool/releases/download/$APPIMAGETOOL_VERSION/appimagetool-x86_64.AppImage"
    chmod +x "$APPIMAGETOOL"
fi
verify_appimagetool || { log "appimagetool sha256 mismatch"; exit 1; }

"$APPIMAGETOOL" --appimage-extract-and-run "$APP_DIR" "$OUT_DIR/$APPIMAGE_NAME"
rm -rf "$APP_DIR"
printf 'Wrote %s\n' "$OUT_DIR/$APPIMAGE_NAME"
