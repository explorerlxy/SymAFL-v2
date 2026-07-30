#!/usr/bin/env bash
# SymAFL v2 — one-command build: aflpp -> symsan
# Usage: scripts/build-all.sh [aflpp] [symsan]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AFLPP="$ROOT/AFLplusplus"
SYMSAN="$ROOT/symsan"
Z3_PREFIX="$ROOT/third_party/z3"
JOBS="${JOBS:-$(nproc)}"

targets=("$@")
[ ${#targets[@]} -eq 0 ] && targets=(aflpp symsan)

has() { local t="$1"; for x in "${targets[@]}"; do [ "$x" = "$t" ] && return 0; done; return 1; }

if has aflpp; then
  if [ -x "$AFLPP/afl-fuzz" ] && [ -f "$AFLPP/SanitizerCoveragePCGUARD.so" ]; then
    echo "[aflpp] already built, skipping"
  else
    echo "[aflpp] building AFL++ v4.31c ..."
    make -C "$AFLPP" PERFORMANCE=1 NO_NYX=1 \
      LLVM_CONFIG=llvm-config-18 CC=clang-18 CXX=clang++-18 \
      source-only -j"$JOBS"
  fi
fi

if has symsan; then
  if [ ! -f "$Z3_PREFIX/lib/libz3.so" ]; then
    echo "[symsan] ERROR: Z3 >= 4.8.15 not found at $Z3_PREFIX" >&2
    echo "  build it first: scripts/build-z3.sh" >&2
    exit 1
  fi
  echo "[symsan] configuring + building (clang-18) ..."
  mkdir -p "$SYMSAN/build"
  cmake -S "$SYMSAN" -B "$SYMSAN/build" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="$SYMSAN/build" \
    -DAFLPP_PATH="$AFLPP" \
    -DZ3_LIBRARY="$Z3_PREFIX/lib/libz3.so" \
    -DZ3_INCLUDE_DIR="$Z3_PREFIX/include" \
    -DCMAKE_C_COMPILER=clang-18 -DCMAKE_CXX_COMPILER=clang++-18
  make -C "$SYMSAN/build" -j"$JOBS"
  make -C "$SYMSAN/build" install
fi

echo "done."
