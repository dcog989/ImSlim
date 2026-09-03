#!/usr/bin/env bash
# Builds the bundled compression tools for linux-x86_64, pinned to the
# versions recorded in tools.lock (committed) so release builds are
# reproducible. Use --update to refresh tools.lock against the latest
# available versions; --check reports when a locked tool has a newer
# version (exits 1 if any are behind).
#
# Incremental: a tool is only rebuilt when the pinned version differs from
# the one recorded in $WORK/.versions, or when its output is missing.
#
# Output: src/imslim/bin/linux-x86_64/  (each tool plus its LICENSE)
#
# Run from the repository root:
#   ./scripts/build_tools.sh            # builds the tools.lock-pinned versions
#   ./scripts/build_tools.sh libjxl     # builds a single tool group
#   ./scripts/build_tools.sh --update   # resolve latest versions, refresh tools.lock
#   ./scripts/build_tools.sh --check    # exit 1 if a locked tool is behind latest
#   ./scripts/build_tools.sh --force    # rebuild everything regardless
#   ./scripts/build_tools.sh --no-deps   # skip the apt dependency install (CI already installs them)
#
# Tools / sources:
#   libjxl  (cjxl djxl)                   -> pinned release tag
#   jpegli  (cjpegli djpegli)             -> pinned main commit (no releases)
#   mozjpeg (jpegtran)                    -> pinned release tag
#   oxipng                                -> pinned release tag
#   pngquant                              -> pinned release tag
#   libwebp (cwebp)                       -> pinned release tag
#   libavif (avifenc avifdec)             -> pinned release tag
#   gifsicle                              -> pinned release tag
#   node + svgo                           -> pinned node, pinned svgo
#
# Shared static dependencies (built into $PREFIX, linked into the tools so the
# bundled binaries are self-contained and do not depend on distro packages):
#   zlib                                  -> pinned release tag
#   libpng                                -> pinned release tag
#   lcms2                                 -> pinned release tag

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/src/imslim/bin/linux-x86_64"
WORK="$ROOT/.build"
JOBS="${JOBS:-$(nproc)}"
PREFIX="$WORK/prefix"
VERSIONS="$WORK/.versions"
LOCK="$ROOT/tools.lock"
CONFIG_HASH_FILE="$WORK/.config-hash"
FORCE=0
UPDATE_LOCK=0
CHECK=0
NO_DEPS=0

# Hash the build script's configuration so changing build flags invalidates the
# incremental-build cache even when pinned versions are unchanged. Hashing the
# whole script is coarse but correct: any build-affecting edit forces a rebuild.
script_config_hash() {
    # $BASH_SOURCE may be relative; hash the canonical path so the result is
    # independent of the current directory (build steps cd into $WORK).
    sha256sum "$ROOT/scripts/build_tools.sh" | awk '{print $1}'
}

mkdir -p "$OUT" "$WORK" "$PREFIX"

log() { printf '\033[1;36m[build]\033[0m %s\n' "$*"; }

install_deps() {
    local pkg_manager=""
    if command -v apt-get >/dev/null 2>&1; then
        pkg_manager="apt-get"
    elif command -v pacman >/dev/null 2>&1; then
        pkg_manager="pacman"
    fi
    if [[ -z "$pkg_manager" ]]; then
        log "no supported package manager found (apt-get or pacman); skipping dependency install"
        return
    fi

    # Elevate when sudo is available, otherwise run directly (e.g. as root).
    local pm="$pkg_manager"
    if [[ "$(id -u)" -ne 0 ]] && command -v sudo >/dev/null 2>&1; then
        pm="sudo $pkg_manager"
    fi

    if [[ "$pkg_manager" == "apt-get" ]]; then
        $pm update -qq
        $pm install -y -qq \
            build-essential cmake ninja-build pkg-config curl git \
            autoconf automake libtool nasm
    else
        # Arch-based (e.g. CachyOS): --needed skips already-installed packages.
        # No -Sy: partial upgrades are discouraged; assume repos are current.
        local deps=(
            base-devel cmake ninja pkgconf curl git rust \
            autoconf automake libtool nasm
        )
        $pm -S --needed --noconfirm "${deps[@]}"
    fi
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
        | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["version"])'
}

latest_svgo_version() {
    curl -fsSL https://registry.npmjs.org/svgo/latest \
        | python3 -c 'import json,sys; print(json.load(sys.stdin)["version"])'
}

# ---------------------------------------------------------------------------
# Lock file (tools.lock) bookkeeping
# ---------------------------------------------------------------------------

