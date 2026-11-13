.PHONY: build check clean distclean fix init install package-linux require-tools run tools translations uninstall update-tools upgrade

build: require-tools
	uv build

# The bundled tools are gitignored, so a fresh checkout would otherwise package
# a wheel that cannot compress anything. Fail the build instead.
require-tools:
	python3 scripts/check_bundled_tools.py

check:
	uv run ruff check
	uv run ruff format --check
	uv run basedpyright src/imslim
	uv run pytest

clean:
	rm -rf .venv dist build .ruff_cache .pytest_cache && find . -name __pycache__ -type d -exec rm -rf {} +

# The bundled tools are deliberately kept out of `clean`: rebuilding them takes
# minutes (and re-clones every source into .build).
distclean: clean
	rm -rf .build src/imslim/bin

fix:
	uv run ruff check --fix
	uv run ruff format .

init:
	uv sync

DATA_HOME = $(or $(XDG_DATA_HOME),$(HOME)/.local/share)

install: require-tools
	uv tool install . --force
	mkdir -p $(DATA_HOME)/applications $(DATA_HOME)/icons/hicolor/scalable/apps
	@BIN=$$(command -v imslim 2>/dev/null || echo $(HOME)/.local/bin/imslim); \
	sed "s|^Exec=.*|Exec=\"$$BIN\" %F|" assets/imslim.desktop | \
		install -Dm644 /dev/stdin $(DATA_HOME)/applications/imslim.desktop; \
	sed "s|^Exec=.*|Exec=\"$$BIN\" --now %F|" assets/imslim-now.desktop | \
		install -Dm644 /dev/stdin $(DATA_HOME)/applications/imslim-now.desktop
	install -Dm644 src/imslim/assets/imslim.svg $(DATA_HOME)/icons/hicolor/scalable/apps/imslim.svg
	@if command -v kbuildsycoca6 >/dev/null 2>&1; then kbuildsycoca6; \
	elif command -v kbuildsycoca5 >/dev/null 2>&1; then kbuildsycoca5; fi
	@if command -v update-desktop-database >/dev/null 2>&1; then \
		update-desktop-database $(DATA_HOME)/applications; fi

uninstall:
	uv tool uninstall imslim || true
	rm -f $(DATA_HOME)/applications/imslim.desktop
	rm -f $(DATA_HOME)/applications/imslim-now.desktop
	rm -f $(DATA_HOME)/icons/hicolor/scalable/apps/imslim.svg
	rm -f $(HOME)/Applications/ImSlim.AppImage
	@if command -v kbuildsycoca6 >/dev/null 2>&1; then kbuildsycoca6; \
	elif command -v kbuildsycoca5 >/dev/null 2>&1; then kbuildsycoca5; fi
	@if command -v update-desktop-database >/dev/null 2>&1; then \
		update-desktop-database $(DATA_HOME)/applications 2>/dev/null || true; fi

package-linux:
	./scripts/package_linux.sh

run:
	uv run imslim

# Builds the tools.lock-pinned versions (reproducible; CI caches on the lock).
tools:
	./scripts/build_tools.sh

# Resolves the latest upstream versions, rewrites tools.lock and rebuilds.
# Pass groups to limit the refresh: make update-tools GROUPS=libjxl
update-tools:
	./scripts/build_tools.sh --update $(GROUPS)

translations:
	./scripts/translations.sh all

upgrade:
	uv lock --upgrade
