# ImSlim

Compress your images — PNG, JPEG, WebP, AVIF and SVG. A Linux-first image
compressor built on [PySide6 / Qt 6](https://doc.qt.io/qtforpython-6/) (renders
natively under Plasma/Breeze), ported from [Curtail](https://github.com/Huluti/Curtail).

## Supported formats

PNG, JPEG, WebP, AVIF, SVG — both lossless and lossy modes, with options to keep
or strip metadata.

## Requirements

The compression backend shells out to standard Linux CLI tools (distro packages):

- [oxipng](https://github.com/shssoichiro/oxipng)
- [pngquant](https://pngquant.org)
- [jpegoptim](https://github.com/tjko/jpegoptim)
- [libwebp](https://developers.google.com/speed/webp) (`cwebp`)
- [libavif](https://github.com/AOMediaCodec/libavif) (`avifenc`/`avifdec`)
- [svgo](https://github.com/svg/svgo)

On Debian/Ubuntu:

```sh
sudo apt install oxipng pngquant jpegoptim webp libavif-bin
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
