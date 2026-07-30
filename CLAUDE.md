# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

SymAFL v2: a fuzzer built on private forks of AFL++ v4.31c and SymSan. The AFL++ fork contains constrained SymAFL scheduling changes for PCBT pipe draining and concolic-to-concrete forkserver switching. A custom mutator (`libSymSanMutator.so`) uses a **PCBT** (Path Constraint Binary Tree) to *screen* mutated candidates in-process via the AFL++ `post_process` hook: candidates that cannot reach an unexplored branch frontier are vetoed before execution. There is **no constraint solving** — the current PCBT evaluates predicates with its local bit-vector interpreter. PCBT mode needs a concolic and a concrete target: until the PCBT saturates, every admitted candidate is a concolic run; then AFL++ retains the queue, rebuilds coverage against the concrete target, and continues as ordinary AFL++.

Authoritative current-behavior documents (read before changing architecture):

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/RUNTIME_PROTOCOL.md](docs/RUNTIME_PROTOCOL.md)
- [docs/PCBT.md](docs/PCBT.md)
- [docs/STATUS.md](docs/STATUS.md)
- [docs/VERIFICATION.md](docs/VERIFICATION.md)

Historical design notes live under [docs/archive/](docs/archive/) and are **not** normative. The repository operating contract is [AGENTS.md](AGENTS.md). Documentation map: [docs/README.md](docs/README.md).

## Repo layout

- `AFLplusplus/` — private submodule (`git@github.com:explorerlxy/SymAFL-AFLplusplus-v2.git`, branch `main`), based on AFL++ v4.31c. Keep its SymAFL changes constrained to scheduling/forkserver integration; PCBT predicates and screening logic belong in `symsan/`.
- `symsan/` — private submodule (`git@github.com:explorerlxy/SymAFL-Symsan.git`, branch `v2-dev`), the **development mainline**:
  - `driver/aflpp/symsan.cpp` — AFL++ custom mutator: `init`, `post_process` (veto), `queue_get`/`queue_new_entry` (trace hooks); solver/fuzz chain stripped.
  - `driver/aflpp/pcbt.{hpp,cpp}` — PCBT core: `InsertTrace` (divergence-point insertion from symbolic-branch event streams) and `CheckInput` (frontier screening).
  - `driver/aflpp/pred.{hpp,cpp}` — predicate representation and SMT-LIB-compatible, ≤64-bit interpreter. Unsupported/wider expressions become opaque and are conservatively admitted.
  - `runtime/dfsan/dfsan_custom.cpp` — taint runtime; contains the forkserver input-label preallocation patch (`taint_max_len`).
  - `backend/solver_common.cpp` — condition-event export and lifecycle transport modes.
  - `solvers/jigsaw/` — retained dependency code; the current mutator does not invoke its JIT or solving path.
- `tests/` — `toy.c` smoke target, seeds, pipe/mode/trace harnesses.
- `scripts/` — build, smoke, and evaluation entrypoints.
- `docs/` — architecture, protocol, verification, status, ADRs, archive.
- `third_party/z3*` — Z3 built from source (required by symsan string-theory APIs; system libz3 is too old).

## Commands

```bash
scripts/build-z3.sh        # one-time: Z3 into third_party/z3
scripts/build-all.sh       # build AFL++ then symsan (skips already-built; pass 'aflpp' or 'symsan' to rebuild one)
scripts/run-fuzz.sh baseline     # ordinary AFL++ on the concrete toy target
scripts/run-fuzz.sh single       # verification A: single ko-clang+sancov binary as forkserver target
scripts/run-fuzz.sh single-taint # verification B: same + TAINT_OPTIONS taint tracking
scripts/run-fuzz.sh pcbt         # PCBT concolic phase + concrete fallback smoke
python3 tests/trace_check.py direct   # symbolic branch events with non-zero labels
python3 tests/trace_check.py afl      # same through afl-fuzz -> forkserver -> children
python3 tests/pcbt_pipe_check.py      # long pipe drain without deadlock
python3 tests/pcbt_toy_modes_check.py # pipe-full -> SHM overflow -> pipe-suffix
```

Run modes support env overrides: `FUZZ_SECONDS` (default 120), `OUT` (default `/tmp/symafl2-out`).

