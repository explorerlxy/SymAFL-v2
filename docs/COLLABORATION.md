# ChatGPT Project and Local Codex Collaboration

## Authority model

- **Git worktree and submodule revisions:** implementation truth.
- **Local Codex/IDE session:** inspects, edits, builds, and tests the worktree.
- **Browser ChatGPT Project:** architecture discussion, review, decision records,
  and task decomposition based on explicitly uploaded snapshots.

Neither chat surface should assume it sees the other's current files or history.

## Start-of-turn snapshot

```text
Snapshot: <branch>, <short HEAD or dirty>, submodules <summary>, <timestamp>
Worktree: <clean or changed files plus diff stat>
Objective: <one concrete outcome>
Latest verification: <command -> PASS/FAIL>
Open decision: <none or one concrete question>
```

## Implementation handoff

A browser-approved task must include:

- objective;
- non-negotiable invariants;
- named files to inspect;
- acceptance commands;
- decision/ADR references;
- explicit non-goals.

Do not rely on “the previous version” or a browser-only attachment.

## Milestone handoff

```text
Snapshot: <branch>, <short HEAD or dirty>, submodules <summary>, <timestamp>
Objective: <one concrete outcome>
Decisions/invariants: <IDs or bullets>
Changed/inspected files: <paths>
Behavioral result: <what changed>
Verification: <command -> PASS/FAIL and key observation>
Documentation updated: <paths>
Open risks/blockers: <none or concrete issue>
Next owner/action: <ChatGPT Project | local Codex> — <action>
```

Update `STATUS.md` when evidence changes and `NEXT_SESSION.md` when the next
owner/action changes.

## Upload hygiene

Upload only the smallest current snapshot needed for the task. Exclude build
trees, `.git`, fuzz output, corpora unless explicitly approved, binaries, core
dumps, credentials, tokens, SSH material, `.env*`, and unrelated benchmark
data. Replace obsolete uploaded files rather than treating same-name uploads as
version history.

## Recommended architecture bundle

1. `README.md`
2. `AGENTS.md`
3. `docs/README.md`
4. `docs/ARCHITECTURE.md`
5. `docs/RUNTIME_PROTOCOL.md`
6. `docs/PCBT.md`
7. `docs/STATUS.md`
8. `docs/NEXT_SESSION.md`
9. `symsan/driver/aflpp/symsan.cpp`
10. `symsan/driver/aflpp/pcbt.hpp`
11. `symsan/driver/aflpp/pcbt.cpp`
12. `symsan/driver/aflpp/pred.hpp`
13. `symsan/driver/aflpp/pred.cpp`
14. `symsan/runtime/dfsan/dfsan.h`
15. `symsan/backend/solver_common.cpp`
16. `AFLplusplus/include/forkserver.h`
17. `AFLplusplus/src/afl-forkserver.c`
18. `AFLplusplus/src/afl-fuzz.c` (scheduler path for `pcbt_switch_pending`)
19. the smallest affected test
20. `scripts/run-fuzz.sh`
