# ImSlim

A Linux-first image compressor for PNG, JPEG, WebP, AVIF, JXL, GIF, and SVG images. Built with Python / PySide6 with native rendering under KDE Plasma.

Inspired by [Curtail](https://github.com/Huluti/Curtail).

## Supported formats

PNG, JPEG, GIF, WebP, AVIF, JXL, SVG — both lossless and lossy modes, with options to keep or strip metadata. Animated GIFs are always compressed losslessly. JXL re-compression decodes via `djxl` and re-encodes via `cjxl`; EXIF/XMP/JUMBF metadata is preserved when the metadata option is enabled.

## Requirements

The compression backends are bundled with the app (no system packages needed). They are built from pinned sources by `./scripts/build_tools.sh` (see `.github/workflows/build-binaries.yml`), then shipped inside the wheel under `src/imslim/bin/linux-x86_64`, along with their licenses:

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
uv sync          # install deps (PySide6)
uv run imslim    # run the app
uv run python -m imslim
```

Lint / format:

```sh
make analyze
make format
```

## License

GNU GENERAL PUBLIC LICENSE (v3)
