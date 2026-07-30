# Current Status and Evidence

This file is the only place that summarizes implementation state. Update it at
every milestone with a revision and test result.

## Snapshot for the documentation-system maintenance pass

```text
Snapshot: superproject main (doc hygiene landing), AFLplusplus main + drain comment
          fix, symsan v2-dev + lifecycle pipe-suffix / pred hygiene
Reviewed: README.md, AGENTS.md, CLAUDE.md, docs/* (new structure),
          symsan/driver/aflpp/{symsan.cpp,pcbt.hpp,pcbt.cpp,pred.hpp,pred.cpp,README.md},
          symsan/backend/solver_common.cpp, symsan/runtime/dfsan/dfsan.h,
          AFLplusplus/include/{forkserver.h,afl-fuzz.h},
          AFLplusplus/src/{afl-forkserver.c,afl-fuzz.c,afl-fuzz-state.c},
          scripts/run-fuzz.sh, tests/* harnesses
Execution (2026-07-30 local):
  python3 tests/trace_check.py direct          -> PASS
  python3 tests/trace_check.py afl             -> PASS
  python3 tests/pcbt_pipe_check.py             -> PASS (65536 events, >2 MiB drained)
  python3 tests/pcbt_toy_modes_check.py        -> PASS (pipe-full -> shm overflow -> pipe-suffix)
  FUZZ_SECONDS=30 scripts/run-fuzz.sh pcbt     -> PASS
    bootstrap full events=11; tree saturated after 1 veto;
    "PCBT saturated; restarting forkserver with concrete target .../tests/toy-afl";
    deinit: traces=1 nodes=11 depth=11 admitted=1 vetoed=1 saturated=1
Logs: /tmp/symafl-verify-142306, /tmp/symafl2-pcbt-smoke
```

## Feature matrix

| Feature | Status | Evidence | Caveat |
|---|---|---|---|
| Required concolic/concrete target validation | Verified | `symsan.cpp: afl_custom_init`; `run-fuzz.sh pcbt` starts | — |
| PCBT screening in `post_process` | Verified | admitted/vetoed counters in pcbt smoke | short-input direction rule still needs directed unit test |
| Full bootstrap insertion | Verified | `pcbt-trace bootstrap mode=full events=11 created=11` | — |
| SHM frontier suffix | Verified | `pcbt_toy_modes_check.py` exercises shm-suffix path | — |
| Pipe-suffix overflow replay | Verified | same harness: forced overflow -> pipe-suffix | — |
| AFL++ parent pipe drain | Verified | `pcbt_pipe_check.py` drained 65536 events | — |
| Concrete phase-switch request + restart | Verified | mutator sets switch; `afl-fuzz.c` restarts concrete target in smoke | longer benchmarks still open |
| Terminal-edge semantics | Code-reviewed | `terminal[2]`, empty suffix handling | directed unit test still desirable |
| Local ≤64-bit predicate interpreter | Code-reviewed | `pred.cpp` rejects `size > 64`; sdiv edge hardened | shared-arena / opacity issues below |
| Memerr/UCSan path binding | Planned | decoder skips non-condition frames; counter not incremented | do not claim as-built |
| Timeout metric | Declared only | field/introspection string | no increment in mutator |
| Jigsaw in PCBT hot path | Not used | local interpreter is called | retained dependency only |

## Static-review findings requiring tests or code changes

### High priority

1. **Shared-converter opacity propagation.** `RunConverter::overflow_` is a
   converter-wide flag. An unsupported expression makes the current and all
   later predicates converted by that instance opaque. Decide whether opacity
   should be per predicate or per trace, then test it.
2. **Arena-prefix evaluation.** `eval_predicate` executes all arena indices
   `0..root`. A shared arena can contain earlier nodes unrelated to the current
   root; an unrelated out-of-range read can abort evaluation. Add a disjoint
   predicate regression and change evaluation order if reproduced.
3. **Unchecked suffix attachment.** `InsertSuffix` trusts the caller and can
   replace an existing child pointer. Enforce/check the frontier precondition at
   the caller or add a defensive failure path.

### Medium priority

4. **Metric semantics.** `saturated` means screening disabled, not necessarily
   tree saturation; `SYMAFL_NO_SCREEN` also sets it. `timeouts` and `memerr`
   remain zero in the reviewed code.
5. **Short-input rule.** Predicate evaluation failure chooses direction zero
   instead of an opaque admission. Confirm this matches the intended contract
   and does not create false vetoes.

## Documentation structure status

| Item | Status |
|---|---|
| Split architecture / protocol / PCBT / config / verification | Present under `docs/` |
| ADRs 0001–0003 | Present under `docs/decisions/` |
| Historical DESIGN / frontier / review docs | Present under `docs/archive/` |
| Root README + AGENTS operating contract | Present |
| CLAUDE.md points at canonical docs (not archived DESIGN_V2) | Updated |
| `.gitignore` versions the documentation system and test/scripts sources | Updated |
| `STATUS` / `NEXT_SESSION` reflect Git + PASS evidence | Updated this pass |

## Next verification milestone

```text
Objective: close the predicate-evaluation correctness gaps
Required files: pred.cpp, pred.hpp, a focused unit-test fixture
Acceptance:
- disjoint shared-arena predicates evaluate only their dependencies;
- unsupported predicate does not unintentionally poison later supported nodes,
  or the per-trace behavior is explicitly accepted and tested;
- short-input behavior is specified and tested;
- all existing PCBT mode checks still pass.
```
