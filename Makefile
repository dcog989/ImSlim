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
	mkdir -p ~/.local/share/applications ~/.local/share/icons/hicolor/scalable/apps
	install -Dm644 assets/imslim.desktop ~/.local/share/applications/imslim.desktop
	install -Dm644 src/imslim/assets/imslim.svg ~/.local/share/icons/hicolor/scalable/apps/imslim.svg
	kbuildsycoca6

package-linux:
	./scripts/package_linux.sh

run:
	uv run imslim

tools:
	./scripts/build_tools.sh

upgrade:
	uv lock --upgrade
