#!/usr/bin/env bash
# Install the ImSlim AppImage into the user's desktop environment.
#
# Copies the AppImage to ~/Applications, installs a desktop entry + icon so the
# app appears in the application menu, registers it as the handler for the
# supported image types, and refreshes the menu cache. Run once after
# downloading an AppImage from a release; launch ImSlim like any other app
# afterwards.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

APPIMAGE="${1:-}"
if [[ -z "$APPIMAGE" ]]; then
    APPIMAGE="$(ls -1 "$ROOT"/dist/ImSlim-*-linux-x86_64.AppImage 2>/dev/null | head -n1 || true)"
fi
if [[ -z "$APPIMAGE" || ! -f "$APPIMAGE" ]]; then
    echo "No AppImage found. Pass its path, e.g.: bash $0 ImSlim-1.0.0-linux-x86_64.AppImage" >&2
    echo "or run ./scripts/package_linux.sh to build one into dist/." >&2
    exit 1
fi

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
APPS_DIR="$HOME/Applications"
ICON_DIR="$DATA_HOME/icons/hicolor/scalable/apps"
DESKTOP_DIR="$DATA_HOME/applications"
TARGET="$APPS_DIR/ImSlim.AppImage"

mkdir -p "$APPS_DIR" "$ICON_DIR" "$DESKTOP_DIR"
install -Dm755 "$APPIMAGE" "$TARGET"

# Prefer the repo's desktop entry/icon so they stay in sync; fall back to the
# embedded copies so the script also works standalone (e.g. as a release asset).
DESKTOP_SOURCE="$ROOT/assets/imslim.desktop"
if [[ -f "$DESKTOP_SOURCE" ]]; then
    sed "s|^Exec=.*|Exec=\"$TARGET\" %F|" "$DESKTOP_SOURCE" > "$DESKTOP_DIR/imslim.desktop"
else
    cat > "$DESKTOP_DIR/imslim.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=ImSlim
GenericName=Image Compressor
Comment=Compress PNG, JPEG, GIF, WebP, AVIF, JXL and SVG images
Exec="$TARGET" %F
Icon=imslim
Terminal=false
Categories=Graphics;Utility;
Keywords=image;compress;optimize;png;jpeg;webp;avif;jxl;svg;
MimeType=image/png;image/jpeg;image/gif;image/webp;image/avif;image/jxl;image/svg+xml;image/bmp;image/tiff;
EOF
fi

ICON_SOURCE="$ROOT/src/imslim/assets/imslim.svg"
if [[ -f "$ICON_SOURCE" ]]; then
    install -Dm644 "$ICON_SOURCE" "$ICON_DIR/imslim.svg"
else
    printf '%s' \
        "PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA1MDAgNTAwIiB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIj4KICA8dGl0bGU+SW1TbGltIExvZ288L3RpdGxlPgogIDxnIHRyYW5zZm9ybT0idHJhbnNsYXRlKDI1MCAyNTApIHNjYWxlKDEuNDM3NSkgdHJhbnNsYXRlKC0yNTAgLTI1MCkiIGZpbGw9IiMwMGJjODUiPgogICAgPCEtLSBUb3AgSG9yaXpvbnRhbCBCYXIgLS0+CiAgICA8cmVjdCB4PSIxNTAiIHk9IjkwIiB3aWR0aD0iMjAwIiBoZWlnaHQ9IjMyIiByeD0iOCIgLz4KCiAgICA8IS0tIFRhcGVyZWQgQ2VudGVyIFZlcnRpY2FsIEJhciAtLT4KICAgIDwhLS0gVG9wIHdpZHRoOiAxMDBweCAoMjAwIHRvIDMwMCksIE1pZGRsZSB3aWR0aDogMjBweCAoMjQwIHRvIDI2MCksIEJvdHRvbSB3aWR0aDogMTAwcHggKDIwMCB0byAzMDApIC0tPgogICAgPHBhdGgKICAgICAgZD0iTSAyMDAsMTM4CiAgICAgICAgICAgICBIIDMwMAogICAgICAgICAgICAgUSAyMjAsMjUwIDMwMCwzNjIKICAgICAgICAgICAgIEggMjAwCiAgICAgICAgICAgICBRIDI4MCwyNTAgMjAwLDEzOCBaIgogICAgLz4KCiAgICA8IS0tIEJvdHRvbSBIb3Jpem9udGFsIEJhciAtLT4KICAgIDxyZWN0IHg9IjE1MCIgeT0iMzc4IiB3aWR0aD0iMjAwIiBoZWlnaHQ9IjMyIiByeD0iOCIgLz4KICA8L2c+Cjwvc3ZnPgo=" \
        | base64 --decode > "$ICON_DIR/imslim.svg"
fi

if command -v kbuildsycoca6 >/dev/null 2>&1; then
    kbuildsycoca6 >/dev/null 2>&1 || true
elif command -v kbuildsycoca5 >/dev/null 2>&1; then
    kbuildsycoca5 >/dev/null 2>&1 || true
fi
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
fi

echo "Installed ImSlim to $TARGET."
echo "ImSlim is now in your application menu and opens the supported image types."