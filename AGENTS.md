# Repository Guidelines

## Project Structure & Module Organization

This superproject combines two Git submodules. `AFLplusplus/` is upstream AFL++
v4.31c and must remain **zero-patch**; integrate behavior through its public
custom-mutator API instead. `symsan/` is the active development tree. Its main
components are `driver/aflpp/` (mutator, PCBT, and predicate evaluation),
`runtime/dfsan/` (taint runtime), `instrumentation/` (LLVM passes), and
`solvers/jigsaw/` (JIT predicate evaluation only). Read `docs/DESIGN_V2.md`
before changing the architecture.

Top-level `tests/` holds smoke and real-target harnesses, seeds, and
`trace_check.py`; `symsan/tests/` contains LLVM lit regression cases. Put
automation in `scripts/` and design or operational notes in `docs/`.

## Build, Test, and Development Commands

Use the pinned LLVM toolchain (`clang-18`/`clang++-18`). Build Z3 once, then
build both components:

```bash
scripts/build-z3.sh
scripts/build-all.sh             # AFL++ then SymSan
scripts/build-all.sh symsan      # rebuild/configure SymSan only
python3 tests/trace_check.py direct
python3 tests/trace_check.py afl
scripts/run-fuzz.sh single-taint # 120-second forkserver smoke run
```

The trace checks must report `PASS` and non-zero symbolic labels. For extended
evaluation, use `scripts/eval-xz.sh [afl|noscreen|screen|all]`. Keep fuzzing
outputs under `/tmp` (an ext4 filesystem), not the repository drive.

## Coding Style & Naming Conventions

Follow the surrounding file's style. C and C++ use two-space indentation,
braces on the declaration line, and `//` comments; C++ types are `PascalCase`,
methods use `PascalCase`, and functions/variables generally use `snake_case`
or established API names. Preserve the existing `pcbt` namespace and concise
invariant comments. Shell scripts use Bash, `set -euo pipefail`, uppercase
environment variables, and lowercase local variables. Python follows standard
four-space indentation. No repository-wide formatter or linter is configured.

## Testing Guidelines

Add focused C/C++ regressions to `symsan/tests/` using descriptive names such
as `bounds.c` or `fp_rounding.c`; add target-level fixtures under `tests/`.
Exercise both direct tracing and AFL forkserver paths when changing tainting,
event streams, or the mutator. Deterministic targets are required: conflicting
traces are intentionally discarded by PCBT.

## Commit & Pull Request Guidelines

Use short, imperative, scoped subjects consistent with history, for example
`tests: add predicate interpreter microbenchmark` or `v2: fix trace timeout`.
Keep submodule pointer updates intentional and never include AFL++ source
edits. PRs should explain the behavioral change, identify the affected
verification mode, link any issue, and include relevant command output or
coverage/performance evidence. Include logs or screenshots only when they help
review an observable fuzzing result.
