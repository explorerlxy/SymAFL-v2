# Engineering Implementation Status

This is the durable engineering layer for the logical designs in
[system.md](system.md) and [evaluation.md](evaluation.md). It answers: which
components and workflows exist in the current source snapshot, where they are
implemented, what has actually been exercised, and which gaps remain?

It does **not** own the next action; that belongs in [next.md](next.md).

## Evidence labels

- **Verified** — implementation path identified and covered by recorded PASS
- **Code-reviewed** — implementation path identified; directed PASS is missing
  or only partial smoke exists
- **Declared only** — an interface or metric exists but has no working evidence
- **Planned** — not current behavior

## Snapshot and retained evidence

```text
Snapshot: superproject main 5eff0b8 (dirty),
          AFLplusplus main ef727c6,
          symsan v2-dev 193cfd7 (dirty)
Last PCBT-structure matrix run: 2026-07-31
  scripts/build-all.sh symsan                 -> PASS
  python3 tests/trace_check.py direct          -> PASS; 11 symbolic conditions
  python3 tests/trace_check.py afl             -> PASS; 32011 symbolic conditions
  python3 tests/pcbt_pipe_check.py             -> PASS; 65536 events drained
  python3 tests/pcbt_toy_modes_check.py        -> PASS; pipe-full -> SHM overflow -> pipe-suffix
  scripts/run-fuzz.sh pcbt                     -> PASS; 11 bootstrap nodes, one veto, concrete restart

Prior matrix: 2026-07-30
  python3 tests/trace_check.py direct          -> PASS
  python3 tests/trace_check.py afl             -> PASS
  python3 tests/pcbt_pipe_check.py             -> PASS
  python3 tests/pcbt_toy_modes_check.py        -> PASS
  FUZZ_SECONDS=30 scripts/run-fuzz.sh pcbt     -> PASS
    bootstrap full events=11; saturated after 1 veto;
    concrete restart observed; nodes=11 admitted=1 vetoed=1
Logs: /tmp/symafl-verify-142306, /tmp/symafl2-pcbt-smoke
```

The 2026-07-31 matrix covers the global predicate arena, root-reachable
interpreter, index-addressed terminal representation, and 8-bit retry-limit
change on deterministic toy fixtures. It is not a benchmark-scale memory or
screening-latency result.

Predicate-conversion follow-up, 2026-08-01 (current dirty worktree):

```text
clang++-18 -std=c++17 -O2 -I"$(llvm-config-18 --includedir)" \
  -Isymsan/runtime -Isymsan/driver/aflpp tests/pcbt_predicate_check.cpp \
  symsan/driver/aflpp/pred.cpp -o /tmp/pcbt_predicate_check \
  && /tmp/pcbt_predicate_check                           -> PASS
scripts/build-all.sh symsan                              -> PASS
RUN_ID=opaque-total-20260801T000000Z FUZZ_SECONDS=10 \
  scripts/eval-xz.sh pcbt                               -> PASS (diagnostic)
  paired-target smoke passed; opaque=0, veto_terminal=18615,
  screened=21783, admitted=3168, executed=3180, but traces=1/nodes=1 and
  admit_eval_failure=3167. This is not multi-root or suffix evidence.
Logs: /tmp/symafl-opaque-final-build.log,
      /tmp/symafl-v2-xz/opaque-total-20260801T000000Z
```

## System realization map

| Logical component or workflow | Current implementation paths | Status | Recorded verification | Caveat |
|---|---|---|---|---|
| Required concolic and concrete targets | `symsan/driver/aflpp/symsan.cpp:afl_custom_init` | Verified | PCBT smoke | targets must be executable |
| PCBT screening before execution | `symsan.cpp:afl_custom_post_process`; `pcbt.cpp:CheckInput` | Verified | admitted/vetoed in PCBT smoke; 2026-08-01 conservative eval-failure admission | distinct entry trace classes remain unresolved |
| Full bootstrap trace and insertion | `symsan.cpp`; `solver_common.cpp`; `pcbt.cpp:InsertTrace` | Verified | bootstrap `mode=full events=11` | — |
| SHM frontier suffix | `symsan.cpp`; `dfsan.h`; `solver_common.cpp`; `pcbt.cpp:InsertSuffix` | Verified | `pcbt_toy_modes_check.py` | insertion precondition is caller-owned |
| Pipe-suffix overflow replay | `symsan.cpp`; `solver_common.cpp` | Verified | harness observed overflow then pipe suffix | replay requires coverage gain |
| Parent-side pipe drain | `AFLplusplus/src/afl-forkserver.c` | Verified | `pcbt_pipe_check.py` with 65536 events | parent stores raw bytes only |
| Concrete phase switch and state reset | `symsan.cpp`; `AFLplusplus/src/afl-fuzz.c` | Verified | 30-second PCBT smoke | longer benchmark evidence remains open |
| Terminal-edge semantics | `pcbt.cpp:InsertSuffix`, `CheckInput` | Verified | PCBT smoke and transport regression | direct topology unit test remains desirable |
| Compact PCBT storage | `pcbt.{hpp,cpp}` | Verified | 2026-07-31 PCBT matrix | 32-bit node references; `0`/`1` are unexplored/terminal; no per-node ID or terminal flags |
| Scalar predicate conversion/interpreter | `symsan/driver/aflpp/pred.cpp` | Code-reviewed | iterative conversion, per-root rollback/resource accounting, shared candidate cache, direct <=8-byte `fmemcmp==0`; focused regression PASS | full transport matrix pending after this change; wide/string/FP grammar remains explicit fallback/preflight scope |
| Memerr/UCSan finding binding | mutator decoder | Planned | decoder skips non-condition frames | do not claim it as built |
| Timeout and memerr counters | mutator statistics | Declared only | none | counters are not incremented |
| Jigsaw in PCBT hot path | `symsan/solvers/jigsaw/` retained only | Verified absent | code review | local interpreter is active path |

