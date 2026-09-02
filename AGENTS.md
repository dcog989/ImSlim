# Agent Directives

## Project Specifics

- Name: ImSlim
- Description: Desktop app to compress images in PNG, JPEG, GIF, WebP, AVIF, JXL and SVG formats, in lossless or lossy mode. BMP and TIFF sources are re-encoded to WebP. Built on the external tools pngquant/oxipng, cjpegli/djpegli, mozjpeg jpegtran, cwebp, gifsicle, cjxl/djxl, avifdec/avifenc and svgo. Tools are bundled per-platform in `src/imslim/bin/` (built by `scripts/build_tools.sh`); `src/imslim/binary_resolver.py` resolves them (frozen-binary aware for PyInstaller).
- Tech: Python (>=3.14), PySide6 (Qt6). Setup and deps managed via `uv`. Lint/format via `ruff`; type-check via `basedpyright`.

### Key Files

- `src/imslim/main.py` — entry point / application bootstrap
- `src/imslim/window.py` — main window UI, mode toggle, home/results views
- `src/imslim/settings.py` — settings dialog
- `src/imslim/settings_manager.py` — persistent settings/state store
- `src/imslim/compressor.py` — base compressor + run logic
- `src/imslim/binary_resolver.py` — resolves bundled/PATH compression tools
- `src/imslim/image_convert.py` — Qt-based decode-to-PNG helper (BMP/TIFF → cwebp input)
- `src/imslim/compressors/` — per-format compressors (png, jpeg, webp, avif, jxl, svg)
- `src/imslim/compression_manager.py` — thread-pool orchestration of compressors
- `src/imslim/assets/imslim.svg` — main window logo
- Tests: none yet (no test suite currently present)

### Commands

- Install: `uv sync`
- Dev: `uv run imslim` (or `python -m imslim`)
- Build bundled tools: `./scripts/build_tools.sh` (populates `src/imslim/bin/linux-x86_64/`); run after a fresh clone so the app has its backends
- Test: no test suite configured
- Type-check: `uv run basedpyright src/imslim`
- Lint: `uv run ruff check`
- Format: `uv run ruff format .`
- Build wheel/sdist: `uv build` / `uvx --from build python -m build` (build backend: uv_build)
- Package standalone binary: `./scripts/package_linux.sh` → `dist/ImSlim-*-linux-x86_64.AppImage` (PyInstaller via `imslim.spec`; icons via `scripts/make_icons.py`)
- Release: `cog bump --auto` (Cocogitto, external Rust binary — `cargo install cocogitto` / `pacman -S cocogitto` / `brew install cocogitto`; config in `cog.toml`, changelog template `changelog.tpl` filters to feat/fix/perf/refactor). Bumps version, syncs `pyproject.toml` + `src/imslim/__init__.py`, writes `CHANGELOG.md`, and tags. Pushing a version tag (e.g. `v0.5.1`, with `v` prefix via `tag_prefix` in `cog.toml`) runs `.github/workflows/release.yml`, which builds the Linux AppImage and wheel and attaches them to the GitHub release.

### File System Access

- Allowed: <project root> and all contained directories + files; `/tmp/*`
- Read-Only: `.env*`, `.git/`
- Disallowed: everything not listed in 'Allowed' unless user grants permission.
- Require confirmation: adding/removing dependencies, any operation outside project root
- Do not delete files or make destructive changes without confirmation.

### Common Patterns

- Add a setting: Add key + accessors in `src/imslim/settings_manager.py`, expose it in `src/imslim/settings.py`, and consume it in the relevant compressor under `src/imslim/compressors/`.
- Add a format: Create a compressor subclass in `src/imslim/compressors/`, register it in `src/imslim/window.py` (`manager.register_compressor(...)`) and `compression_manager.py` (`mime_type_to_compressor_type`), and add its extensions to `_IMAGE_EXTENSIONS`/`image_filter()` in `src/imslim/tools.py`.
- Compressor pipeline: override `build_command()` to return `list[tuple[list[str], str | None]]` (argv, optional stdout path); implement `get_intermediate_files()` and `get_file_type()` as needed.
- State access: Read/write mode and settings through `SettingsManager` (exposed on the window as `self.settings`).

---

## General Guidelines

### Code Changes

- For non-trivial work, propose an approach and confirm before implementing.
- Keep modifications minimal and scoped; prefer incremental improvements over rewrites. Ask before architectural changes.
- Use explicit types and named constants (no magic numbers).
- Return explicit error types; do not suppress exceptions.
- Follow standard repository linting and formatting configs.
- Decompose files over 400 lines if they mix concerns.
- Use clear naming over comments; reserve comments for complex workarounds or non-obvious issues — why, not what.
- Never run git mutations (commit, push, reset, rebase, amend) unless explicitly instructed.
- Do not create documentation files unless explicitly requested.

### Verification

- Do not run test, lint, format, or type-check commands; the user builds, tests, and lints manually.
- Run them only when the user explicitly asks.

### Author Environment

- CachyOS, KDE Plasma 6, Wayland, Btrfs.
- fish shell, Ghostty terminal, Fresh TUI editor, yay package manager, bun npm manager, Firefox, and Zed code editor.

### Testing

- Do not create test files for trivial changes, or for behavior that is not reliably unit-testable in the test environment (e.g. UI layout/click mapping). Prefer no new files; only add a test when the logic is genuinely testable and worth guarding.

### Definition of Done

- Logic fully implemented.
- Existing docs updated if public interfaces changed.
- When required by the `Verification` rules, run the corresponding `Workflow` command.
- On completion of an update or fix, print a concise conventional commit message in a fenced code block.

### Communication Style

- Provide concise, actionable responses.
- Ask clarifying questions when requirements are ambiguous.
- Flag potential risks or edge cases proactively.
- Do not pretend to understand how the user feels.
- Never editorialise your answer. No "to be honest", "honestly", hedging, disclaimers, or meta-commentary — just answer.
