# Next Session Handoff

```text
Snapshot: superproject main (docs-system landing), AFLplusplus ef727c6, symsan ee90b4a,
          clean published worktrees, 2026-07-30
Objective: completed — land documentation system + matching protocol code and
           re-verify transport modes
Decisions/invariants:
- ADR 0001 two-phase execution
- ADR 0002 lifecycle-selected transport
- ADR 0003 frontier-anchored suffix
Changed/inspected files:
- .gitignore, .gitmodules, README.md, AGENTS.md, CLAUDE.md
- docs/** (map, archive, ADRs, STATUS, NEXT_SESSION)
- scripts/**, tests/** (sources/harnesses; binaries ignored)
- symsan: solver_common.cpp, dfsan.h, symsan.cpp, pred.cpp, driver/aflpp/README.md
- AFLplusplus: forkserver.h, afl-forkserver.c (comments only)
Verification:
- python3 tests/trace_check.py direct -> PASS
- python3 tests/trace_check.py afl -> PASS
- python3 tests/pcbt_pipe_check.py -> PASS
- python3 tests/pcbt_toy_modes_check.py -> PASS
- FUZZ_SECONDS=30 scripts/run-fuzz.sh pcbt -> PASS (phase switch observed)
Open risks/blockers:
- shared-converter opacity; arena-prefix eval; InsertSuffix precondition trust
- treat metrics saturated/timeouts/memerr carefully for papers
Next owner/action: local Codex — start predicate-evaluation correctness
                   milestone with focused unit tests
```

## Current recommended next action

Start the predicate-evaluation milestone without mixing transport or
phase-switch changes:

1. Disjoint shared-arena predicates evaluate only their dependencies.
2. Converter-wide opacity is either fixed per predicate or explicitly accepted
   and tested as per-trace behavior.
3. Short-input direction rule is specified and regression-tested.
4. Existing PCBT mode checks remain green.
