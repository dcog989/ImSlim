# Changelog
All notable changes to this project will be documented in this file.

## UNRELEASED

### Added
- Port Curtail to PySide6 / Qt 6 (Linux-first, Plasma/Breeze native).
- Keep the full compression backend (oxipng, pngquant, jpegoptim, cwebp, avif*, scour).
- JXL compression via `cjxl`/`djxl` (lossy and lossless), preserving EXIF/XMP/JUMBF metadata via sidecar extraction and re-injection.
