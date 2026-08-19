# Agent Directives

## Project

- Name: ImSlim
- Description: Desktop app to compress images in PNG, JPEG, GIF, WebP, AVIF and SVG formats, in lossless or lossy mode. Built on the external tools pngquant/oxipng, cjpegli/djpegli, mozjpeg jpegtran, cwebp, gifsicle, avifdec/avifenc and svgo.
- Tech: Python (>=3.13), PySide6 (Qt6). Setup and deps managed via `uv`. Lint/format via `ruff`.

## Key Files

- `src/imslim/main.py` — entry point / application bootstrap
- `src/imslim/window.py` — main window UI, mode toggle, home/results views
- `src/imslim/preferences.py` — preferences dialog
- `src/imslim/settings_manager.py` — persistent settings/state store
- `src/imslim/compressor.py` — base compressor + run logic
- `src/imslim/compressors/` — per-format compressors (png, jpeg, webp, avif, svg)
- `src/imslim/compression_manager.py` — thread-pool orchestration of compressors
- `assets/imslim.svg` — main window logo
- Tests: none yet (no test suite currently present)

## Workflow

### Commands

- Install: `uv sync`
- Dev: `uv run imslim` (or `python -m imslim`)
- Test: no test suite configured
- Lint: `uv run ruff check`
- Format: `uv run ruff format .`
- Build: `uv build` / `uvx --from build python -m build` (build backend: uv_build)

### Code Changes

- Keep modifications minimal and scoped; prefer incremental improvements over rewrites. Ask before architectural changes.
- Use explicit types and named constants (no magic numbers).
- Return explicit error types; do not suppress exceptions.
- Follow standard repository linting and formatting configs.
- Decompose files over 400 lines if they mix concerns.
- Self-documenting code via clear naming. Use comments only for complex workarounds or issues that need noting — why, not what.
- Never run git mutations (commit, push, reset, rebase, amend) unless explicitly instructed.
- Do not create documentation files unless explicitly requested.

### Verification

- Do not run test, lint, clippy, biome, format, or type-check commands. The user builds, tests, and lints manually.
- Exception to above: run them for major refactors, or when the user explicitly asks.

## Dev Environment

- CachyOS, KDE Plasma 6, Wayland, Btrfs.
- fish shell, Ghostty terminal, Fresh TUI editor, yay package manager, bun npm manager, Firefox, and Zed code editor.
- All software is up to date as of today.

## File System Access

- Allowed: <project root> and all contained directories + files; `/tmp/*`
- Read-Only: `.env*`, `.git/`
- Disallowed: everything not listed in 'Allowed' unless user grants permission.
- Require confirmation: adding/removing dependencies, any operation outside project root
- Do not delete files or make destructive changes without confirmation.

## Testing

- Do not create test files for trivial changes, or for behavior that is not reliably unit-testable in the test environment (e.g. UI layout/click mapping). Prefer no new files; only add a test when the logic is genuinely testable and worth guarding.

## Common Patterns

- Add a setting: Add key + accessors in `src/imslim/settings_manager.py`, expose it in `src/imslim/preferences.py`, and consume it in the relevant compressor under `src/imslim/compressors/`.
- Add a format: Create a compressor subclass in `src/imslim/compressors/`, register it in `src/imslim/window.py` (`manager.register_compressor(...)`) and `compression_manager.py` (`mime_type_to_compressor_type`).
- Compressor pipeline: override `build_command()` to return `list[tuple[list[str], str | None]]` (argv, optional stdout path); implement `get_intermediate_files()` and `get_file_type()` as needed.
- State access: Read/write mode and preferences through `SettingsManager` (exposed on the window as `self.settings`).

## Communication Style

- Provide concise, actionable responses.
- Ask clarifying questions when requirements are ambiguous.
- Flag potential risks or edge cases proactively.
- Do not pretend to understand how the user feels.

## Definition of Done

- Logic fully implemented.
- Existing docs updated if public interfaces changed.
- On completion of an update or fix, print a concise conventional commit message in a fenced code block.
