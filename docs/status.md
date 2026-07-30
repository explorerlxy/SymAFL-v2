# Engineering Realization Status

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
Snapshot: superproject main (prior document-map revision),
          AFLplusplus main ef727c6,
          symsan v2-dev ee90b4a
Last matrix run: 2026-07-30
  python3 tests/trace_check.py direct          -> PASS
  python3 tests/trace_check.py afl             -> PASS
  python3 tests/pcbt_pipe_check.py             -> PASS
  python3 tests/pcbt_toy_modes_check.py        -> PASS
  FUZZ_SECONDS=30 scripts/run-fuzz.sh pcbt     -> PASS
    bootstrap full events=11; saturated after 1 veto;
    concrete restart observed; nodes=11 admitted=1 vetoed=1
Logs: /tmp/symafl-verify-142306, /tmp/symafl2-pcbt-smoke
```

This documentation refactor creates no new runtime or experiment evidence. The
snapshot above remains the last recorded implementation matrix until a later
run replaces it.

## System realization map

| Logical component or workflow | Current implementation paths | Status | Recorded verification | Caveat |
|---|---|---|---|---|
| Required concolic and concrete targets | `symsan/driver/aflpp/symsan.cpp:afl_custom_init` | Verified | PCBT smoke | targets must be executable |
| PCBT screening before execution | `symsan.cpp:afl_custom_post_process`; `pcbt.cpp:CheckInput` | Verified | admitted/vetoed in PCBT smoke | short-input decision needs unit test |
| Full bootstrap trace and insertion | `symsan.cpp`; `solver_common.cpp`; `pcbt.cpp:InsertTrace` | Verified | bootstrap `mode=full events=11` | — |
| SHM frontier suffix | `symsan.cpp`; `dfsan.h`; `solver_common.cpp`; `pcbt.cpp:InsertSuffix` | Verified | `pcbt_toy_modes_check.py` | insertion precondition is caller-owned |
| Pipe-suffix overflow replay | `symsan.cpp`; `solver_common.cpp` | Verified | harness observed overflow then pipe suffix | replay requires coverage gain |
| Parent-side pipe drain | `AFLplusplus/src/afl-forkserver.c` | Verified | `pcbt_pipe_check.py` with 65536 events | parent stores raw bytes only |
| Concrete phase switch and state reset | `symsan.cpp`; `AFLplusplus/src/afl-fuzz.c` | Verified | 30-second PCBT smoke | longer benchmark evidence remains open |
| Terminal-edge semantics | `pcbt.cpp:InsertSuffix`, `CheckInput` | Code-reviewed | empty suffix behavior reviewed | directed topology unit test desirable |
| <=64-bit predicate interpreter | `symsan/driver/aflpp/pred.cpp` | Code-reviewed | source review; wide expressions opaque | shared-arena and opacity gaps |
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
| Benchmark contribution | xz entrypoint exists | no result recorded here | `scripts/eval-xz.sh` | define benchmark snapshot and run controlled comparison |

## Durable engineering gaps

### High

1. **Shared-converter opacity.** `RunConverter::overflow_` is run-global; one
   unsupported expression can make later predicates opaque.
2. **Arena-prefix evaluation.** `eval_predicate` evaluates indices `0..root`,
   not only the root-reachable dependency graph.
3. **Unchecked `InsertSuffix`.** Caller must guarantee an unexplored frontier;
   misuse can overwrite a reachable child.

### Medium

4. **Metric semantics.** `saturated` means screening disabled, including under
   `SYMAFL_NO_SCREEN`; `timeouts` and `memerr` remain zero.
5. **Short-input rule.** Failed predicate reads choose direction `0` rather than
   opaque admission.

## Documentation ownership

- [system.md](system.md): logical components, workflows, semantics, invariants
- [evaluation.md](evaluation.md): logical experiment design and criteria
- `status.md`: current code mapping, executed evidence, measurable results, gaps
- [next.md](next.md): next action only
- [chatgpt-codex-cooperation.md](chatgpt-codex-cooperation.md): cross-surface
  context and responsibility contract

Update this file whenever implementation mapping, experiment evidence, measured
results, or durable gaps change. Do not put next-action narrative here.
