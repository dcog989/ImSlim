init:
	uv sync

lint:
	uv run ruff format

format:
	uv run ruff format .

analyze:
	uv run ruff check

fix:
	uv run ruff check --fix

types:
	uv run ruff check

update_deps:
	uv lock --upgrade
