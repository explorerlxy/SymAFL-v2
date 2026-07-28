#!/usr/bin/env bash
# Build Z3 (>=4.8.15, required by symsan string theory APIs) into third_party/z3
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TP="$ROOT/third_party"
Z3_VER="${Z3_VER:-z3-4.13.4}"

mkdir -p "$TP"
if [ ! -d "$TP/z3-src" ]; then
  curl -sL -o "$TP/z3.tar.gz" \
    "https://gh-proxy.com/https://github.com/Z3Prover/z3/archive/refs/tags/$Z3_VER.tar.gz"
  tar -C "$TP" xzf "$TP/z3.tar.gz"
  mv "$TP/z3-$Z3_VER" "$TP/z3-src"
  rm "$TP/z3.tar.gz"
fi
cd "$TP/z3-src"
[ -d build ] || python3 scripts/mk_make.py --prefix="$TP/z3"
make -C build -j"${JOBS:-$(nproc)}"
make -C build install
"$TP/z3/bin/z3" --version
