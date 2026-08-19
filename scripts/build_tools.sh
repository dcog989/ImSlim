#!/usr/bin/env bash
# Builds the bundled compression tools for linux-x86_64 from pinned sources.
#
# Output: src/imslim/bin/linux-x86_64/  (each tool plus its LICENSE)
#
# Run from the repository root:
#   ./scripts/build_tools.sh            # builds everything
#   ./scripts/build_tools.sh libjxl     # builds a single tool group
#
# Tools / pinned sources:
#   libjxl  (cjxl djxl)                   -> v0.12.0
#   jpegli  (cjpegli djpegli)             -> v0.12.0
#   mozjpeg (jpegtran)                    -> v4.1.5
#   oxipng                                -> v9.1.0
#   pngquant                              -> 3.0.3
#   libwebp (cwebp)                       -> v1.4.0
#   libavif (avifenc avifdec)             -> v1.2.1
#   gifsicle                              -> v1.95
#   node + svgo                           -> node v22.x LTS, svgo@^3

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/src/imslim/bin/linux-x86_64"
WORK="$ROOT/.build"
JOBS="${JOBS:-$(nproc)}"
PREFIX="$WORK/prefix"

mkdir -p "$OUT" "$WORK" "$PREFIX"

log() { printf '\033[1;36m[build]\033[0m %s\n' "$*"; }

install_deps() {
    if ! command -v apt-get >/dev/null 2>&1; then
        log "only apt-based images are supported; skipping dependency install"
        return
    fi
    apt-get update -qq
    apt-get install -y -qq \
        build-essential cmake ninja-build pkg-config curl git \
        libpng-dev zlib1g-dev libjpeg-dev libwebp-dev \
        libhwy-dev libbrotli-dev liblcms2-dev libaom-dev libyuv-dev \
        libsqlite3-dev libzstd-dev libtiff-dev && true
}

# ---------------------------------------------------------------------------
# libjxl (cjxl djxl)
# ---------------------------------------------------------------------------
build_libjxl() {
    local tag=v0.12.0
    if [[ -d "$WORK/libjxl" ]]; then
        cd "$WORK/libjxl" && git fetch origin tag "$tag" && git checkout -q "$tag"
    else
        git clone -q --depth 1 --branch "$tag" https://github.com/libjxl/libjxl.git "$WORK/libjxl"
        cd "$WORK/libjxl"
    fi
    ./deps.sh

    cmake -B build -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX="$PREFIX" \
        -DBUILD_SHARED_LIBS=OFF \
        -DJPEGXL_ENABLE_TOOLS=ON \
        -DJPEGXL_ENABLE_DEVTOOLS=OFF \
        -DJPEGXL_ENABLE_BENCHMARK=OFF \
        -DJPEGXL_ENABLE_EXAMPLES=OFF \
        -DJPEGXL_ENABLE_PLUGINS=OFF \
        -DJPEGXL_ENABLE_SJPEG=OFF \
        -DJPEGXL_ENABLE_VIEWERS=OFF \
        -DJPEGXL_ENABLE_FLAC=OFF \
        -DJPEGXL_ENABLE_TCMALLOC=OFF \
        -DJPEGXL_STATIC=ON
    cmake --build build -j"$JOBS"
    cmake --install build

    cp "$PREFIX/bin/cjxl" "$OUT/cjxl"
    cp "$PREFIX/bin/djxl" "$OUT/djxl"
    chmod +x "$OUT/cjxl" "$OUT/djxl"
    cp LICENSE "$OUT/LICENSE-libjxl"
}

# ---------------------------------------------------------------------------
# jpegli (cjpegli djpegli)
# jpegli has no releases; pin a specific main commit.
# ---------------------------------------------------------------------------
build_jpegli() {
    local commit=031a0077f5799a6041004267fc12b956c1f52a20
    if [[ -d "$WORK/jpegli" ]]; then
        cd "$WORK/jpegli" && git fetch origin "$commit" && git checkout -q "$commit"
    else
        git clone -q https://github.com/google/jpegli.git "$WORK/jpegli"
        cd "$WORK/jpegli"
        git checkout -q "$commit"
    fi
    ./deps.sh

    cmake -B build -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX="$PREFIX" \
        -DBUILD_SHARED_LIBS=OFF \
        -DJPEGXL_ENABLE_TOOLS=ON \
        -DJPEGXL_ENABLE_DEVTOOLS=OFF \
        -DJPEGXL_ENABLE_PLUGINS=OFF
    cmake --build build -j"$JOBS"
    cmake --install build

    for tool in cjpegli djpegli; do
        cp "$PREFIX/bin/$tool" "$OUT/$tool"
        chmod +x "$OUT/$tool"
    done
    cp LICENSE "$OUT/LICENSE-jpegli"
}

