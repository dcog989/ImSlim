data_home := env("XDG_DATA_HOME", home_dir() / ".local" / "share")
groups := env("GROUPS", "")

# Verify the repo: the same gate CI runs.
default: check

# Ruff lint, format check, basedpyright and pytest.
check: lint test

# Ruff lint, format check and types.
lint:
    uv run ruff check
    uv run ruff format --check
    uv run basedpyright src/imslim

# Test suite.
test:
    uv run pytest

# Auto-fix lint issues and rewrite formatting.
fix:
    uv run ruff check --fix
    uv run ruff format .

# Rewrite formatting only.
format:
    uv run ruff format .

# Wheel and sdist into dist/.
build: require-tools
    uv build

# Fail the build when the gitignored bundled tools are missing.
require-tools:
    python3 scripts/check_bundled_tools.py

# Build the tools.lock-pinned backends into src/imslim/bin/.
tools:
    ./scripts/build_tools.sh

# Resolve the latest upstream tools, rewrite tools.lock and rebuild (`GROUPS=libjxl` limits it).
update-tools:
    ./scripts/build_tools.sh --update {{groups}}

# Install as a uv tool, with desktop entries and icon.
install: require-tools
    #!/usr/bin/env bash
    set -euo pipefail
    uv tool install . --force
    data_home={{data_home}}
    bin="$(command -v imslim 2>/dev/null || echo "$HOME/.local/bin/imslim")"
    mkdir -p "$data_home/applications" "$data_home/icons/hicolor/scalable/apps"
    sed "s|^Exec=.*|Exec=\"$bin\" %F|" assets/imslim.desktop | install -Dm644 /dev/stdin "$data_home/applications/imslim.desktop"
    sed "s|^Exec=.*|Exec=\"$bin\" --now %F|" assets/imslim-now.desktop | install -Dm644 /dev/stdin "$data_home/applications/imslim-now.desktop"
    install -Dm644 src/imslim/assets/imslim.svg "$data_home/icons/hicolor/scalable/apps/imslim.svg"
    kbuildsycoca6 2>/dev/null || kbuildsycoca5 2>/dev/null || true
    update-desktop-database "$data_home/applications" 2>/dev/null || true

# Remove the uv tool, desktop entries and icon.
uninstall:
    #!/usr/bin/env bash
    set -uo pipefail
    data_home={{data_home}}
    uv tool uninstall imslim || true
    rm -f "$data_home/applications/imslim.desktop" "$data_home/applications/imslim-now.desktop"
    rm -f "$data_home/icons/hicolor/scalable/apps/imslim.svg"
    rm -f "$HOME/Applications/ImSlim.AppImage"
    kbuildsycoca6 2>/dev/null || kbuildsycoca5 2>/dev/null || true
    update-desktop-database "$data_home/applications" 2>/dev/null || true

# AppImage via scripts/package_linux.sh.
package-linux:
    ./scripts/package_linux.sh

# Run the app.
run:
    uv run imslim

# Extract, update and compile the translations.
translations:
    ./scripts/translations.sh all

# Sync the uv environment.
init:
    uv sync

# Bump the lockfile to the latest allowed versions.
update:
    uv lock --upgrade

# Remove build artifacts.
clean:
    rm -rf .venv dist build .ruff_cache .pytest_cache
    find . -name __pycache__ -type d -exec rm -rf {} +

# Also remove the bundled tools, which take minutes to rebuild.
distclean: clean
    rm -rf .build src/imslim/bin
