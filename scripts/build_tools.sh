#!/usr/bin/env bash
# Builds the bundled compression tools for linux-x86_64 from the latest
# available versions: stable release tags where available, latest main for
# jpegli, latest LTS for node, latest svgo from npm.
#
# Incremental: a tool is only rebuilt when a newer version than the one
# recorded in $WORK/.versions is available, or when its output is missing.
#
# Output: src/imslim/bin/linux-x86_64/  (each tool plus its LICENSE)
#
# Run from the repository root:
#   ./scripts/build_tools.sh            # builds/updates everything as needed
#   ./scripts/build_tools.sh libjxl     # builds a single tool group
#   ./scripts/build_tools.sh --force    # rebuild everything regardless
#
# Tools / sources:
#   libjxl  (cjxl djxl)                   -> latest release tag
#   jpegli  (cjpegli djpegli)             -> latest main commit
#   mozjpeg (jpegtran)                    -> latest release tag
#   oxipng                                -> latest release tag
#   pngquant                              -> latest release tag
#   libwebp (cwebp)                       -> latest release tag
#   libavif (avifenc avifdec)             -> latest release tag
#   gifsicle                              -> latest release tag
#   node + svgo                           -> latest LTS node, svgo@latest

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/src/imslim/bin/linux-x86_64"
WORK="$ROOT/.build"
JOBS="${JOBS:-$(nproc)}"
PREFIX="$WORK/prefix"
VERSIONS="$WORK/.versions"
FORCE=0

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
        libdav1d-dev \
        libsqlite3-dev libzstd-dev libtiff-dev && true
}

# ---------------------------------------------------------------------------
# Version resolution helpers
# ---------------------------------------------------------------------------

latest_git_tag() {
    local url="$1"
    git ls-remote --tags --refs "$url" \
        | sed 's/.*\///' \
        | grep -E '^v?[0-9]+\.[0-9]+(\.[0-9]+)?$' \
        | sort -V \
        | tail -n 1
}

latest_git_commit() {
    local url="$1" ref="$2"
    git ls-remote "$url" "refs/heads/$ref" | awk '{print $1}'
}

latest_node_version() {
    curl -fsSL https://nodejs.org/dist/index.json \
        | python3 -c 'import json,sys; print(next(x["version"] for x in json.load(sys.stdin) if x.get("lts")))'
}

latest_svgo_version() {
    curl -fsSL https://registry.npmjs.org/svgo/latest \
        | python3 -c 'import json,sys; print(json.load(sys.stdin)["version"])'
}

# ---------------------------------------------------------------------------
# Incremental-build bookkeeping
# ---------------------------------------------------------------------------

recorded_version() {
    awk -v t="$1" '$1 == t { print $2 }' "$VERSIONS" 2>/dev/null | tail -n 1
}

record_version() {
    if [[ -f "$VERSIONS" ]]; then
        sed -i "/^$1 /d" "$VERSIONS"
    fi
    printf '%s %s\n' "$1" "$2" >> "$VERSIONS"
}

need_build() {
    local tool="$1" version="$2" primary="$3"
    if [[ "$FORCE" -eq 1 ]]; then
        log "$tool: --force set, rebuilding"
        return 0
    fi
    if [[ "$(recorded_version "$tool")" == "$version" && -x "$OUT/$primary" ]]; then
        log "$tool: already up to date ($version), skipping"
        return 1
    fi
    log "$tool: new version available ($version), building"
    return 0
}

ensure_repo() {
    local dir="$1" url="$2" ref="$3"
    if [[ -d "$dir/.git" ]]; then
        git -C "$dir" fetch -q --force origin tag "$ref" --depth 1
        git -C "$dir" checkout -q "$ref"
    else
        git clone -q --depth 1 --branch "$ref" "$url" "$dir"
    fi
}

# ---------------------------------------------------------------------------
# libjxl (cjxl djxl)
# ---------------------------------------------------------------------------
build_libjxl() {
    local url=https://github.com/libjxl/libjxl.git
    local tag; tag="$(latest_git_tag "$url")"
    need_build libjxl "$tag" cjxl || return 0
    ensure_repo "$WORK/libjxl" "$url" "$tag"
    cd "$WORK/libjxl"
    ./deps.sh

    # Reconfig from scratch: stale CMake caches (e.g. after flag changes)
    # otherwise leak old linker flags into the build.
    cmake -E remove_directory build
    cmake -B build -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX="$PREFIX" \
        -DBUILD_SHARED_LIBS=OFF \
        -DBUILD_TESTING=OFF \
        -DJPEGXL_ENABLE_TOOLS=ON \
        -DJPEGXL_ENABLE_DEVTOOLS=OFF \
        -DJPEGXL_ENABLE_BENCHMARK=OFF \
        -DJPEGXL_ENABLE_EXAMPLES=OFF \
        -DJPEGXL_ENABLE_PLUGINS=OFF \
        -DJPEGXL_ENABLE_SJPEG=OFF \
        -DJPEGXL_ENABLE_VIEWERS=OFF \
        -DJPEGXL_ENABLE_FLAC=OFF \
        -DJPEGXL_ENABLE_TCMALLOC=OFF
    cmake --build build -j"$JOBS"
    cmake --install build

    cp "$PREFIX/bin/cjxl" "$OUT/cjxl"
    cp "$PREFIX/bin/djxl" "$OUT/djxl"
    chmod +x "$OUT/cjxl" "$OUT/djxl"
    cp LICENSE "$OUT/LICENSE-libjxl"
    record_version libjxl "$tag"
}