locked_version() {
    awk -v t="$1" '$1 == t { print $2 }' "$LOCK" 2>/dev/null | tail -n 1
}

latest_version() {
    case "$1" in
        libjxl)   latest_git_tag "https://github.com/libjxl/libjxl.git" ;;
        jpegli)   latest_git_commit "https://github.com/google/jpegli.git" main ;;
        mozjpeg)  latest_git_tag "https://github.com/mozilla/mozjpeg.git" ;;
        oxipng)   latest_git_tag "https://github.com/shssoichiro/oxipng.git" ;;
        pngquant) latest_git_tag "https://github.com/kornelski/pngquant.git" ;;
        webp)     latest_git_tag "https://github.com/webmproject/libwebp.git" ;;
        avif)     latest_git_tag "https://github.com/AOMediaCodec/libavif.git" ;;
        gifsicle) latest_git_tag "https://github.com/kohler/gifsicle.git" ;;
        node)     latest_node_version ;;
        svgo)     latest_svgo_version ;;
        zlib)     latest_git_tag "https://github.com/madler/zlib.git" ;;
        libpng)   latest_git_tag "https://github.com/pnggroup/libpng.git" ;;
        lcms2)    latest_lcms2_version ;;
    esac
}

# Little CMS tags its releases as e.g. lcms2.19.1 (no 'v' prefix), which the
# generic tag matcher rejects; resolve those directly.
latest_lcms2_version() {
    git ls-remote --tags --refs "https://github.com/mm2/Little-CMS.git" \
        | sed 's#.*refs/tags/##' \
        | grep -E '^lcms2\.[0-9]+(\.[0-9]+)?$' \
        | sed 's/^lcms2\./2./' \
        | sort -V \
        | tail -n 1 \
        | sed 's/^2\./lcms2./'
}

# Version to build: the locked one when present (reproducible release
# builds), unless --update requests the latest available.
target_version() {
    local tool="$1"
    if [[ "$UPDATE_LOCK" -eq 1 ]]; then
        latest_version "$tool"
        return
    fi
    local locked; locked="$(locked_version "$tool")"
    if [[ -n "$locked" ]]; then
        echo "$locked"
    else
        latest_version "$tool"
    fi
}

