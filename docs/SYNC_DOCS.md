# Browser Sync Digest — Documentation

Upload this file (with [`SYNC_CODE.md`](SYNC_CODE.md)) to ChatGPT Project when
you need architecture/planning context. Prefer these two digests over bulk
uploads of the whole docs tree.

**Authority:** Git worktree + submodule SHAs remain truth. This digest is a
curated summary and can lag; when conflicted, trust the named repo snapshot.

```text
Snapshot: superproject main, AFLplusplus ef727c6, symsan ee90b4a, 2026-07-30
Purpose: docs/system summary for browser review and task decomposition
```

## One-paragraph system model

SymAFL v2 runs AFL++ mutation under a PCBT (path-constraint binary tree)
screening mutator. Candidates that cannot reach an unexplored symbolic frontier
are vetoed in `afl_custom_post_process` before execution. There is **no
constraint solving** on the hot path. Phase A uses a SymSan/DFSan concolic
target and builds the tree from condition events. When the tree is saturated,
AFL++ switches to a separate concrete target, keeps queue files, and rebuilds
coverage-derived state.

## Lifecycle transport (normative)

| Mode | When | Channel | Consumer |
|---|---|---|---|
| pipe-full | bootstrap / no concrete frontier | pipe, all conditions | `InsertTrace` |
| shm-suffix | steady-state known frontier | bounded SHM after `skip_depth` | `InsertSuffix` on coverage gain |
| pipe-suffix | SHM overflow **and** coverage gain | pipe replay after `skip_depth` | `InsertSuffix` |

`SYMAFL_TRACE_MODE` is ignored. Pipe bytes are drained by the **afl-fuzz parent**
while waiting on the forkserver child; framing/semantics belong to the mutator.

## Ownership split

- **AFLplusplus:** pipe drain, phase-switch scheduling, coverage-state reset.
- **symsan mutator:** screening, arming transport, decode, PCBT insert/eval.
- **symsan runtime:** DFSan propagation + condition export according to armed mode.

## Document map (canonical sources)

| Need | Canonical file |
|---|---|
| System architecture | `ARCHITECTURE.md` |
| Trace / phase protocol | `RUNTIME_PROTOCOL.md` |
| Tree + predicate semantics | `PCBT.md` |
| Env vars / run modes | `CONFIGURATION.md` |
| Command matrix | `VERIFICATION.md` |
| Evidence + durable gaps | `STATUS.md` |
| Next action only | `NEXT_SESSION.md` |
| Research framing | `RESEARCH_CONTEXT.md` |
| Collaboration protocol | `COLLABORATION.md` |
| Durable decisions | `decisions/0001–0003` |
| Superseded notes | `archive/` |

Root entrypoints: `README.md`, operating contract `AGENTS.md`, agent skim
`CLAUDE.md`.

## ADRs (accepted)

1. **Two-phase execution** — concolic PCBT then concrete AFL++; retain queue,
   recreate coverage universe.
2. **Lifecycle-selected transport** — full / shm-suffix / pipe-suffix only; no
   production mode override.
3. **Frontier-anchored suffix** — export post-frontier conditions only;
   `InsertSuffix` does not revalidate the prefix.

## Required config (PCBT)

```bash
AFL_CUSTOM_MUTATOR_LIBRARY=.../libSymSanMutator.so
SYMAFL_CONCOLIC_TARGET=...   # must be executable
SYMAFL_CONCRETE_TARGET=...   # must be executable
TAINT_OPTIONS="taint_file=<out>/default/.cur_input:taint_max_len=65536:exit_on_memerror=false"
AFL_DISABLE_TRIM=1
```

Optional: `SYMAFL_RCNT_LIMIT` (default 16; smoke uses 0), `SYMAFL_NO_SCREEN=1`,
`SYMAFL_SINGLE_PASS_CAPACITY`.

## Verification commands

```bash
python3 tests/trace_check.py direct
python3 tests/trace_check.py afl
python3 tests/pcbt_pipe_check.py
python3 tests/pcbt_toy_modes_check.py
scripts/run-fuzz.sh pcbt          # also baseline|single|single-taint
```

Latest recorded matrix: all PASS on 2026-07-30 (see `STATUS.md`).

## Durable open issues (summary)

High: shared-converter opacity; arena-prefix eval; `InsertSuffix` precondition
trust. Medium: metric semantics (`saturated`/`timeouts`/`memerr`); short-input
direction chooses 0.

Memerr binding and Jigsaw hot-path use are **not** current claims.

## STATUS vs NEXT_SESSION

| File | Owns |
|---|---|
| `STATUS.md` | feature matrix, PASS/FAIL evidence, durable gaps |
| `NEXT_SESSION.md` | single next objective, acceptance, owner |

Facts go to STATUS. Actions go to NEXT_SESSION. Do not duplicate.

## Browser upload default

**Default (planning / review):**

1. `docs/SYNC_DOCS.md` (this file)
2. `docs/SYNC_CODE.md`
3. optional: `docs/NEXT_SESSION.md` if the next action is the topic

**Add full source files only** when editing a specific path and the digest
snippet is insufficient. Never treat uploads as live Git.

## Refresh triggers

Regenerate/refresh this digest when any of the following change:

- phase model, transport lifecycle, or ownership split;
- feature matrix evidence labels or durable open issues;
- verification command set or required env contract;
- ADR set.

Do not refresh for pure typo fixes or private experiment logs.
