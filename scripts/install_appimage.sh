#!/usr/bin/env bash
# Install the ImSlim AppImage into the user's desktop environment.
#
# Copies the AppImage to ~/Applications, installs a desktop entry + icon so the
# app appears in the application menu, registers it as the handler for the
# supported image types, and refreshes the menu cache. Run once after
# downloading an AppImage from a release; launch ImSlim like any other app
# afterwards.
#
# The desktop entries and icon come from next to this script (release assets)
# or from the repository, so download them with the script:
#   install_appimage.sh imslim.desktop imslim-now.desktop imslim.svg
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"

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

# Release assets land next to this script; a checkout keeps them under assets/.
find_asset() {
    local name="$1" path
    for path in "$HERE/$name" "$ROOT/assets/$name" "$ROOT/src/imslim/assets/$name"; do
        if [[ -f "$path" ]]; then
            printf '%s' "$path"
            return 0
        fi
    done
    echo "missing $name next to this script; download it from the release" >&2
    return 1
}

DESKTOP_SOURCE="$(find_asset imslim.desktop)"
NOW_DESKTOP_SOURCE="$(find_asset imslim-now.desktop)"
ICON_SOURCE="$(find_asset imslim.svg)"

mkdir -p "$APPS_DIR" "$ICON_DIR" "$DESKTOP_DIR"
install -Dm755 "$APPIMAGE" "$TARGET"

sed "s|^Exec=.*|Exec=\"$TARGET\" %F|" "$DESKTOP_SOURCE" > "$DESKTOP_DIR/imslim.desktop"
sed "s|^Exec=.*|Exec=\"$TARGET\" --now %F|" "$NOW_DESKTOP_SOURCE" \
    > "$DESKTOP_DIR/imslim-now.desktop"
install -Dm644 "$ICON_SOURCE" "$ICON_DIR/imslim.svg"

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