# ---------------------------------------------------------------------------
# mozjpeg (jpegtran)
# ---------------------------------------------------------------------------
build_mozjpeg() {
    local tag=v4.1.5
    if [[ -d "$WORK/mozjpeg" ]]; then
        cd "$WORK/mozjpeg" && git fetch origin tag "$tag" && git checkout -q "$tag"
    else
        git clone -q --depth 1 --branch "$tag" https://github.com/mozilla/mozjpeg.git "$WORK/mozjpeg"
        cd "$WORK/mozjpeg"
    fi

    cmake -B build -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX="$PREFIX" \
        -DENABLE_STATIC=ON \
        -DENABLE_SHARED=OFF \
        -DWITH_JPEG8=ON \
        -DPNG_SUPPORTED=OFF
    cmake --build build -j"$JOBS"
    cmake --install build

    cp "$PREFIX/bin/jpegtran" "$OUT/jpegtran"
    chmod +x "$OUT/jpegtran"
    cp "$PREFIX/share/doc/libjpeg-turbo/LICENSE.md" "$OUT/LICENSE-jpegtran"
}

# ---------------------------------------------------------------------------
# oxipng
# ---------------------------------------------------------------------------
build_oxipng() {
    local tag=v9.1.0
    if [[ -d "$WORK/oxipng" ]]; then
        cd "$WORK/oxipng" && git fetch origin tag "$tag" && git checkout -q "$tag"
    else
        git clone -q --depth 1 --branch "$tag" https://github.com/shssoichiro/oxipng.git "$WORK/oxipng"
        cd "$WORK/oxipng"
    fi

    cargo build --release -j"$JOBS"
    cp target/release/oxipng "$OUT/oxipng"
    chmod +x "$OUT/oxipng"
    cp LICENSE "$OUT/LICENSE-oxipng"
}

# ---------------------------------------------------------------------------
# pngquant
# ---------------------------------------------------------------------------
build_pngquant() {
    local tag=3.0.3
    if [[ -d "$WORK/pngquant" ]]; then
        cd "$WORK/pngquant"
        git fetch -q origin tag "$tag" --force
        git checkout -q "$tag"
    else
        git clone -q --depth 1 --branch "$tag" https://github.com/kornelski/pngquant.git "$WORK/pngquant"
        cd "$WORK/pngquant"
    fi

    # pngquant grabs libpng dynamically unless given one; build with the static
    # system zlib/libpng when present, otherwise fall back to its internal copy.
    ./configure --prefix="$PREFIX" --enable-static --disable-shared || \
        make install PREFIX="$PREFIX"
    make -j"$JOBS" || true
    cp pngquant "$OUT/pngquant" 2>/dev/null || cp "$PREFIX/bin/pngquant" "$OUT/pngquant"
    chmod +x "$OUT/pngquant"
    cp COPYRIGHT "$OUT/LICENSE-pngquant" 2>/dev/null || true
}

# ---------------------------------------------------------------------------
# libwebp (cwebp)
# ---------------------------------------------------------------------------
build_webp() {
    local tag=v1.4.0
    if [[ -d "$WORK/libwebp" ]]; then
        cd "$WORK/libwebp" && git fetch origin tag "$tag" && git checkout -q "$tag"
    else
        git clone -q --depth 1 --branch "$tag" https://github.com/webmproject/libwebp.git "$WORK/libwebp"
        cd "$WORK/libwebp"
    fi

    cmake -B build -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX="$PREFIX" \
        -DBUILD_SHARED_LIBS=OFF \
        -DWEBP_BUILD_CWEBP=ON \
        -DWEBP_BUILD_DWEBP=OFF \
        -DWEBP_BUILD_ANIM_UTILS=OFF \
        -DWEBP_BUILD_GIF2WEBP=OFF \
        -DWEBP_BUILD_IMG2WEBP=OFF \
        -DWEBP_BUILD_VWEBP=OFF \
        -DWEBP_BUILD_WEBPINFO=OFF
    cmake --build build -j"$JOBS"
    cmake --install build

    cp "$PREFIX/bin/cwebp" "$OUT/cwebp"
    chmod +x "$OUT/cwebp"
    cp COPYING "$OUT/LICENSE-cwebp"
}

