# Agent Directives

## Project Specifics

- Name: ImSlim
- Description: Desktop app to compress images in PNG, JPEG, GIF, WebP, AVIF, JXL and SVG formats, in lossless or lossy mode. BMP and TIFF sources are re-encoded to WebP. Built on the external tools pngquant/oxipng, cjpegli/djpegli, mozjpeg jpegtran, cwebp, gifsicle, cjxl/djxl, avifdec/avifenc and svgo. Tools are bundled per-platform in `src/imslim/bin/` (built by `scripts/build_tools.sh`); `src/imslim/binary_resolver.py` resolves them (frozen-binary aware for PyInstaller).
- Tech: Python (>=3.14), PySide6 (Qt6). Setup and deps managed via `uv`. Lint/format via `ruff`; type-check via `basedpyright`.

### Key Files

- `src/imslim/main.py` — entry point / application bootstrap, CLI args (`--help`/`--version`) and single-instance server
- `src/imslim/window.py` — main window UI, mode toggle, home view, drag & drop
- `src/imslim/results_view.py` — `ResultsView`: results page, chunked result rows, busy overlay
- `src/imslim/result_item.py` / `result_item_manager.py` / `result_item_row.py` — per-file state, intake/analysis and the results row widget (thumbnails)
- `src/imslim/clipboard_intake.py` — `ClipboardIntake`: paste-to-paths (URLs or saved image) and temp-dir cleanup
- `src/imslim/composition.py` — `AppContext` / `build_app_context()`: assembles settings, compression manager and batch flow
- `src/imslim/batch_flow.py` / `batch_options.py` / `batch_summary.py` — one analyze→compress→summary batch, its immutable options snapshot and its counters
- `src/imslim/workers.py` — pooled background tasks (analyze, version probe)
- `src/imslim/settings/` — settings dialog: `dialog.py` hosts the tabbed `SettingsDialog`, with one widget per tab (`general_tab.py`, `formats_tab.py`, `about_tab.py`), shared signal/handler helpers in `tab.py` and shared styling in `style.py`
- `src/imslim/settings_manager.py` — persistent settings/state store (`log_file_path()` included)
- `src/imslim/commands.py` — `Command` (`argv` or in-process `action`, plus `temp_files`) and `tokens`
- `src/imslim/compressor.py` — `Compressor` ABC: subclasses produce pure command lists in `build_command()`
- `src/imslim/command_runner.py` — `CommandRunner` (killable subprocess execution) and `CompressionContext` (batch cancellation)
- `src/imslim/pipeline.py` — `CompressionPipeline`: runs a compressor's commands, finalizes output, cleans up and reports errors
- `src/imslim/conversion.py` — `decode_commands()`: bundled decoder or Qt fallback that turns any source into PNG
- `src/imslim/output_writer.py` — `OutputWriter`: moves the temp result into place (skip-if-larger, backups, attributes)
- `src/imslim/binary_resolver.py` — resolves bundled/PATH compression tools (`KNOWN_TOOLS`)
- `src/imslim/image_convert.py` — Qt-based decode-to-PNG helper (BMP/TIFF → cwebp input)
- `src/imslim/jpeg_metadata.py` — `transfer_metadata()`: carries EXIF/XMP/JUMBF from the source onto the JPEG output (or drops it)
- `src/imslim/formats.py` — `FORMAT_SPECS` and derived tables (`DECODER_TOOLS`, MIME/extension maps, file-dialog filter) plus `ALLOWED_MIME_TYPES`: single source of truth for formats and per-format knobs
- `src/imslim/compressors/` — per-format compressors (PNG, JPEG, WebP, AVIF, jxl, SVG); `ALL_COMPRESSORS` in `__init__.py` is the registry
- `src/imslim/compression_manager.py` — thread-pool orchestration of compressors
- `src/imslim/_i18n.py` + `src/imslim/locale/` — `_()` gettext lookup and translation catalogs
- `src/imslim/system_info.py` / `_logging.py` / `theme.py` — about-tab info, rotating log setup and palette/accent helpers
- `src/imslim/assets/imslim.svg` — main window logo
- Tests: `tests/` (pytest unit tests for compressor command building, batch summary and pipeline branches, format/percent math, JPEG encode + metadata, output writer, result-item manager and system info)

### Commands