# ---------------------------------------------------------------------------
# jpegli (cjpegli djpegli)
# jpegli has no releases; track the latest main commit.
# ---------------------------------------------------------------------------
build_jpegli() {
    local url=https://github.com/google/jpegli.git
    local commit; commit="$(latest_git_commit "$url" main)"
    need_build jpegli "$commit" cjpegli || return 0
    if [[ -d "$WORK/jpegli/.git" ]]; then
        git -C "$WORK/jpegli" fetch -q origin main --depth 1
        git -C "$WORK/jpegli" checkout -q "$commit"
    else
        git clone -q --depth 1 "$url" "$WORK/jpegli"
        git -C "$WORK/jpegli" checkout -q "$commit"
    fi
    cd "$WORK/jpegli"
    ./deps.sh

    # Reconfig from scratch: stale CMake caches (e.g. after flag changes)
    # otherwise leak old linker flags into the build.
    cmake -E remove_directory build
    cmake -B build -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX="$PREFIX" \
        -DBUILD_SHARED_LIBS=OFF \
        -DBUILD_TESTING=OFF \
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
    record_version jpegli "$commit"
}

# ---------------------------------------------------------------------------
# mozjpeg (jpegtran)
# ---------------------------------------------------------------------------
build_mozjpeg() {
    local url=https://github.com/mozilla/mozjpeg.git
    local tag; tag="$(latest_git_tag "$url")"
    need_build mozjpeg "$tag" jpegtran || return 0
    ensure_repo "$WORK/mozjpeg" "$url" "$tag"
    cd "$WORK/mozjpeg"

    cmake -E remove_directory build
    cmake -B build -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX="$PREFIX" \
        -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
        -DENABLE_STATIC=ON \
        -DENABLE_SHARED=OFF \
        -DWITH_JPEG8=ON \
        -DPNG_SUPPORTED=OFF
    cmake --build build -j"$JOBS"
    cmake --install build

    cp "$PREFIX/bin/jpegtran" "$OUT/jpegtran"
    chmod +x "$OUT/jpegtran"
    cp "$WORK/mozjpeg/LICENSE.md" "$OUT/LICENSE-jpegtran"
    record_version mozjpeg "$tag"
}

# ---------------------------------------------------------------------------
# oxipng
# ---------------------------------------------------------------------------
build_oxipng() {
    local url=https://github.com/shssoichiro/oxipng.git
    local tag; tag="$(latest_git_tag "$url")"
    need_build oxipng "$tag" oxipng || return 0
    ensure_repo "$WORK/oxipng" "$url" "$tag"
    cd "$WORK/oxipng"

    cargo build --release -j"$JOBS"
    cp target/release/oxipng "$OUT/oxipng"
    chmod +x "$OUT/oxipng"
    cp LICENSE "$OUT/LICENSE-oxipng"
    record_version oxipng "$tag"
}

# ---------------------------------------------------------------------------
# pngquant
# ---------------------------------------------------------------------------
build_pngquant() {
    local url=https://github.com/kornelski/pngquant.git
    local tag; tag="$(latest_git_tag "$url")"
    need_build pngquant "$tag" pngquant || return 0
    ensure_repo "$WORK/pngquant" "$url" "$tag"
    git -C "$WORK/pngquant" submodule update --init --recursive
    cd "$WORK/pngquant"

    # pngquant 3.x is a Rust project
    cargo build --release -j"$JOBS"
    cp target/release/pngquant "$OUT/pngquant"
    chmod +x "$OUT/pngquant"
    cp COPYRIGHT "$OUT/LICENSE-pngquant"
    record_version pngquant "$tag"
}

# ---------------------------------------------------------------------------
# libwebp (cwebp)
# ---------------------------------------------------------------------------
build_webp() {
    local url=https://github.com/webmproject/libwebp.git
    local tag; tag="$(latest_git_tag "$url")"
    need_build webp "$tag" cwebp || return 0
    ensure_repo "$WORK/libwebp" "$url" "$tag"
    cd "$WORK/libwebp"

    cmake -E remove_directory build
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
    record_version webp "$tag"
}

