#!/usr/bin/env bash
# Phase 3.2 xz evaluation: 3 configs side by side.
#   ① afl      — stock afl-clang-fast binary, plain AFL++
#   ② noscreen — v2 single concolic binary + mutator, screening off
#   ③ screen   — v2 + mutator, PCBT screening on
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AFLPP="$ROOT/AFLplusplus"
SEEDS="${SEEDS:-/media/hahafish/Data/ForUbuntu/test/Realworld/xz/seeds}"
FUZZ_SECONDS="${FUZZ_SECONDS:-300}"
MUT="$ROOT/symsan/build/bin/libSymSanMutator.so"
XZV2="$ROOT/tests/targets/xz-v2"

run() { # name target_bin extra_env...
  local name="$1"; local bin="$2"; shift 2
  local out="/tmp/eval-xz-$name"
  rm -rf "$out"; mkdir -p "$out/default"
  env AFL_SKIP_BIN_CHECK=1 AFL_DISABLE_TRIM=1 AFL_NO_UI=1 \
      AFL_I_DONT_CARE_ABOUT_MISSING_CRASHES=1 "$@" \
      timeout --preserve-status -s INT "$FUZZ_SECONDS" \
      "$AFLPP/afl-fuzz" -i "$SEEDS" -o "$out" -m none -t 2000+ -- "$bin" @@ \
      > "/tmp/eval-xz-$name.log" 2>&1
}

case "${1:-all}" in
  afl)
    run afl "$ROOT/tests/targets/xz-afl" ;;
  noscreen)
    run noscreen "$XZV2" \
      AFL_CUSTOM_MUTATOR_LIBRARY="$MUT" SYMSAN_TARGET="$XZV2" \
      SYMSAN_OUTPUT_DIR=/tmp/eval-xz-noscreen/symsan SYMSAN_DONT_EXIT_ON_MEMERROR=1 \
      SYMAFL_TRACE_TIMEOUT_MS=60000 SYMAFL_NO_SCREEN=1 ;;
  screen)
    run screen "$XZV2" \
      AFL_CUSTOM_MUTATOR_LIBRARY="$MUT" SYMSAN_TARGET="$XZV2" \
      SYMSAN_OUTPUT_DIR=/tmp/eval-xz-screen/symsan SYMSAN_DONT_EXIT_ON_MEMERROR=1 \
      SYMAFL_TRACE_TIMEOUT_MS=60000 ;;
  all)
    "$0" afl & "$0" noscreen & "$0" screen & wait ;;
  *) echo "usage: $0 [afl|noscreen|screen|all]" >&2; exit 1 ;;
esac
