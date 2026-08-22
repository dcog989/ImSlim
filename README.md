# ImSlim

A Linux-first image compressor. Compress all common image formats lossy or lossless, strip metadata, retain file attributes.

Inspired by [Curtail](https://github.com/Huluti/Curtail).

## Supported formats

PNG, JPEG, GIF, WebP, AVIF, JXL, SVG — lossless and lossy modes, with options to keep or strip metadata.

BMP and TIFF are re-encoded to WebP (lossless or lossy per the mode) — the original files are always left untouched for these two, and the compressed result is written as a new `.webp` file.

Animated GIFs are always compressed losslessly. JXL re-compression decodes via `djxl` and re-encodes via `cjxl`; EXIF/XMP/JUMBF metadata is preserved when the metadata option is enabled.

## Tech Stack

Built with Python / PySide6 with native rendering under KDE Plasma.

The compression backends are bundled with the app (no system packages needed). They are built from the latest stable releases by `./scripts/build_tools.sh` (see `.github/workflows/build-binaries.yml`), which rebuilds each tool only when a newer version is available, then shipped inside the wheel under `src/imslim/bin/linux-x86_64`, along with their licenses:

- [libjxl](https://github.com/libjxl/libjxl) (`cjxl`/`djxl`)
- [jpegli](https://github.com/google/jpegli) (`cjpegli`/`djpegli`)
- [mozjpeg](https://github.com/mozilla/mozjpeg) (`jpegtran`)
- [oxipng](https://github.com/shssoichiro/oxipng)
- [pngquant](https://pngquant.org)
- [libwebp](https://developers.google.com/speed/webp) (`cwebp`)
- [libavif](https://github.com/AOMediaCodec/libavif) (`avifenc`/`avifdec`)
- [gifsicle](https://www.lcdf.org/gifsicle/)
- [node](https://nodejs.org) + [svgo](https://github.com/svg/svgo)

On Debian/Ubuntu, the bundled binaries are used automatically; setting `IMSLIM_TOOLS_PATH` overrides them, and tools absent from the bundle fall back to `PATH` (useful during development).

## Development

```sh
uv sync            # install deps (PySide6)
uv lock --upgrade  # upgrade deps
uv run imslim      # run the app
uv cache clean     # remove stale tool cache
uv clean           # clear global download cache
```

Lint / format:

```sh
make analyze
make format
```

Install (user-level):

```sh
uv tool install .
mkdir -p ~/.local/share/applications ~/.local/share/icons/hicolor/scalable/apps
install -Dm644 assets/imslim.desktop ~/.local/share/applications/imslim.desktop
install -Dm644 src/imslim/assets/imslim.svg ~/.local/share/icons/hicolor/scalable/apps/imslim.svg
kbuildsycoca6   # refresh the KDE application cache
```

The desktop entry declares the app as a handler for PNG, JPEG, GIF, WebP, AVIF, JXL, BMP and TIFF; SVG is intentionally excluded so ImSlim is not offered as the default SVG opener.

Full clean:

```sh
rm -rf .venv dist src/*.egg-info && find . -name __pycache__ -type d -exec rm -rf {} +
```

### Build + Install

```sh
uv tool install .

mkdir -p ~/.local/share/applications ~/.local/share/icons/hicolor/scalable/apps

printf '[Desktop Entry]\nName=ImSlim\nExec=imslim\nIcon=imslim\nTerminal=false\nType=Application\nCategories=Graphics;\n' > ~/.local/share/applications/imslim.desktop

cp src/imslim/assets/imslim.svg ~/.local/share/icons/hicolor/scalable/apps/imslim.svg

kbuildsycoca6

uv tool upgrade imslim
uv tool install . --force  # force install even if version has not changed
```

## License

GNU GENERAL PUBLIC LICENSE (v3)