# ---------------------------------------------------------------------------
# libavif (avifenc avifdec)
# ---------------------------------------------------------------------------
build_avif() {
    local tag=v1.2.1
    if [[ -d "$WORK/libavif" ]]; then
        cd "$WORK/libavif" && git fetch origin tag "$tag" && git checkout -q "$tag"
    else
        git clone -q --depth 1 --branch "$tag" --recursive https://github.com/AOMediaCodec/libavif.git "$WORK/libavif"
        cd "$WORK/libavif"
    fi

    cmake -B build -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX="$PREFIX" \
        -DBUILD_SHARED_LIBS=OFF \
        -DAVIF_BUILD_APPS=ON \
        -DAVIF_CODEC_AOM=LOCAL \
        -DAVIF_CODEC_DAV1D=OFF \
        -DAVIF_LIBYUV=LOCAL \
        -DAVIF_JPEG=SYSTEM \
        -DAVIF_PNG=SYSTEM \
        -DAVIF_ZLIBPNG=OFF \
        -DAVIF_ENABLE_WERROR=OFF
    cmake --build build -j"$JOBS"
    cmake --install build

    for tool in avifenc avifdec; do
        cp "$PREFIX/bin/$tool" "$OUT/$tool"
        chmod +x "$OUT/$tool"
    done
    cp LICENSE "$OUT/LICENSE-avif"
}

# ---------------------------------------------------------------------------
# gifsicle
# ---------------------------------------------------------------------------
build_gifsicle() {
    local tag=v1.95
    if [[ -d "$WORK/gifsicle" ]]; then
        cd "$WORK/gifsicle" && git fetch origin tag "$tag" && git checkout -q "$tag"
    else
        git clone -q --depth 1 --branch "$tag" https://github.com/kohler/gifsicle.git "$WORK/gifsicle"
        cd "$WORK/gifsicle"
    fi

    ./autogen.sh
    ./configure --prefix="$PREFIX" --disable-shared --enable-static
    make -j"$JOBS"
    make install

    cp "$PREFIX/bin/gifsicle" "$OUT/gifsicle"
    chmod +x "$OUT/gifsicle"
    cp LICENSE "$OUT/LICENSE-gifsicle"
}

# ---------------------------------------------------------------------------
# node + svgo
# Svgo is a Node tool: bundle a static node runtime with the npm package.
# ---------------------------------------------------------------------------
build_svgo() {
    local node_ver=v22.16.0
    if [[ ! -f "$WORK/node/bin/node" ]]; then
        curl -fsSLO "https://nodejs.org/dist/$node_ver/node-$node_ver-linux-x64.tar.xz"
        mkdir -p "$WORK/node"
        tar -xJf "node-$node_ver-linux-x64.tar.xz" -C "$WORK/node" --strip-components=1
    fi

    cp "$WORK/node/bin/node" "$OUT/node"
    "$WORK/node/bin/npm" install --prefix "$OUT/svgo-dist" svgo@^3 --no-audit --no-fund

    cat > "$OUT/svgo" <<'EOF'
#!/bin/sh
DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
exec "$DIR/node" "$DIR/svgo-dist/node_modules/svgo/bin/svgo" "$@"
EOF
    chmod +x "$OUT/svgo" "$OUT/node"
    cp "$OUT/svgo-dist/node_modules/svgo/LICENSE" "$OUT/LICENSE-svgo"
}

main() {
    local groups=("$@")
    [[ ${#groups[@]} -eq 0 ]] && groups=(libjxl jpegli mozjpeg oxipng pngquant webp avif gifsicle svgo)

    install_deps
    for group in "${groups[@]}"; do
        log "building $group"
        "build_$group"
    done
    log "done — tools installed in $OUT"
}

main "$@"