# ImSlim

A Linux-first image compressor for PNG, JPEG, WebP, AVIF, JXL, GIF, and SVG images. Built with Python / PySide6 with native rendering under KDE Plasma.

Inspired by [Curtail](https://github.com/Huluti/Curtail).

## Supported formats

PNG, JPEG, GIF, WebP, AVIF, JXL, SVG — both lossless and lossy modes, with options to keep or strip metadata. Animated GIFs are always compressed losslessly. JXL re-compression decodes via `djxl` and re-encodes via `cjxl`; EXIF/XMP/JUMBF metadata is preserved when the metadata option is enabled.

## Requirements

The compression backend shells out to standard Linux CLI tools (distro packages):

- [oxipng](https://github.com/shssoichiro/oxipng)
- [pngquant](https://pngquant.org)
- [libjxl](https://github.com/libjxl/libjxl) (`cjpegli`/`djpegli`, `cjxl`/`djxl`)
- [mozjpeg](https://github.com/mozilla/mozjpeg) (`jpegtran`)
- [libwebp](https://developers.google.com/speed/webp) (`cwebp`)
- [libavif](https://github.com/AOMediaCodec/libavif) (`avifenc`/`avifdec`)
- [gifsicle](https://www.lcdf.org/gifsicle/)
- [svgo](https://github.com/svg/svgo)

On Debian/Ubuntu:

```sh
sudo apt install oxipng pngquant libjxl-tools mozjpeg webp libavif-bin gifsicle
npm install -g svgo
```

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