Rebuild both toy targets required by PCBT:
```bash
clang-18 -c tests/afl_init_shim.c -o /tmp/afl-init-shim.o
KO_CC=clang-18 KO_CXX=clang++-18 KO_USE_FASTGEN=1 \
  symsan/build/bin/ko-clang -O1 -fno-sanitize-link-runtime \
  -fsanitize-coverage=trace-pc-guard tests/toy.c AFLplusplus/afl-compiler-rt.o \
  /tmp/afl-init-shim.o -o tests/toy
AFLplusplus/afl-clang-fast -O1 tests/toy.c -o tests/toy-afl
```

## Key operational facts

- **Fuzzing env always needs** `AFL_DISABLE_TRIM=1` (trim mutates traced entries, invalidating their tree paths) and a fuzz output dir on **ext4** (`/tmp`, not the NTFS repo drive). The repo itself lives on NTFS — submodules have `core.filemode false`; don't fight filemode noise.
- Taint config: `TAINT_OPTIONS="taint_file=<out>/default/.cur_input:taint_max_len=65536:exit_on_memerror=false"`. The forkserver starts before `.cur_input` exists, so `taint_max_len` (preallocated labels) is mandatory, not optional.
- Mutator env: `AFL_CUSTOM_MUTATOR_LIBRARY=symsan/build/bin/libSymSanMutator.so`, `SYMAFL_CONCOLIC_TARGET=<traced binary>`, `SYMAFL_CONCRETE_TARGET=<normal AFL binary>`; screening toggles: `SYMAFL_NO_SCREEN=1` (disable), `SYMAFL_RCNT_LIMIT=<n>`. Mutator stats are printed by `afl_custom_deinit` on exit (nodes/depth/admitted/vetoed/selfcheck_fail).
- Toolchain is pinned to **clang-18** (Ubuntu 24.04); ko-clang is an LLVM-18 pass.
- Event stream semantics: each concolic child executes the complete DFSan propagation and label-DAG construction. Bootstrap exports the complete symbolic-condition sequence over pipe; steady state exports only the known-frontier suffix into bounded SHM; an SHM overflow on a coverage-gaining input is rerun as a pipe suffix. `afl-fuzz` drains pipe data while waiting for the target child, and the mutator inserts it after the run; no launcher sidecar is used. `SYMAFL_TRACE_MODE` is ignored — lifecycle selects transport.
- Predicate semantic boundary: `pred.cpp` supports only ≤64-bit integer bit-vectors and follows SMT-LIB division-by-zero and wide-shift rules. Other expressions become opaque and must be admitted. Any future JIT must be cross-validated against this interpreter and Z3 before use.

## Verification targets

- Replay consistency ≥ 99% (admitted candidates actually reach predicted frontier; mismatched traces are discarded, never inserted).
- Screening latency mean < 100µs/candidate; coverage ≥ 95% of baseline.
- Evaluation targets must be deterministic — non-determinism poisons the tree.

See [docs/VERIFICATION.md](docs/VERIFICATION.md) for the command matrix and [docs/STATUS.md](docs/STATUS.md) for evidence labels.

## Git workflow for agents

Full policy lives in [AGENTS.md](AGENTS.md) (“Commit and pull-request guidelines”). Apply this compact form by default:

- **Commit locally often, by intent:** one coherent change per commit (fix, script, doc section, harness). Commit after green checks, before risky edits, and before pausing a session. Do not dump unrelated files into one commit.
- **Push less often, when shareable:** push for backup, review, handoff, or a reproducible milestone. Prefer `feature/*` / `exp/*`; push `main` only when relatively stable and documented.
- **Do not push:** thrashing WIP, secrets/local absolute paths, large fuzz outputs, or any superproject pointer whose submodule commit is not yet on the submodule remote.
- **Submodule order:** commit in `symsan/` or `AFLplusplus/` → push submodule remote → commit superproject pointer → push superproject.
- **Split themes:** metadata, docs/agent files, `scripts/`, `tests/`, and submodule bumps are separate commits. Keep scratch (`task/`, corpora, `/tmp` queues, binaries, logs) out of Git unless it is a small intentional fixture.
- **After a milestone:** update [docs/NEXT_SESSION.md](docs/NEXT_SESSION.md) with intent, files, verification commands/results, risks, and next action.
