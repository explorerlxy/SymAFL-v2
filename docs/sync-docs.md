# Browser Sync — Docs Digest

Upload this file with [`sync-code.md`](sync-code.md) to ChatGPT Project for
architecture/planning context. Prefer these two digests over bulk docs uploads.

**Authority:** Git worktree + submodule SHAs remain truth. This digest can lag.

```text
Snapshot: superproject main, AFLplusplus ef727c6, symsan ee90b4a, 2026-07-30
Purpose: docs/system summary for browser review and task decomposition
```

## One-paragraph system model

SymAFL v2 runs AFL++ mutation under a PCBT screening mutator. Candidates that
cannot reach an unexplored symbolic frontier are vetoed in
`afl_custom_post_process` before execution. There is **no constraint solving**
on the hot path. Phase A uses a SymSan/DFSan concolic target and builds the tree
from condition events. When the tree is saturated, AFL++ switches to a separate
concrete target, keeps queue files, and rebuilds coverage-derived state.

## Lifecycle transport

| Mode | When | Channel | Consumer |
|---|---|---|---|
| pipe-full | bootstrap / no concrete frontier | pipe, all conditions | `InsertTrace` |
| shm-suffix | steady-state known frontier | bounded SHM after `skip_depth` | `InsertSuffix` on coverage gain |
| pipe-suffix | SHM overflow **and** coverage gain | pipe replay after `skip_depth` | `InsertSuffix` |

`SYMAFL_TRACE_MODE` is ignored. Pipe bytes are drained by the **afl-fuzz parent**
while waiting on the forkserver child; framing/semantics belong to the mutator.

## Ownership split

- **AFLplusplus:** pipe drain, phase-switch scheduling, coverage-state reset
- **symsan mutator:** screening, arming transport, decode, PCBT insert/eval
- **symsan runtime:** DFSan propagation + condition export per armed mode

## Document map

| Need | File |
|---|---|
| System structure | `system.md` |
| Trace / phase protocol | `protocol.md` |
| Tree + predicate semantics | `pcbt.md` |
| Env vars / run modes | `config.md` |
| Command matrix | `verify.md` |
| Evidence + durable gaps | `status.md` |
| Next action only | `next.md` |
| Research framing | `research.md` |
| Collaboration protocol | `workflow.md` |
| Durable decisions | `adr/0001–0003` |
| History | Git (`git log -- docs/`) |

Root: `README.md`, contract `AGENTS.md`, agent skim `CLAUDE.md`.

## ADRs (accepted)

1. **Two-phase execution** — concolic PCBT then concrete AFL++; retain queue,
   recreate coverage universe.
2. **Lifecycle-selected transport** — full / shm-suffix / pipe-suffix only.
3. **Frontier-anchored suffix** — export post-frontier conditions only;
   `InsertSuffix` does not revalidate the prefix.

## Required config (PCBT)

```bash
AFL_CUSTOM_MUTATOR_LIBRARY=.../libSymSanMutator.so
SYMAFL_CONCOLIC_TARGET=...   # executable
SYMAFL_CONCRETE_TARGET=...   # executable
TAINT_OPTIONS="taint_file=<out>/default/.cur_input:taint_max_len=65536:exit_on_memerror=false"
AFL_DISABLE_TRIM=1
```

Optional: `SYMAFL_RCNT_LIMIT` (default 16; smoke uses 0), `SYMAFL_NO_SCREEN=1`,
`SYMAFL_SINGLE_PASS_CAPACITY`.

## Verification commands

```bash
python3 tests/trace_check.py direct|afl
python3 tests/pcbt_pipe_check.py
python3 tests/pcbt_toy_modes_check.py
scripts/run-fuzz.sh pcbt   # also baseline|single|single-taint
```

Latest recorded matrix: all PASS on 2026-07-30 (see `status.md`).

## Durable open issues

High: shared-converter opacity; arena-prefix eval; `InsertSuffix` precondition
trust. Medium: metric semantics (`saturated`/`timeouts`/`memerr`); short-input
direction chooses 0. Memerr binding and Jigsaw hot-path use are not current.

## status vs next

| File | Owns |
|---|---|
| `status.md` | feature matrix, evidence, durable gaps |
| `next.md` | single next objective, acceptance, owner |

## Browser upload default

1. `docs/sync-docs.md` (this file)
2. `docs/sync-code.md`
3. optional `docs/next.md`

Add full sources only when editing a path and the code digest is insufficient.

## Refresh triggers

Normative behavior, feature evidence, verification commands, required env, or
ADR set changes. Skip pure typos and private experiment logs.