- Install: `uv sync`
- Dev: `uv run imslim` (or `python -m imslim`; `make run`)
- Build bundled tools: `./scripts/build_tools.sh` (populates `src/imslim/bin/linux-x86_64/`); run after a fresh clone so the app has its backends. Pinned in `tools.lock`; `--update` refreshes pins, `--check` reports stale ones
- Test: `uv run pytest`
- Type-check: `uv run basedpyright src/imslim`
- Lint: `uv run ruff check` (`make fix` auto-fixes and formats)
- Format: `uv run ruff format .`
- Full gate (what CI runs): `make check` → `ruff check`, `ruff format --check`, `basedpyright src/imslim`, `pytest`
- Translations: `./scripts/translations.sh all` (extract + update + compile; wraps `_()` strings and needs GNU gettext) or `make translations`
- Build wheel/sdist: `uv build` / `uvx --from build python -m build` (build backend: uv_build; `make build` first runs `scripts/check_bundled_tools.py` and fails when the gitignored bundled tools are missing, since the wheel carries them)
- Package standalone binary: `./scripts/package_linux.sh` → `dist/ImSlim-*-linux-x86_64.AppImage` (PyInstaller via `imslim.spec`; icons via `scripts/make_icons.py`)
- Release: `cog bump --auto` (Cocogitto, external Rust binary — `cargo install cocogitto` / `pacman -S cocogitto` / `brew install cocogitto`; config in `cog.toml`, changelog template `changelog.tpl` filters to feat/fix/perf/refactor). Bumps version, syncs `pyproject.toml` + `src/imslim/__init__.py`, writes `CHANGELOG.md`, and tags. Pushing a version tag (e.g. `v0.5.1`, with `v` prefix via `tag_prefix` in `cog.toml`) runs `.github/workflows/release.yml`, which builds the Linux AppImage and wheel and attaches them to the GitHub release.

### File System Access

- Allowed: <project root> and all contained directories + files; `/tmp/*`
- Read-Only: `.env*`, `.git/`
- Disallowed: everything not listed in 'Allowed' unless user grants permission.
- Require confirmation: adding/removing dependencies, any operation outside project root
- Do not delete files or make destructive changes without confirmation.

### Common Patterns

- Add a setting: Add key + accessors in `src/imslim/settings_manager.py`, expose it in the relevant tab under `src/imslim/settings/`, and consume it via `BatchOptions` / the relevant compressor under `src/imslim/compressors/`.
- Add a format: Create a compressor subclass in `src/imslim/compressors/`, add it to `ALL_COMPRESSORS` in `src/imslim/compressors/__init__.py`, and add a `FormatSpec` to `FORMAT_SPECS` in `src/imslim/formats.py` (MIME + extensions, decoder, knobs). Every lookup table, the file-dialog filter, the settings defaults and the format selector are derived from it.
- Add a decoder: map the source MIME to a bundled tool in `DECODER_TOOLS` (`src/imslim/formats.py`), add the tool to `KNOWN_TOOLS` in `src/imslim/binary_resolver.py` and build it in `scripts/build_tools.sh` + `tools.lock`. Without a decoder, `decode_commands()` falls back to Qt decoding via `image_convert.to_png()`.
- Translate a string: wrap it in `_()` from `imslim._i18n`, then run `./scripts/translations.sh all`. Add a language with `./scripts/translations.sh init <lang>`, translate its `.po`, and rerun.
- Compressor pipeline: override `build_command(result_item, options, input_path)` to return a pure `list[Command]` (a `NamedTuple` of `argv: list[str] | None`, `action: Callable[[], None] | None`, `stdout_path: str | None`, `ignore_errors: bool`, `temp_files: tuple[str, ...]`, `adapt: Callable[[list[str]], list[str]] | None`, defined in `src/imslim/commands.py`). Declare every temporary file a command creates in `temp_files` so cleanup is derived; implement `get_file_type()` as needed. Pre-decode with `decode_commands()` rather than doing work in the builder.
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

### Author Environment

- CachyOS, KDE Plasma 6, Wayland, Btrfs.
- fish shell, Ghostty terminal, Fresh TUI editor, yay package manager, bun npm manager, Firefox, and Zed code editor.

### Testing

- Do not create test files for trivial changes, or for behavior that is not reliably unit-testable in the test environment (e.g. UI layout/click mapping). Prefer no new files; only add a test when the logic is genuinely testable and worth guarding.

### Definition of Done

- Logic fully implemented.
- Existing docs updated if public interfaces changed.
- Run `make check` (ruff check, ruff format check, basedpyright, pytest) before calling the work done.

### Commit Messages

- On completion of an update or fix, print a conventional commit message in a fenced code block.
- Add a body only when the "why" isn't obvious.
- Do not wrap lines. One physical line per paragraph however long it gets. Never hard-wrap the subject or the body.

### Communication Style

- Terse: short declarative sentences, one idea per line.
- Fixes and instructions: numbered steps, one action each, exact command/path/code. No prose paragraphs or recap.
- Questions and explanations: direct prose, only the reasoning needed.
- Cut words, never facts — keep every command, flag, path, default and caveat.
- No preamble, restating, hedging, disclaimers, meta-commentary, emotional framing, or closing offers; end when done unless a real decision is needed.
- Ask when requirements are ambiguous; state risks and edge cases.
- End answers to questions with a `TL;DR:` line: one sentence, the whole point. Skip it for acknowledgements, status updates, and completed work.
