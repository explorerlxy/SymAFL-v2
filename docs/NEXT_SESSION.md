# Next Session Handoff

```text
Snapshot: superproject main after doc-system maintenance commits (local; push
          pending remote reachability), AFLplusplus comment hygiene, symsan
          lifecycle pipe-suffix / pred hygiene, 2026-07-30
Objective: completed — land documentation system + matching protocol code and
           re-verify transport modes after rebuild
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
                   milestone with focused unit tests; push remotes if not yet
                   published (submodules first, then superproject)
```

## Current recommended next action

1. Confirm remotes are published:
   - `AFLplusplus` main
   - `symsan` v2-dev
   - superproject main with matching submodule pointers
2. Start the predicate-evaluation milestone:
   - disjoint shared-arena predicates
   - converter-wide opacity policy
   - short-input direction rule
3. Do not mix transport/phase-switch changes into that milestone unless a
   regression proves coupling.
