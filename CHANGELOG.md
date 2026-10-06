# Changelog

All notable changes to this project will be documented in this file. See [conventional commits](https://www.conventionalcommits.org/) for commit guidelines.

- - -
## v0.10.0 - 2026-10-06

#### Features

- (5948cdc) rebrand accent color for logo - dcog989

#### Bug Fixes

- (633866a) use integer HSL API and explicit string concatenation - dcog989

- (9e23290) strip cancel-looking icon from done button - dcog989

- (15232bd) dim custom folder label when inactive - dcog989
- - -

## v0.9.0 - 2026-10-04

#### Features

- (c0afaa2) persist window size and narrow the default width - dcog989

- (37bea6d) show drop indicator when dragging files in - dcog989

- (42ec086) add original-file and copy-error actions to row menu - dcog989

- (27fc0a7) add Open Output Folder button for custom-folder saves - dcog989

- (4c6cfc5) fold output folder into the save method choice - dcog989

- (c116a67) add "Output format:" label before the format dropdown - dcog989

- (ddfd3f9) record session opener at startup - dcog989

- (a22696e) warn per item when animation is dropped - dcog989

- (dae4618) clean up running batch when the window closes - dcog989

#### Bug Fixes

- (4cd1b9b) process explicitly passed files that look like generated output - dcog989

- (584e0b7) silence basedpyright warnings from recent UI changes - dcog989

- (715b7c9) explain overwrite limitation for re-encoded formats - dcog989

- (99f311f) relabel settings dialog button "Close" to "Done" - dcog989

- (4255b7e) describe skipped rows as "Already optimal" - dcog989

- (8fd2044) drop redundant log file path line from startup - dcog989

- (85e01aa) resolve basedpyright warnings so make check passes - dcog989

- (6c184c3) clear prefs dialog reference on finish to keep settings reopenable - dcog989

- (52da272) replace assert-based validation with explicit exceptions - dcog989

- (0d02c6d) mark result rows running only when a worker starts them - dcog989

- (8e84943) configure logging only in the primary process - dcog989

- (0122ca6) dedupe input files and skip ImSlim's own outputs - dcog989

- (64d8757) stop rewriting settings when the dialog opens - dcog989

- (aa65224) parse local paths from Qt arguments instead of raw sys.argv - dcog989

- (6fe555b) add rows in input order instead of reversed - dcog989

- (1b6d05d) keep running thumbnail tasks alive until run() completes - dcog989

- (922c933) ship constant svgo configs as assets instead of writing to source dir - dcog989

- (621bd83) delete settings dialog on close - dcog989

- (0404867) follow XDG base directory spec for logs and IPC socket - dcog989

- (b2fc723) store clipboard images in a private temp dir and clean up - dcog989

- (d54c865) deinterlace with oxipng instead of forcing Adam7 - dcog989

- (c2e4669) restore original file permissions, not just timestamps - dcog989

- (7851123) keep raw error details and render them as plain text - dcog989

- (b75988b) recover app state when analysis fails unexpectedly - dcog989

- (116bce9) mark post-command cancellation as cancelled - dcog989

- (e87bc63) iterate handler snapshot when reconfiguring - dcog989

- (c51be53) forward paths before claiming primary - dcog989

- (1b12db3) consistent menu naming 'Select' - dcog989

- (9388d80) record build config hash per tool to avoid redundant rebuilds - dcog989

#### Refactoring

- (4a99b27) move overwrite save-method note into combo tooltip - dcog989

- (6480a41) derive item subtitle and savings in the row view - dcog989

- (02c427d) derive compressor and output extension from MIME_TO_FORMAT - dcog989

- (672f32b) split widgets.py into theme, icons and spinner modules - dcog989

- (7557199) extract ResultsView, ClipboardIntake and AppContext - dcog989

- (2fa0ef4) make ResultItem a dataclass and signal updates via BatchFlow - dcog989

- (c3c0c97) replace SettingsTab base class with module-level helpers - dcog989

- (3d5a1b9) unify background jobs on a pooled QRunnable Task base - dcog989

- (f330b6a) rename *_lossless_level knobs to *_effort - dcog989

- (a614ba2) move argv adaptation onto Command - dcog989

- (fa6d0ad) add composition root for compressor wiring - dcog989

- (800dabe) make compressor builders pure and derive cleanup from commands - dcog989

- (9bc574f) split Compressor into command strategy, runner, and pipeline - dcog989

- (8e7edba) use Format/CompressorType/View enums instead of loose strings - dcog989

- (c9636b2) derive result subtitle in row refresh - dcog989

- (315a66b) give result rows their own container and drop magic count check - dcog989

- (602cb2c) finalize run() via try/finally and drop _mark_cancelled - dcog989

- (f1775f5) replace status booleans with ResultState enum - dcog989

- (6f4b5a6) replace paste event filter with contextMenuEvent - dcog989

- (b66a3d6) drop dead cache/try-except and tighten compressor exports - dcog989

- (da40f17) drop duplicate guard and unused row list - dcog989

- (cc28e1e) replace recursive radio pair with a checkbox - dcog989

- (47b6a51) drop unused prepare_batch/finish_batch hooks - dcog989

- (11049b4) dedupe log levels and hoist record_done - dcog989

- (546afa5) centralize format metadata in a single FormatSpec table - dcog989

- (562ba0a) extract shared icon stroke setup - dcog989

- (6894f98) share one mime→decoder mapping across pre-decode paths - dcog989

- (e3d3d4a) freeze per-batch options into one dataclass - dcog989

- (31c85de) split dialog into per-tab package and drop redundant save-all - dcog989

- (6a5ad47) centralize tool metadata and add cmake_release_build helper - dcog989
- - -

## v0.8.1 - 2026-09-17

#### Bug Fixes

- (c3961f0) mark webp _intermediate_path as override - dcog989

- (0386bb7) set filename before stat lookup - dcog989

#### Refactoring

- (a501c11) alphabetise image formats - dcog989

- (9ef66c1) name magic numbers in avif/jxl/webp - dcog989

- (f225ea7) document and guard single-batch assumption - dcog989

- (d4aa6d2) dedupe _intermediate_path across compressors - dcog989

- (4e1aa47) remove dead code - dcog989
- - -

## v0.8.0 - 2026-09-16

#### Features

- (7e78212) add batch image conversion to a single target format - dcog989

- (bbb27ac) add uninstall target - dcog989

#### Bug Fixes

- (b7416e9) accept variable-length tuples in _build_option_combo - dcog989
- - -

## v0.7.0 - 2026-09-03

#### Features

- (7080e55) add self-contained AppImage installer script - dcog989

- (5b9177f) balance header so dropdowns center relative to window width - dcog989

- (e00ad69) replace clear-results icon with chevron-left back button - dcog989

- (50f485f) centre "Compression Results" title in the header - dcog989

- (74a647f) hide settings dropdowns and gear icon on results page - dcog989

#### Bug Fixes

- (1d935c2) restore centred dropdowns on home view - dcog989
- - -

## v0.6.0 - 2026-09-03

#### Features

- (682147c) lazily collect environment info on about tab open - dcog989

- (bcf8a13) move about page into a settings tab, drop header icon - dcog989

- (104eb89) expose lossy, metadata and attribute options as home-page dropdowns - dcog989

#### Bug Fixes

- (d9e348a) annotate _about_env_label in __init__ - dcog989

- (721ad61) use smooth transformation for AppImage icons - dcog989

- (d14e711) re-extract node when working tree is missing - dcog989

- (efdb0c7) remove TOCTOU exists+getsize race - dcog989

- (69df91a) delete finished single-instance sockets - dcog989

#### Refactoring

- (113dc42) refine main window layout - dcog989

- (2455e7e) move main page dropdowns to top of window - dcog989
- - -

## v0.5.6 - 2026-08-25

#### Features

- (3df7555) publish changelog section as GitHub release body - dcog989
- - -

## 0.5.5 - 2026-08-24

#### Bug Fixes

- (d9bbdc1) copy desktop entry to AppDir root for appimagetool - dcog989
- - -

## 0.5.4 - 2026-08-24

#### Bug Fixes

- (3c80cc2) install Qt runtime libs and force offscreen for icon rendering - dcog989

- (0583499) match cocogitto display-name commit types and add version header - dcog989
- - -

Changelog generated by [cocogitto](https://github.com/cocogitto/cocogitto).
