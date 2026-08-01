#!/usr/bin/env bash
# Build paired concrete and concolic XZ targets for the v2 PCBT benchmark.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AFLPP="$ROOT/AFLplusplus"
SYMSAN_BIN="$ROOT/symsan/build/bin"
XZ_SOURCE="${XZ_SOURCE:-/media/hahafish/Data/ForUbuntu/test/Realworld/xz/src}"
BUILD_ROOT="${BUILD_ROOT:-/tmp/symafl-v2-realworld-build}"
TARGET_ROOT="$BUILD_ROOT/xz"
CLEAN=0

usage() {
  cat <<EOF
usage: $0 [--clean]

Builds these executables outside the checkout:
  $TARGET_ROOT/concolic/xz
  $TARGET_ROOT/concrete/xz

Override XZ_SOURCE or BUILD_ROOT to use a different local source/build root.
--clean removes an existing $TARGET_ROOT before rebuilding.
EOF
}

while (($#)); do
  case "$1" in
    --clean) CLEAN=1 ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
  shift
done

fail() { printf 'build-xz-benchmark: %s\n' "$*" >&2; exit 1; }
need_file() { [[ -f "$1" ]] || fail "missing file: $1"; }
need_exec() { [[ -x "$1" ]] || fail "missing executable: $1"; }
need_cmd() { command -v "$1" >/dev/null || fail "missing command: $1"; }

need_file "$XZ_SOURCE/CMakeLists.txt"
need_file "$ROOT/tests/targets/xz_target.c"
need_file "$ROOT/tests/afl_init_shim.c"
need_file "$AFLPP/afl-compiler-rt.o"
need_exec "$AFLPP/afl-clang-fast"
need_exec "$SYMSAN_BIN/ko-clang"
need_cmd clang-18
need_cmd cmake
need_cmd ninja

if [[ -e "$TARGET_ROOT" ]]; then
  (( CLEAN )) || fail "build directory exists: $TARGET_ROOT (pass --clean to replace it)"
  rm -rf "$TARGET_ROOT"
fi

mkdir -p "$TARGET_ROOT"/{concolic,concrete}

configure_and_build() {
  local kind="$1"
  local compiler="$2"
  local build_dir="$TARGET_ROOT/$kind/lib"
  # Concolic uses -O0 to reduce TaintPass vectorization crashes in liblzma.
  # SHA256 is disabled: SymSan TaintPass currently crashes on xz's sha256.c.
  local cflags="-g"
  local extra_cmake=()
  if [[ "$kind" == concolic ]]; then
    cflags+=" -O0 -fno-vectorize -fno-slp-vectorize"
    cflags+=" -fsanitize-coverage=trace-pc-guard -fno-sanitize-link-runtime"
  else
    cflags+=" -O1"
  fi
  extra_cmake+=(-DADDITIONAL_CHECK_TYPES=crc64)

  cmake -S "$XZ_SOURCE" -B "$build_dir" -G Ninja \
    -DCMAKE_C_COMPILER="$compiler" \
    -DCMAKE_C_FLAGS="$cflags" \
    -DCMAKE_TRY_COMPILE_TARGET_TYPE=STATIC_LIBRARY \
    -DCMAKE_C_BYTE_ORDER=LITTLE_ENDIAN \
    -DBUILD_SHARED_LIBS=OFF \
    -DENABLE_SMALL=ON -DALLOW_CLMUL_CRC=OFF \
    "${extra_cmake[@]}"
  ninja -C "$build_dir" liblzma
}

printf '[xz-build] configuring concolic liblzma\n'
KO_CC=clang-18 KO_CXX=clang++-18 KO_USE_FASTGEN=1 \
  configure_and_build concolic "$SYMSAN_BIN/ko-clang"
printf '[xz-build] configuring concrete liblzma\n'
configure_and_build concrete "$AFLPP/afl-clang-fast"

find_liblzma() {
  local dir="$1" lib
  lib="$(find "$dir" -name liblzma.a -type f -print -quit)"
  [[ -n "$lib" ]] || fail "liblzma.a not produced below $dir"
  printf '%s\n' "$lib"
}

CONCOLIC_LIB="$(find_liblzma "$TARGET_ROOT/concolic/lib")"
CONCRETE_LIB="$(find_liblzma "$TARGET_ROOT/concrete/lib")"
SHIM="$TARGET_ROOT/concolic/afl-init-shim.o"
clang-18 -c "$ROOT/tests/afl_init_shim.c" -o "$SHIM"

INCLUDE=(-I"$XZ_SOURCE/src/liblzma/api")
printf '[xz-build] linking concolic target\n'
KO_CC=clang-18 KO_CXX=clang++-18 KO_USE_FASTGEN=1 \
  "$SYMSAN_BIN/ko-clang" -O1 -g -fno-sanitize-link-runtime \
  -fsanitize-coverage=trace-pc-guard "${INCLUDE[@]}" \
  "$ROOT/tests/targets/xz_target.c" "$CONCOLIC_LIB" \
  "$AFLPP/afl-compiler-rt.o" "$SHIM" -lpthread -ldl \
  -o "$TARGET_ROOT/concolic/xz"
printf '[xz-build] linking concrete target\n'
"$AFLPP/afl-clang-fast" -O1 -g "${INCLUDE[@]}" \
  "$ROOT/tests/targets/xz_target.c" "$CONCRETE_LIB" -lpthread -ldl \
  -o "$TARGET_ROOT/concrete/xz"

printf 'concolic=%s\nconcrete=%s\nsource=%s\n' \
  "$TARGET_ROOT/concolic/xz" "$TARGET_ROOT/concrete/xz" "$XZ_SOURCE"
