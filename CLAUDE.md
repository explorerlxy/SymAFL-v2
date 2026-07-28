# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

SymAFL v2: a fuzzer built on stock AFL++ (v4.31c, **zero patches**) plus a fork of SymSan. A custom mutator (`libSymSanMutator.so`) uses a **PCBT** (Path Constraint Binary Tree) to *screen* mutated candidates in-process via the AFL++ `post_process` hook: candidates that cannot reach an unexplored branch frontier are vetoed before execution. There is **no constraint solving** — Jigsaw is used only as a predicate→native-function JIT/eval library. Until the PCBT saturates, every executed candidate is a concolic run (SymSan taint tracking with the event pipe short-circuited, `pipe_fd=-1`, zero serialization).

The authoritative design doc is [docs/DESIGN_V2.md](docs/DESIGN_V2.md) (as-planned/as-built, in Chinese). Consult it before changing architecture.

## Repo layout

- `AFLplusplus/` — submodule, upstream @ v4.31c, must stay **zero-patch** (screening is done purely through the official custom-mutator API).
- `symsan/` — submodule (fork `explorerlxy/SymAFL-Symsan`, branch `v2-dev`), the **development mainline**:
  - `driver/aflpp/symsan.cpp` — AFL++ custom mutator: `init`, `post_process` (veto), `queue_get`/`queue_new_entry` (trace hooks); solver/fuzz chain stripped.
  - `driver/aflpp/pcbt.{hpp,cpp}` — PCBT core: `InsertTrace` (divergence-point insertion from symbolic-branch event streams) and `CheckInput` (frontier screening).
  - `driver/aflpp/pred.{hpp,cpp}` — predicate representation/evaluation (input-byte AST, with JIT via `solvers/jigsaw/jit.cc` reused as codegen only; `gd.cc`/`rgd.cc` not linked).
  - `runtime/dfsan/dfsan_custom.cpp` — taint runtime; contains the forkserver input-label preallocation patch (`taint_max_len`).
  - `solvers/jigsaw/` — kept only for `jit.cc` codegen.
- `tests/` — `toy.c` smoke target (+ prebuilt `toy`, `toy-afl`, `toy-trace`), `seeds/`, `trace_check.py` (verification harness).
- `third_party/z3*` — Z3 built from source (required by symsan string-theory APIs; system libz3 is too old).

## Commands

```bash
scripts/build-z3.sh        # one-time: Z3 into third_party/z3
scripts/build-all.sh       # build AFL++ then symsan (skips already-built; pass 'aflpp' or 'symsan' to rebuild one)
scripts/run-fuzz.sh baseline     # stock SymSan hybrid fuzzing (2 binaries + solvers) — reference mode
scripts/run-fuzz.sh single       # verification A: single ko-clang+sancov binary as forkserver target
scripts/run-fuzz.sh single-taint # verification B: same + TAINT_OPTIONS taint tracking
python3 tests/trace_check.py direct   # verification B harness, direct-exec mode (PASS = symbolic branch events with non-zero labels)
python3 tests/trace_check.py afl      # same, through afl-fuzz -> forkserver -> children
```

Run modes support env overrides: `FUZZ_SECONDS` (default 120), `OUT` (default `/tmp/symafl2-out`).

Rebuild a toy target (single binary = concolic tracing + AFL coverage + forkserver):
```bash
KO_CC=clang-18 KO_CXX=clang++-18 KO_USE_FASTGEN=1 \
  symsan/build/bin/ko-clang -O1 -fsanitize-coverage=trace-pc-guard tests/toy.c -o tests/toy
```

## Key operational facts

- **Fuzzing env always needs** `AFL_DISABLE_TRIM=1` (trim mutates traced entries, invalidating their tree paths) and a fuzz output dir on **ext4** (`/tmp`, not the NTFS repo drive). The repo itself lives on NTFS — submodules have `core.filemode false`; don't fight filemode noise.
- Taint config: `TAINT_OPTIONS="taint_file=<out>/default/.cur_input:taint_max_len=65536:exit_on_memerror=false"`. The forkserver starts before `.cur_input` exists, so `taint_max_len` (preallocated labels) is mandatory, not optional.
- Mutator env: `AFL_CUSTOM_MUTATOR_LIBRARY=symsan/build/bin/libSymSanMutator.so`, `SYMSAN_TARGET=<traced binary>`, `SYMSAN_OUTPUT_DIR=<dir>`; screening toggles: `SYMAFL_NO_SCREEN=1` (disable), `SYMAFL_RCNT_LIMIT=<n>`. Mutator stats are printed by `afl_custom_deinit` on exit (nodes/depth/admitted/vetoed/selfcheck_fail).
- Toolchain is pinned to **clang-18** (Ubuntu 24.04); ko-clang is an LLVM-18 pass.
- Event stream semantics the PCBT relies on: each traced run emits, from program entry, the complete sequence of `pipe_msg{cid,label,result}` for *symbolic* branches only (label≠0), in execution order. Traces are collected by fork+exec'ing the same binary via the launcher (shared union AST table), not from forkserver runs.
- Semantic red line in JIT reuse: `solvers/jigsaw/jit.cc` div-by-zero hack (`select(c==0,1,c)`) diverges from Z3 bitvector semantics; predicate evaluation must follow Z3/SMT-LIB semantics (shifts ≥ width, exact-width masks). Z3 is used only as an offline cross-validator.

## Verification targets (from the design doc)

- Replay consistency ≥ 99% (admitted candidates actually reach predicted frontier; bitmap comparison of first run vs traced replay; mismatched traces are discarded, never inserted).
- Screening latency mean < 100µs/candidate; coverage ≥ 95% of baseline.
- Evaluation targets must be deterministic — non-determinism poisons the tree.
