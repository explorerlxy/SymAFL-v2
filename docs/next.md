# Next Action

Action-only relay. **Do not** restate the feature matrix or long evidence logs;
those live in [`status.md`](status.md).

```text
Snapshot: superproject main, AFLplusplus ef727c6, symsan ee90b4a, 2026-07-30
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
Blockers: none beyond status.md high-priority items 1–3 / medium 5
Owner: Codex VS Code
```

## Refresh rules

- Update only when next owner, objective, or acceptance commands change.
- Keep the body under ~30 lines.
- If `status.md` already makes the next step obvious, leave this file alone.
