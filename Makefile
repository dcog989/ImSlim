build:
	uv build

bump:
	cog bump --auto

check:
	uv run ruff check
	uv run basedpyright src/imslim

clean:
	rm -rf .venv dist src/*.egg-info && find . -name __pycache__ -type d -exec rm -rf {} +

format:
	uv run ruff format .

fix:
	uv run ruff check --fix

init:
	uv sync

install:
	uv tool install . --force
	mkdir -p $(HOME)/.local/share/applications $(HOME)/.local/share/icons/hicolor/scalable/apps
	@BIN=$$(command -v imslim 2>/dev/null || echo $(HOME)/.local/bin/imslim); \
	sed "s|^Exec=.*|Exec=$$BIN %F|" assets/imslim.desktop | \
		install -Dm644 /dev/stdin $(HOME)/.local/share/applications/imslim.desktop
	install -Dm644 src/imslim/assets/imslim.svg $(HOME)/.local/share/icons/hicolor/scalable/apps/imslim.svg
	@if command -v kbuildsycoca6 >/dev/null 2>&1; then kbuildsycoca6; \
	elif command -v kbuildsycoca5 >/dev/null 2>&1; then kbuildsycoca5; fi
	@if command -v update-desktop-database >/dev/null 2>&1; then \
		update-desktop-database $(HOME)/.local/share/applications; fi

package-linux:
	./scripts/package_linux.sh

run:
	uv run imslim

tools:
	./scripts/build_tools.sh

upgrade:
	uv lock --upgrade