# ---------------------------------------------------------------------------
# libavif (avifenc avifdec)
# ---------------------------------------------------------------------------
build_avif() {
    local url=https://github.com/AOMediaCodec/libavif.git
    local tag; tag="$(latest_git_tag "$url")"
    need_build avif "$tag" avifenc || return 0
    ensure_repo "$WORK/libavif" "$url" "$tag"
    cd "$WORK/libavif"

    cmake -E remove_directory build
    cmake -B build -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX="$PREFIX" \
        -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
        -DBUILD_SHARED_LIBS=OFF \
        -DAVIF_BUILD_APPS=ON \
        -DAVIF_BUILD_TESTS=OFF \
        -DAVIF_CODEC_AOM=SYSTEM \
        -DAVIF_CODEC_DAV1D=SYSTEM \
        -DAVIF_LIBYUV=OFF \
        -DAVIF_JPEG=SYSTEM \
        -DAVIF_PNG=SYSTEM \
        -DAVIF_ZLIBPNG=SYSTEM \
        -DAVIF_ENABLE_WERROR=OFF
    cmake --build build -j"$JOBS"
    cmake --install build

    for tool in avifenc avifdec; do
        cp "$PREFIX/bin/$tool" "$OUT/$tool"
        chmod +x "$OUT/$tool"
    done
    cp LICENSE "$OUT/LICENSE-avif"
    record_version avif "$tag"
}

# ---------------------------------------------------------------------------
# gifsicle
# ---------------------------------------------------------------------------
build_gifsicle() {
    local url=https://github.com/kohler/gifsicle.git
    local tag; tag="$(latest_git_tag "$url")"
    need_build gifsicle "$tag" gifsicle || return 0
    ensure_repo "$WORK/gifsicle" "$url" "$tag"
    cd "$WORK/gifsicle"

    ./bootstrap.sh
    ./configure --prefix="$PREFIX" --disable-shared --enable-static
    make -j"$JOBS"
    make install

    cp "$PREFIX/bin/gifsicle" "$OUT/gifsicle"
    chmod +x "$OUT/gifsicle"
    cp COPYING "$OUT/LICENSE-gifsicle"
    record_version gifsicle "$tag"
}

# ---------------------------------------------------------------------------
# node + svgo
# Svgo is a Node tool: bundle a static node runtime with the npm package.
# ---------------------------------------------------------------------------
installed_node_version() {
    "$OUT/node" --version 2>/dev/null || true
}

installed_svgo_version() {
    python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' \
        "$OUT/svgo-dist/node_modules/svgo/package.json" 2>/dev/null || true
}

build_svgo() {
    local node_ver svgo_ver
    node_ver="$(latest_node_version)"
    svgo_ver="$(latest_svgo_version)"
    local node_current=0 svgo_current=0
    if [[ "$(installed_node_version)" == "$node_ver" ]]; then
        node_current=1
    fi
    if [[ "$(installed_svgo_version)" == "$svgo_ver" ]]; then
        svgo_current=1
    fi

    if [[ "$FORCE" -eq 0 && "$node_current" -eq 1 && "$svgo_current" -eq 1 ]]; then
        log "svgo: already up to date (node $node_ver, svgo $svgo_ver), skipping"
        return 0
    fi

    if [[ "$node_current" -eq 0 ]]; then
        log "svgo: downloading node $node_ver"
        curl -fsSLo "$WORK/node-$node_ver.tar.xz" \
            "https://nodejs.org/dist/$node_ver/node-$node_ver-linux-x64.tar.xz"
        rm -rf "$WORK/node"
        mkdir -p "$WORK/node"
        tar -xJf "$WORK/node-$node_ver.tar.xz" -C "$WORK/node" --strip-components=1
    fi

    cp "$WORK/node/bin/node" "$OUT/node"
    chmod +x "$OUT/node"

    if [[ "$node_current" -eq 0 || "$svgo_current" -eq 0 ]]; then
        log "svgo: installing svgo $svgo_ver"
        rm -rf "$OUT/svgo-dist"
        "$WORK/node/bin/npm" install --prefix "$OUT/svgo-dist" "svgo@$svgo_ver" --no-audit --no-fund
    fi

    cat > "$OUT/svgo" <<'EOF'
#!/bin/sh
DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
exec "$DIR/node" "$DIR/svgo-dist/node_modules/svgo/bin/svgo" "$@"
EOF
    chmod +x "$OUT/svgo"
    cp "$OUT/svgo-dist/node_modules/svgo/LICENSE" "$OUT/LICENSE-svgo"
    log "svgo: done (node $node_ver, svgo $svgo_ver)"
}

main() {
    local groups=()
    for arg in "$@"; do
        case "$arg" in
            --force|-f) FORCE=1 ;;
            *) groups+=("$arg") ;;
        esac
    done
    [[ ${#groups[@]} -eq 0 ]] && groups=(libjxl jpegli mozjpeg oxipng pngquant webp avif gifsicle svgo)

    install_deps
    for group in "${groups[@]}"; do
        log "checking $group"
        ( "build_$group" )
    done
    log "done — tools up to date in $OUT"
}

main "$@"
