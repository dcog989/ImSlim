# Agent Directives

## Project Specifics

- Name: ImSlim
- Description: Desktop app to compress images in PNG, JPEG, GIF, WebP, AVIF, JXL and SVG formats, in lossless or lossy mode. BMP and TIFF sources are re-encoded to WebP. Built on the external tools pngquant/oxipng, cjpegli/djpegli, mozjpeg jpegtran, cwebp, gifsicle, cjxl/djxl, avifdec/avifenc and svgo. Tools are bundled per-platform in `src/imslim/bin/` (built by `scripts/build_tools.sh`); `src/imslim/binary_resolver.py` resolves them (frozen-binary aware for PyInstaller).
- Tech: Python (>=3.14), PySide6 (Qt6). Setup and deps managed via `uv`. Lint/format via `ruff`; type-check via `basedpyright`.

### Key Files

- `src/imslim/main.py` — entry point / application bootstrap, CLI args (`--help`/`--version`/`--now`), single-instance server and the ImSlimNow path
- `src/imslim/window.py` — main window: three-column splitter (queue / options / comparison), drag & drop, batch lifecycle and the completion dialog
- `src/imslim/queue_view.py` — column 1: persistent file queue, multi-select, view toggle, thumbnail zoom, per-file state
- `src/imslim/options_view.py` — column 2: format, destination, checkboxes, per-format knobs and the Process button
- `src/imslim/compare_view.py` / `preview.py` — column 3: zoomable/pannable original-vs-processed split; preview decode uses the bundled decoders for formats Qt cannot read
- `src/imslim/dialogs.py` — batch progress dialog, completion summary and the About window
- `src/imslim/properties.py` / `exif.py` — per-file Properties dialog (exact dimensions, byte size, EXIF) and its minimal, dependency-free EXIF/TIFF reader
- `src/imslim/now.py` — `NowRunner`: ImSlimNow's analyze→compress run, dialogs and exit codes
- `src/imslim/result_item.py` / `result_item_manager.py` / `result_item_row.py` — per-file state, intake/analysis and the results row widget (thumbnails)
- `src/imslim/clipboard_intake.py` — `ClipboardIntake`: paste-to-paths (URLs or saved image) and temp-dir cleanup
- `src/imslim/composition.py` — `AppContext` / `build_app_context()`: assembles settings, compression manager and batch flow
- `src/imslim/batch_flow.py` / `batch_options.py` / `batch_summary.py` — analysis and the analyze→compress→summary batch, its immutable options snapshot and its counters
- `src/imslim/workers.py` — pooled background tasks (analyze, version probe)
- `src/imslim/settings_manager.py` — persistent settings/state store (`log_file_path()` included)
- `src/imslim/commands.py` — `Command` (`argv` or in-process `action`, plus `temp_files`) and `tokens`
- `src/imslim/compressor.py` — `Compressor` ABC: subclasses produce pure command lists in `build_command()`
- `src/imslim/command_runner.py` — `CommandRunner` (killable subprocess execution) and `CompressionContext` (batch cancellation)
- `src/imslim/pipeline.py` — `CompressionPipeline`: runs a compressor's commands, finalizes output, cleans up and reports errors
- `src/imslim/conversion.py` — `decode_commands()`: bundled decoder or Qt fallback that turns any source into PNG
- `src/imslim/output_writer.py` — `OutputWriter`: moves the temp result into place (optional skip-if-larger, backups, attributes)
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
- Headless batch: `uv run imslim --now FILES...`
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

- Add a setting: Add key + accessors in `src/imslim/settings_manager.py`, expose it in `src/imslim/options_view.py` (or the About view for app-level info), and consume it via `BatchOptions` / the relevant compressor under `src/imslim/compressors/`.
- Add a format: Create a compressor subclass in `src/imslim/compressors/`, add it to `ALL_COMPRESSORS` in `src/imslim/compressors/__init__.py`, and add a `FormatSpec` to `FORMAT_SPECS` in `src/imslim/formats.py` (MIME + extensions, decoder, knobs). Every lookup table, the file-dialog filter, the settings defaults and the format selector are derived from it.
- Add a decoder: map the source MIME to a bundled tool in `DECODER_TOOLS` (`src/imslim/formats.py`), add the tool to `KNOWN_TOOLS` in `src/imslim/binary_resolver.py` and build it in `scripts/build_tools.sh` + `tools.lock`. Without a decoder, `decode_commands()` falls back to Qt decoding via `image_convert.to_png()`.
- Translate a string: wrap it in `_()` from `imslim._i18n`, then run `./scripts/translations.sh all`. Add a language with `./scripts/translations.sh init <lang>`, translate its `.po`, and rerun.
- Compressor pipeline: override `build_command(result_item, options, input_path)` to return a pure `list[Command]` (a `NamedTuple` of `argv: list[str] | None`, `action: Callable[[], None] | None`, `stdout_path: str | None`, `ignore_errors: bool`, `temp_files: tuple[str, ...]`, `adapt: Callable[[list[str]], list[str]] | None`, defined in `src/imslim/commands.py`). Declare every temporary file a command creates in `temp_files` so cleanup is derived; implement `get_file_type()` as needed. Pre-decode with `decode_commands()` rather than doing work in the builder.
- State access: Read/write mode and settings through `SettingsManager` (exposed on the window as `self.settings`).

---

## General Guidelines

### Code Changes

- For non-trivial work, propose an approach and confirm before implementing, including architectural changes.
- Keep modifications minimal and scoped; prefer incremental improvements over rewrites.
- Use explicit types and named constants (no magic numbers).
- Return explicit error types; do not suppress exceptions.
- Follow standard repository linting and formatting configs.
- Decompose files over 400 lines if they mix concerns.
- Name things clearly; reserve comments for the non-obvious why (workarounds, edge cases).
- Never run git mutations (commit, push, reset, rebase, amend) unless explicitly instructed.
- Do not create documentation files unless explicitly requested.
- Adhere to <https://develop.kde.org/hig/>.

### Author Environment

- Ryzen 5800X3D, Radeon RX 7900 XT, Display (AW3225QF); CachyOS, KDE, KWin / Wayland, Btrfs.
- fish shell, Ghostty terminal, Fresh TUI editor, yay package manager, bun npm manager, Firefox, Zed code editor.

### Testing

- Add tests only when the logic is genuinely testable and worth guarding. No test files for trivial changes or behavior the environment cannot test reliably (e.g. UI layout/click mapping).

### Definition of Done

- Logic fully implemented.
- Existing docs updated if public interfaces changed.
- Run the corresponding `Workflow` command when `Verification` requires it.

### Commit Messages

- On completion of an update or fix, print a conventional commit message in a fenced code block.
- Add a body only when the "why" isn't obvious.
- Never hard-wrap: one physical line per paragraph, however long.

### Communication Style

- Format: short declarative sentences, one idea per line.
- Instructions: numbered steps, one action each (exact command, path, or code); no prose recap.
- Explanations: essential context only. End question answers with `TL;DR:`, one sentence; omit for status updates and completed work.
- Tone: no preamble, restating, hedging, disclaimers, emotional framing, or closing offers. Keep every fact, command, flag, path, default, caveat.
- Edge Cases: state risks explicitly; ask when requirements are ambiguous.
