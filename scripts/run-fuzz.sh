#!/usr/bin/env bash
# SymAFL v2 — run afl-fuzz in one of the verification modes.
# Usage:
#   scripts/run-fuzz.sh baseline   # stock SymSan hybrid fuzzing (two binaries + solvers)
#   scripts/run-fuzz.sh single     # single-binary: ko-clang+sancov+PCGUARD, no mutator (验证 A)
#   scripts/run-fuzz.sh single-taint # same + TAINT_OPTIONS (验证 B)
# Env overrides: FUZZ_SECONDS (default 120), OUT (default /tmp/symafl2-out)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AFLPP="$ROOT/AFLplusplus"
SYMSAN_BUILD="$ROOT/symsan/build"
MODE="${1:?mode: baseline|single|single-taint}"
OUT="${OUT:-/tmp/symafl2-out}"
FUZZ_SECONDS="${FUZZ_SECONDS:-120}"
SEEDS="$ROOT/tests/seeds"

rm -rf "$OUT"; mkdir -p "$OUT"

export AFL_SKIP_BIN_CHECK=1
export AFL_DISABLE_TRIM=1
export AFL_NO_UI=1
export AFL_I_DONT_CARE_ABOUT_MISSING_CRASHES=1
export AFL_MAP_SIZE=65536

AFL_FUZZ=(timeout --preserve-status -s INT "$FUZZ_SECONDS"
          "$AFLPP/afl-fuzz" -i "$SEEDS" -o "$OUT" -m none -t 2000+)

case "$MODE" in
  baseline)
    # stock SymSan: normal binary for fuzzing, tracing binary via SYMSAN_TARGET
    export AFL_CUSTOM_MUTATOR_LIBRARY="$SYMSAN_BUILD/bin/libSymSanMutator.so"
    export SYMSAN_TARGET="$ROOT/tests/toy-trace"
    export SYMSAN_OUTPUT_DIR="$OUT/symsan-tmp"
    export SYMSAN_USE_JIGSAW=1
    export SYMSAN_USE_Z3=1
    mkdir -p "$SYMSAN_OUTPUT_DIR"
    "${AFL_FUZZ[@]}" -- "$ROOT/tests/toy-afl" @@
    ;;
  single)
    # single binary already has afl-compiler-rt linked (forkserver+coverage)
    "${AFL_FUZZ[@]}" -- "$ROOT/tests/toy" @@
    ;;
  single-taint)
    # forkserver children inherit this; AFL++ per-fuzzer input is <out>/default/.cur_input
    export TAINT_OPTIONS="taint_file=$OUT/default/.cur_input:taint_max_len=65536:exit_on_memerror=false"
    "${AFL_FUZZ[@]}" -- "$ROOT/tests/toy" @@
    ;;
  *) echo "unknown mode $MODE" >&2; exit 1;;
esac
