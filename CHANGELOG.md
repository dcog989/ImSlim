# Changelog

All notable changes to this project will be documented in this file. See [conventional commits](https://www.conventionalcommits.org/) for commit guidelines.

- - -
## v0.12.0 - 2026-11-09

#### Features

- (01cf545) register ImSlim as a handler for directories - dcog989

- (f450e3a) choose the folder the Add Files and Add Directory dialogs start in - dcog989

- (6716bb6) rotate the log daily as well as at 1 MB, keeping nine backups - dcog989

- (68a8600) use a circle-x icon for clearing the queue - dcog989

- (4991e85) show the full destination file path above the after image - dcog989

- (533c36a) mark the format-notes button '!' and add hint dialogs to flag knobs - dcog989

- (f0f9088) always on image compare - dcog989

- (e08e1e2) list every file with its percent change in the completion dialog - dcog989

- (811de11) show per-format caveats in a click popup - dcog989

- (d0d6b22) three-column v2 window with persistent queue, live comparison and ImSlimNow - dcog989

#### Bug Fixes

- (f660f17) install the release desktop and icon assets - dcog989

- (c63711a) keep the svgo pin and its npm lock in step - dcog989

- (9059187) stop silent success paths in the app shell - dcog989

- (8c57078) report exact dimensions and keep the dialog responsive - dcog989

- (e26be55) free progress dialogs, gate Ctrl+0, save once - dcog989

- (6c19646) skip the preview re-encode for destination-only changes - dcog989

- (cc22efa) report a selection only when the shown file changes - dcog989

- (aaafe58) decode an output that was rewritten in place - dcog989

- (af59d3a) keep the About and completion dialogs truthful - dcog989

- (1d34ebf) keep the comparison pane responsive and truthful - dcog989

- (f1fdcc2) address the remaining audit findings - dcog989

- (0ca7df8) keep the progress dialog alive, force lossy JPEG, and strip JUMBF - dcog989

- (b1a77ba) correct selection, thumbnail and row-cap state - dcog989

- (37bc070) correct row sizing, text handling, queue selection and the progress dialog - dcog989

- (1e3fe61) refresh About and Properties text on theme change - dcog989

- (ecc8204) sharpen icons on high-DPI screens - dcog989

- (ab355a3) refresh muted labels and painted icons on theme change - dcog989

- (223ae13) keep the row shade consistent after a refresh - dcog989

- (f7dce47) show a placeholder when a preview fails - dcog989

- (5881963) read the live palette without compounding the tint - dcog989

- (3f021e4) follow a live theme change and drop dead helpers - dcog989

- (82173e1) keep paths that are not valid UTF-8 intact - dcog989

- (6188609) keep previews honest, show scan progress and save state on quit - dcog989

- (cdbb7a9) bound decoder concurrency and stop re-decoding the source - dcog989

- (afee66c) keep the saved compression mode when JPEG is selected - dcog989

- (2237b93) keep selection stable and stop thumbnail work piling up - dcog989

- (5425d4c) defer folder validation and label the real destination folder - dcog989

- (9c23e98) harden overwrite naming and destination handling - dcog989

- (64c8603) cap thumbnail decode size and tighten SVG animation sniffing - dcog989

- (56d4218) save pasted images in Pictures instead of a temp dir - dcog989

- (24b30c6) apply skip-if-larger only when the format is unchanged - dcog989

- (681bb73) rewrite metadata through an atomic temp file - dcog989

- (b46750f) keep encoder metadata, orientation and resources correct - dcog989

- (9c90813) resolve a tool installed after startup - dcog989

- (32bdec2) keep JPEG metadata on JXL and bound avifenc threads - dcog989

- (4534ff7) bound bundled decoders and support large rotated sources - dcog989

- (ce0f519) harden values read from the config file - dcog989

- (2945ba3) report an unusable output folder in ImSlimNow too - dcog989

- (beae97c) cache the tool version probe - dcog989

- (96ca55d) run Qt decodes in a cancellable helper and separate the Now log - dcog989

- (aca085d) bound large queues and completion lists, delete unused helpers - dcog989

- (b9fa8ef) reject an empty output folder and disambiguate batch names - dcog989

- (dbfc94d) keep PNG metadata on lossy re-encodes and harden EXIF - dcog989

- (f5937f8) keep pasted sources and results until the queue releases them - dcog989

- (534ea61) prepare output names off the UI thread and ignore stale analysis - dcog989

- (2f7df59) ship the bundled tools at the frozen resolver path - dcog989

- (5b0e7f1) disable Remove from Queue when the view has no selection - dcog989

- (3d3ae31) various UI refinements, docs - dcog989

- (f1111dc) mark the selected thumbnail with a 4px border instead of the style underline - dcog989

- (0208431) keep the original stem when overwriting with a conversion - dcog989

- (01e265d) refresh the compare destination path when save options change - dcog989

- (1ae03f3) label the savings percentage as saved - dcog989

- (1af7079) lighten spinner input - dcog989

- (04b225e) drop the unused checkbox text spacing so boxes align with the fields - dcog989

- (c297815) keep the progress counter from shifting as the count grows - dcog989

- (353b966) let each pane fit its own area when the splitter is dragged - dcog989

- (8180891) disable Lossless for JPEG output and force the lossy encoder - dcog989

- (fa56884) unbold queue file names and shorten option labels - dcog989

- (9dc60ac) report the real output size in the completion summary - dcog989

- (06c92bd) show GIF and SVG knobs when keeping the source format - dcog989

- (ea905cf) gate keyboard zoom to the focused comparison pane - dcog989

- (409b6a9) cover-crop square thumbnails to the shortest side - dcog989

#### Performance

- (a69cb72) render every icon size in one pass - dcog989

- (681b80c) add analyzed files in one signal - dcog989

#### Refactoring

- (c5ed2c0) move recursive and timestamped-dir checkboxes up - dcog989

- (464621b) share the decode command runner - dcog989

- (ce22dd2) fold the one-shot command helpers - dcog989

- (6b8cba1) derive lookups and drop dead branches - dcog989

- (deb6cb7) build the settings once and pass them to logging - dcog989

- (a8826ec) align every checkbox in one shared form column - dcog989

- (ce0d528) compact inline form with sectioned groups - dcog989
- - -

## v0.11.4 - 2026-11-01

#### Bug Fixes

- (08f4406) build cwebp with static libjpeg so JPEG input works - dcog989

- (a577892) match the settings gear height to the header combos - dcog989

- (afdf263) accept every file and path the user gives - dcog989

- (414cc77) write through a queue so reconfiguring cannot hit a closed file - dcog989

- (46a8fb7) protect output files and clean up reliably - dcog989

- (70c2d27) prefer the most specific Qt plugin root - dcog989

#### Performance

- (773a3e7) bound decode work and UI updates during big batches - dcog989

#### Refactoring

- (32274da) remove dead wiring and duplicated format tables - dcog989
- - -

## v0.11.3 - 2026-10-15

#### Bug Fixes

- (a70de83) make every form field share one inset and stop stretching - dcog989

- (b38a81f) set the Wayland desktop file name so the dock shows ImSlim's icon - dcog989
- - -

## v0.11.2 - 2026-10-12

#### Bug Fixes

- (639a462) defer PySide6 QtGui imports in image_utils - dcog989
- - -

## v0.11.1 - 2026-10-12

#### Bug Fixes

- (1726c8d) defer PySide6 QtGui import in image_convert - dcog989

- (9bc47a7) include perf commits in the changelog - dcog989
- - -

## v0.11.0 - 2026-10-12

#### Features

- (0526cb4) load real gettext catalogs and add translation tooling - dcog989

- (bc2ba7c) handle --help/--version and stop treating flags as file paths - dcog989

#### Bug Fixes

- (63c37c6) pad spin box text like the other input fields - dcog989

- (30fe635) restore the ruff BLE001 ignore for intentional broad excepts - dcog989

- (5eb845a) pin svgo's dependency tree with a committed npm lockfile - dcog989

- (a1cac4a) merge into tools.lock so a partial --update can't drop pins - dcog989

- (ac519b3) run the test suite before cog bumps the version - dcog989

- (8df624f) lock dependency sync so a stale uv.lock fails instead of re-resolving - dcog989

- (608e6b3) keep the bundled tools out of `make clean` - dcog989

- (f48225c) mark Makefile targets phony so directory names can't shadow them - dcog989

- (cfca898) declare GPL-3.0-only and ship LICENSE in the distributions - dcog989

- (5a6e242) widen uv_build pin to <0.14 to silence build warning on uv 0.13 - dcog989

- (43a9388) stop queued rows showing 100% savings before compression - dcog989

- (7af615d) use quality 100 when Lossless is selected for a JPEG target - dcog989

- (c62a2b8) keep EXIF/XMP when re-encoding to JPEG or AVIF - dcog989

- (18a98c6) cap the single-instance payload to a few MB per connection - dcog989

- (f9e4848) flush each setting to disk as it is written - dcog989

- (3f22567) describe the results page from the batch snapshot, not live settings - dcog989

- (1ebae57) serialize the single-instance primary decision with a lock file - dcog989

- (c7f0e46) reset previous results when a new batch starts - dcog989

- (a1919bd) build bundled tools before packaging the wheel - dcog989

- (f121ba3) disable Clear Results while a batch is compressing - dcog989

#### Refactoring

- (95c39d3) use uv from a cold checkout and export ARCH - dcog989

- (6ecd615) unify pool-size formula into one worker_count helper - dcog989

- (2857227) merge the two tool-button helpers into one - dcog989

- (16fb87d) delete dead debug_pairs, set_knob and stray conversion export - dcog989
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