check_lock() {
    local tool latest locked stale=0
    for tool in zlib libpng lcms2 libjxl jpegli mozjpeg oxipng pngquant webp avif gifsicle node svgo; do
        latest="$(latest_version "$tool")"
        locked="$(locked_version "$tool")"
        if [[ -z "$locked" ]]; then
            log "$tool: not locked (latest $latest)"
            stale=1
        elif [[ "$locked" != "$latest" ]]; then
            log "$tool: locked $locked, latest $latest"
            stale=1
        fi
    done
    if [[ "$stale" -eq 0 ]]; then
        log "tools.lock is up to date"
    fi
    return "$stale"
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
    local artifact="$primary"
    [[ "$primary" != /* ]] && artifact="$OUT/$primary"
    if [[ "$FORCE" -eq 1 ]]; then
        log "$tool: --force set, rebuilding"
        return 0
    fi
    if [[ "$(recorded_version "$tool")" == "$version" && -f "$artifact" ]]; then
        if [[ "$(cat "$CONFIG_HASH_FILE" 2>/dev/null)" == "$(script_config_hash)" ]]; then
            log "$tool: already up to date ($version), skipping"
            return 1
        fi
        log "$tool: build config changed, rebuilding"
        return 0
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

ensure_commit() {
    local dir="$1" url="$2" ref="$3"
    if [[ -d "$dir/.git" ]]; then
        git -C "$dir" fetch -q --force origin "$ref" --depth 1
    else
        git init -q "$dir"
        git -C "$dir" remote add origin "$url"
        git -C "$dir" fetch -q --force origin "$ref" --depth 1
    fi
    git -C "$dir" checkout -q "$ref"
}

# ---------------------------------------------------------------------------
# Shared static dependencies
# Built from source into $PREFIX so the bundled tools link them statically and
# do not depend on distro-provided shared libraries at runtime.
# ---------------------------------------------------------------------------

build_zlib() {
    local url=https://github.com/madler/zlib.git
    local tag; tag="$(target_version zlib)"
    need_build zlib "$tag" "$PREFIX/lib/libz.a" || return 0
    ensure_repo "$WORK/zlib" "$url" "$tag"
    cd "$WORK/zlib"

    cmake -E remove_directory build
    cmake -B build -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX="$PREFIX" \
        -DBUILD_SHARED_LIBS=OFF \
        -DZLIB_BUILD_SHARED=OFF \
        -DZLIB_BUILD_STATIC=ON \
        -DZLIB_BUILD_TESTING=OFF
    cmake --build build -j"$JOBS"
    cmake --install build

    record_version zlib "$tag"
}

build_libpng() {
    local url=https://github.com/pnggroup/libpng.git
    local tag; tag="$(target_version libpng)"
    need_build libpng "$tag" "$PREFIX/lib/libpng16.a" || return 0
    ensure_repo "$WORK/libpng" "$url" "$tag"
    cd "$WORK/libpng"

    cmake -E remove_directory build
    cmake -B build -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX="$PREFIX" \
        -DCMAKE_PREFIX_PATH="$PREFIX" \
        -DPNG_SHARED=OFF \
        -DPNG_STATIC=ON \
        -DPNG_TESTS=OFF \
        -DPNG_TOOLS=OFF
    cmake --build build -j"$JOBS"
    cmake --install build

    record_version libpng "$tag"
}

build_lcms2() {
    local url=https://github.com/mm2/Little-CMS.git
    local tag; tag="$(target_version lcms2)"
    need_build lcms2 "$tag" "$PREFIX/lib/liblcms2.a" || return 0
    ensure_repo "$WORK/lcms2" "$url" "$tag"
    cd "$WORK/lcms2"

    ./autogen.sh
    # Only the core color library is needed; disable the optional JPEG/TIFF
    # plugins so the build stays self-contained.
    ./configure --prefix="$PREFIX" --disable-shared --enable-static \
        --without-jpeg --without-tiff
    make -j"$JOBS"
    make install

    record_version lcms2 "$tag"
}

# ---------------------------------------------------------------------------
# libjxl (cjxl djxl)
# ---------------------------------------------------------------------------
build_libjxl() {
    local url=https://github.com/libjxl/libjxl.git
    local tag; tag="$(target_version libjxl)"
    need_build libjxl "$tag" cjxl || return 0
    ensure_repo "$WORK/libjxl" "$url" "$tag"
    cd "$WORK/libjxl"
    ./deps.sh

    # Reconfig from scratch: stale CMake caches (e.g. after flag changes)
    # otherwise leak old linker flags into the build.
    # Install into a private prefix so libjxl's bundled deps (zlib 1.3.1,
    # brotli, hwy) do not clobber the shared $PREFIX zlib/libpng/lcms2 that
    # pngquant and cwebp link against.
    cmake -E remove_directory build
    cmake -E remove_directory "$WORK/install-libjxl"
    cmake -B build -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX="$WORK/install-libjxl" \
        -DBUILD_SHARED_LIBS=OFF \
        -DBUILD_TESTING=OFF \
        -DJPEGXL_ENABLE_TOOLS=ON \
        -DJPEGXL_ENABLE_DEVTOOLS=OFF \
        -DJPEGXL_ENABLE_BENCHMARK=OFF \
        -DJPEGXL_ENABLE_EXAMPLES=OFF \
        -DJPEGXL_ENABLE_DOXYGEN=OFF \
        -DJPEGXL_ENABLE_MANPAGES=OFF \
        -DJPEGXL_ENABLE_PLUGINS=OFF \
        -DJPEGXL_ENABLE_SJPEG=OFF \
        -DJPEGXL_ENABLE_VIEWERS=OFF \
        -DJPEGXL_ENABLE_OPENEXR=OFF \
        -DJPEGXL_ENABLE_TCMALLOC=OFF \
        -DJPEGXL_BUNDLE_LIBPNG=ON \
        -DJPEGXL_FORCE_SYSTEM_BROTLI=OFF \
        -DJPEGXL_FORCE_SYSTEM_HWY=OFF \
        -DJPEGXL_FORCE_SYSTEM_LCMS2=OFF \
        -DCMAKE_DISABLE_FIND_PACKAGE_JPEG=TRUE \
        -DCMAKE_DISABLE_FIND_PACKAGE_GIF=TRUE
    cmake --build build -j"$JOBS"
    cmake --install build

    cp "$WORK/install-libjxl/bin/cjxl" "$OUT/cjxl"
    cp "$WORK/install-libjxl/bin/djxl" "$OUT/djxl"
    chmod +x "$OUT/cjxl" "$OUT/djxl"
    cp LICENSE "$OUT/LICENSE-libjxl"
    record_version libjxl "$tag"
}

# ---------------------------------------------------------------------------
# jpegli (cjpegli djpegli)
# jpegli has no releases; the lock pins a main commit.
# ---------------------------------------------------------------------------
build_jpegli() {
    local url=https://github.com/google/jpegli.git
    local commit; commit="$(target_version jpegli)"
    need_build jpegli "$commit" cjpegli || return 0
    ensure_commit "$WORK/jpegli" "$url" "$commit"
    cd "$WORK/jpegli"
    ./deps.sh

    # Reconfig from scratch: stale CMake caches (e.g. after flag changes)
    # otherwise leak old linker flags into the build.
    # Install into a private prefix so jpegli's bundled deps (zlib 1.3.1,
    # hwy) do not clobber the shared $PREFIX zlib/libpng/lcms2 that pngquant
    # and cwebp link against.
    cmake -E remove_directory build
    cmake -E remove_directory "$WORK/install-jpegli"
    cmake -B build -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX="$WORK/install-jpegli" \
        -DBUILD_SHARED_LIBS=OFF \
        -DBUILD_TESTING=OFF \
        -DJPEGLI_ENABLE_TOOLS=ON \
        -DJPEGLI_ENABLE_DEVTOOLS=OFF \
        -DJPEGLI_ENABLE_BENCHMARK=OFF \
        -DJPEGLI_ENABLE_DOXYGEN=OFF \
        -DJPEGLI_ENABLE_MANPAGES=OFF \
        -DJPEGLI_ENABLE_OPENEXR=OFF \
        -DJPEGLI_ENABLE_JPEGLI_LIBJPEG=OFF \
        -DJPEGLI_BUNDLE_LIBPNG=ON \
        -DJPEGLI_FORCE_SYSTEM_HWY=OFF \
        -DJPEGLI_FORCE_SYSTEM_LCMS2=OFF \
        -DCMAKE_DISABLE_FIND_PACKAGE_JPEG=TRUE \
        -DCMAKE_DISABLE_FIND_PACKAGE_GIF=TRUE
    cmake --build build -j"$JOBS"
    cmake --install build

    for tool in cjpegli djpegli; do
        cp "$WORK/install-jpegli/bin/$tool" "$OUT/$tool"
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
    local tag; tag="$(target_version mozjpeg)"
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
    local tag; tag="$(target_version oxipng)"
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
    # pngquant statically links libpng, lcms2 and zlib from $PREFIX.
    build_zlib
    build_libpng
    build_lcms2
    local url=https://github.com/kornelski/pngquant.git
    local tag; tag="$(target_version pngquant)"
    need_build pngquant "$tag" pngquant || return 0
    ensure_repo "$WORK/pngquant" "$url" "$tag"
    git -C "$WORK/pngquant" submodule update --init --recursive
    cd "$WORK/pngquant"

    # pngquant 3.x is a Rust project; statically link the bundled libpng,
    # lcms2 and zlib (via pkg-config) so the binary is self-contained.
    PKG_CONFIG_PATH="$PREFIX/lib/pkgconfig" \
        cargo build --release -j"$JOBS" --features "static z-static"
    cp target/release/pngquant "$OUT/pngquant"
    chmod +x "$OUT/pngquant"
    cp COPYRIGHT "$OUT/LICENSE-pngquant"
    record_version pngquant "$tag"
}

# ---------------------------------------------------------------------------
# libwebp (cwebp)
# ---------------------------------------------------------------------------
build_webp() {
    # cwebp reads PNG input, so its static libpng/zlib must be built first.
    build_zlib
    build_libpng
    local url=https://github.com/webmproject/libwebp.git
    local tag; tag="$(target_version webp)"
    need_build webp "$tag" cwebp || return 0
    ensure_repo "$WORK/libwebp" "$url" "$tag"
    cd "$WORK/libwebp"

    cmake -E remove_directory build
    cmake -B build -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX="$PREFIX" \
        -DCMAKE_PREFIX_PATH="$PREFIX" \
        -DBUILD_SHARED_LIBS=OFF \
        -DWEBP_LINK_STATIC=ON \
        -DWEBP_BUILD_CWEBP=ON \
        -DWEBP_BUILD_DWEBP=OFF \
        -DWEBP_BUILD_ANIM_UTILS=OFF \
        -DWEBP_BUILD_GIF2WEBP=OFF \
        -DWEBP_BUILD_IMG2WEBP=OFF \
        -DWEBP_BUILD_VWEBP=OFF \
        -DWEBP_BUILD_WEBPINFO=OFF \
        -DCMAKE_DISABLE_FIND_PACKAGE_JPEG=TRUE \
        -DCMAKE_DISABLE_FIND_PACKAGE_GIF=TRUE
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
    local tag; tag="$(target_version avif)"
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
        -DAVIF_CODEC_AOM=LOCAL \
        -DAVIF_CODEC_DAV1D=OFF \
        -DAVIF_LIBYUV=OFF \
        -DAVIF_JPEG=LOCAL \
        -DAVIF_ZLIBPNG=LOCAL \
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
    local tag; tag="$(target_version gifsicle)"
    need_build gifsicle "$tag" gifsicle || return 0
    ensure_repo "$WORK/gifsicle" "$url" "$tag"
    cd "$WORK/gifsicle"

    ./bootstrap.sh
    # gifsicle is a standalone program, not a libtool library; the shared
    # library flags used for the other deps are unrecognized here.
    ./configure --prefix="$PREFIX"
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
    node_ver="$(target_version node)"
    svgo_ver="$(target_version svgo)"
    local node_current=0 svgo_current=0
    if [[ "$(installed_node_version)" == "$node_ver" ]]; then
        node_current=1
    fi
    if [[ "$(installed_svgo_version)" == "$svgo_ver" ]]; then
        svgo_current=1
    fi

    if [[ "$FORCE" -eq 0 && "$node_current" -eq 1 && "$svgo_current" -eq 1 ]]; then
        log "svgo: already up to date (node $node_ver, svgo $svgo_ver), skipping"
        record_version node "$node_ver"
        record_version svgo "$svgo_ver"
        return 0
    fi

    # npm install below needs the full extracted node tree, not just the
    # binary copied out to $OUT/node — a restored bin-output cache (e.g. CI,
    # which caches src/imslim/bin/linux-x86_64 but not .build/node) can leave
    # $OUT/node current while $WORK/node is missing, so check for the
    # extraction directly rather than trusting node_current alone.
    if [[ "$node_current" -eq 0 || ! -x "$WORK/node/bin/node" ]]; then
        log "svgo: downloading node $node_ver"
        curl -fsSLo "$WORK/node-$node_ver.tar.xz" \
            "https://nodejs.org/dist/$node_ver/node-$node_ver-linux-x64.tar.xz"
        # Verify against the checksums nodejs publishes for that release;
        # fail loudly on a corrupt or tampered download.
        local expected
        expected="$(curl -fsSL "https://nodejs.org/dist/$node_ver/SHASUMS256.txt" \
            | awk -v f="node-$node_ver-linux-x64.tar.xz" '$2 == f { print $1 }')"
        echo "$expected  $WORK/node-$node_ver.tar.xz" | sha256sum -c --quiet \
            || { log "node $node_ver tarball sha256 mismatch"; exit 1; }
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
    record_version node "$node_ver"
    record_version svgo "$svgo_ver"
    log "svgo: done (node $node_ver, svgo $svgo_ver)"
}

main() {
    local groups=()
    for arg in "$@"; do
        case "$arg" in
            --force|-f) FORCE=1 ;;
            --update|-u) UPDATE_LOCK=1 ;;
            --check|-c) CHECK=1 ;;
            --no-deps|-n) NO_DEPS=1 ;;
            *) groups+=("$arg") ;;
        esac
    done

    if [[ "$CHECK" -eq 1 ]]; then
        check_lock
        exit $?
    fi

    [[ ${#groups[@]} -eq 0 ]] && groups=(zlib libpng lcms2 libjxl jpegli mozjpeg oxipng pngquant webp avif gifsicle svgo)

    # Seed the config hash on a fresh checkout so shared deps built more than
    # once in a single run (e.g. zlib for pngquant and cwebp) compare against
    # the current script instead of a missing file and rebuild needlessly.
    if [[ ! -s "$CONFIG_HASH_FILE" ]]; then
        script_config_hash > "$CONFIG_HASH_FILE"
    fi

    if [[ "$NO_DEPS" -eq 0 ]]; then
        install_deps
    fi
    for group in "${groups[@]}"; do
        log "checking $group"
        ( "build_$group" )
    done
    script_config_hash > "$CONFIG_HASH_FILE"

    if [[ "$UPDATE_LOCK" -eq 1 ]]; then
        cp "$VERSIONS" "$LOCK"
        log "tools.lock refreshed"
    fi
    log "done — tools up to date in $OUT"
}

main "$@"