## Evaluation realization and results

The following rows map [evaluation.md](evaluation.md)'s designed experiments to
currently recorded evidence. Unlisted performance or benchmark results have not
been recorded and must not be inferred from the existence of scripts.

| Evaluation question | Executed configuration | Result | Evidence / log | Remaining gap |
|---|---|---|---|---|
| Direct symbolic-condition tracing | toy fixture, direct SymSan execution | PASS; nonzero labels | `tests/trace_check.py direct`; `/tmp/symafl-verify-142306` | none for smoke scope |
| Forkserver trace integration | toy fixture through AFL++ forkserver | PASS; forkserver and labels observed | `tests/trace_check.py afl`; same log root | none for smoke scope |
| Pipe-drain safety | long local event stream | PASS; 65536 events drained without deadlock | `tests/pcbt_pipe_check.py` | benchmark-scale volume unmeasured |
| Lifecycle transport | toy fixture with forced SHM pressure | PASS; full bootstrap, SHM suffix, pipe-suffix replay | `tests/pcbt_toy_modes_check.py` | more malformed-frame cases desirable |
| PCBT-to-concrete transition | `FUZZ_SECONDS=30`, toy binaries, smoke retry limit | PASS; 11 bootstrap events, one admitted, one vetoed, concrete restart | `scripts/run-fuzz.sh pcbt`; `/tmp/symafl2-pcbt-smoke` | no long-run coverage comparison |
| Concrete baseline | evaluation design exists | no result recorded here | `scripts/run-fuzz.sh baseline` is available | execute and record before comparative claim |
| Screening-overhead controls | evaluation design exists | no result recorded here | `single`, `single-taint`, and no-screen modes available | measure latency, throughput, RSS, CPU |
| Benchmark contribution / XZ throughput pilot | sequential 30 s × 1 run each: concrete AFL, no-screen concolic, PCBT; dual XZ builds from local `xz` source `6e8732c`, seeds under `test/Realworld/xz/seeds`, SHA256 checks disabled for concolic TaintPass stability | Earlier pilot remains only a pilot. New 10 s PCBT diagnostic has `opaque=0` and `veto_terminal=18615`, but learned only `traces=1/nodes=1`; `admit_eval_failure=3167` and no frontier/suffix capture. It establishes the local opaque fix, not safe multi-entry screening or comparative performance. | `/tmp/symafl-v2-xz/opaque-total-20260801T000000Z` | establish entry-trace-class routing before claiming valid/malformed multi-root screening; rerun full matrix; TaintPass crash still forces no SHA256 |

## Durable engineering gaps

### High

1. **Unchecked `InsertSuffix`.** Caller must guarantee an unexplored frontier;
   misuse can overwrite a reachable child.

### Medium

4. **Metric semantics.** `saturated` means screening disabled, including under
   `SYMAFL_NO_SCREEN`; `timeouts` and `memerr` remain zero.
5. **Entry trace classes.** A single-root tree learned from one bootstrap
   sequence is not yet safe to use for candidates whose first symbolic
   condition belongs to another sequence; define class affinity or a
   conservative multi-root dispatcher before screening such candidates.
6. **XZ short-input admissions and suffix coverage.** The latest diagnostic
   eliminates opaque nodes but has `admit_eval_failure=3167`, one learned node,
   and no frontier/suffix capture. It is not evidence of complete XZ filtering.

## Documentation ownership

- [system.md](system.md): logical components, workflows, semantics, invariants
- [evaluation.md](evaluation.md): logical experiment design and criteria
- `status.md`: current code mapping, executed evidence, measurable results, gaps
- [next.md](next.md): next action only
- [chatgpt-codex-cooperation.md](chatgpt-codex-cooperation.md): cross-surface
  context and responsibility contract

Update this file whenever implementation mapping, experiment evidence, measured
results, or durable gaps change. Do not put next-action narrative here.
