# Next Session Handoff

Action-only relay. **Do not** restate the feature matrix or long evidence logs;
those live in [`STATUS.md`](STATUS.md).

```text
Snapshot: superproject main, AFLplusplus ef727c6, symsan ee90b4a, clean, 2026-07-30
Next objective: close predicate-evaluation correctness gaps
Invariants: ADR 0001–0003; no transport/phase-switch changes in this milestone
Start in:
- symsan/driver/aflpp/pred.cpp
- symsan/driver/aflpp/pred.hpp
- focused unit fixture under symsan/tests/ or tests/
Acceptance:
- disjoint shared-arena predicates evaluate only their dependencies
- converter opacity is either per-predicate or explicitly accepted/tested as per-trace
- short-input direction rule is specified and regression-tested
- existing PCBT mode checks still PASS
Blockers: none beyond STATUS high-priority items 1–3 / medium 5
Owner: local Codex
```

## Refresh rules

- Update this file only when the next owner, next objective, or acceptance
  commands change.
- Keep the body under ~30 lines.
- If STATUS already makes the next step obvious and no handoff is needed, leave
  this file unchanged.
