# SymAFL v2 Critical Code Digest

This is the sole browser synchronization digest. Upload it with the canonical
context documents named in [chatgpt-codex-cooperation.md](chatgpt-codex-cooperation.md):
`system.md`, `evaluation.md`, `status.md`, and optional `next.md`. It is curated
implementation context, not a second system specification and not a substitute
for the local worktree.

```text
Snapshot: superproject main, AFLplusplus ef727c6, symsan ee90b4a, 2026-07-30
Freshness: documentation consolidation; updated context contract and document links
Changed sections: preamble, verification pointer, freshness record
If a code range drifts, reopen the path in the local checkout.
```

## Source map

| Path | Role |
|---|---|
| `symsan/driver/aflpp/symsan.cpp` | mutator lifecycle, arming, screening, queue insertion |
| `symsan/driver/aflpp/pcbt.{hpp,cpp}` | tree, `CheckInput`, `InsertTrace`/`InsertSuffix`, saturation |
| `symsan/driver/aflpp/pred.{hpp,cpp}` | converter and <=64-bit interpreter |
| `symsan/runtime/dfsan/dfsan.h` | SHM control block and mode constants |
| `symsan/backend/solver_common.cpp` | condition export to pipe or SHM |
| `AFLplusplus/src/afl-forkserver.c` | parent pipe drain |
| `AFLplusplus/src/afl-fuzz.c` | concrete phase switch |
| `AFLplusplus/include/afl-fuzz.h` | `pcbt_switch_pending`, concrete-target fields |
| `scripts/run-fuzz.sh` | smoke modes |
| `tests/pcbt_toy_modes_check.py` | transport-mode regression |

## Shared control block and modes

`symsan/runtime/dfsan/dfsan.h`

```c
#define SYMAFL_TRACE_OFF 0U
#define SYMAFL_TRACE_FULL_STREAM 1U
#define SYMAFL_TRACE_SUFFIX_SHM 2U
#define SYMAFL_TRACE_SUFFIX_PIPE 3U

struct symafl_single_pass_control {
  uint32_t magic, version, mode, armed;
  uint32_t skip_depth, event_capacity, event_count, overflow, reserved;
  symafl_single_pass_event events[];
};
```

## Mutator lifecycle and transport

`symsan/driver/aflpp/symsan.cpp`

```cpp
// init requires executable SYMAFL_CONCOLIC_TARGET + SYMAFL_CONCRETE_TARGET
// pcbt_mode = 1; store concrete target for later phase switch
// SYMAFL_TRACE_MODE only warns: lifecycle selects transport

// bootstrap / no frontier       -> SYMAFL_TRACE_FULL_STREAM
// steady known frontier         -> SYMAFL_TRACE_SUFFIX_SHM at node->depth
// overflow replay after gain    -> SYMAFL_TRACE_SUFFIX_PIPE at same depth

// post_process: previous no-gain admission increments rCnt
// CheckInput admit -> arm capture and return candidate
// veto + IsSaturated -> screening=false; pcbt_switch_pending=1
```

`saturated` printed during deinit is `screening ? 0 : 1`; it is therefore also
true under `SYMAFL_NO_SCREEN`.

## Coverage-gain insertion and writer

`afl_custom_queue_new_entry` inserts a full trace or suffix only after bootstrap
and an armed capture. A known-frontier capture that fails or overflows replays
the same queue bytes through pipe suffix before insertion.

`symsan/backend/solver_common.cpp`, `__taint_send_cond`:

```cpp
// SUFFIX_SHM: skip to skip_depth; append until overflow
// FULL_STREAM | SUFFIX_PIPE: optional skip, then pipe write
// child still performs complete DFSan propagation and label construction
```

The decoder inserts condition frames with nonzero non-initializing labels only.

## PCBT and predicate anchors

`symsan/driver/aflpp/pcbt.cpp`

```cpp
// CheckInput: empty admit-all; opaque admit no frontier;
// eval failure -> direction 0; terminal veto; frontier iff rCnt < rlimit
// InsertSuffix: no prefix check; empty suffix -> terminal; else child[dir]=raw
// IsSaturated: opaque => false; otherwise every direction is exhausted
```

`symsan/driver/aflpp/pred.cpp`

```cpp
// RunConverter::overflow_ is run-global
// size == 0 || size > 64 -> opaque; no truncation
// eval_predicate walks i=0..root, not only root dependencies
```

These caveats are engineering gaps, not current logical guarantees; see
[status.md](status.md) and the corresponding required regressions in
[evaluation.md](evaluation.md).

## AFL++ integration anchors

- `AFLplusplus/src/afl-forkserver.c`: `select(status_fd, sym_trace_fd)`, raw
  append to `sym_trace_buf`, no frame interpretation, length reset each run.
- `AFLplusplus/src/afl-fuzz.c`: `switch_pcbt_to_concrete` retargets the
  forkserver, resizes the map when needed, clears coverage-derived state, and
  keeps queue files.

## Verification snapshot

The latest recorded implementation evidence is in [status.md](status.md):
`trace_check.py` direct and AFL, long pipe drain, three transport modes, and a
30-second PCBT smoke all passed on 2026-07-30. This digest does not claim
unrecorded baseline, performance, or benchmark results.

## Open implementation risks

1. Per-predicate versus run-global converter opacity
2. Arena-prefix evaluation versus root dependency graph
3. `InsertSuffix` without an unexplored-edge assertion
4. Short input choosing direction `0`
5. `saturated` conflating no-screen and true saturation
6. Unused `timeouts` and `memerr` counters

## Refresh rule

Refresh only the affected sections when critical behavior, cited paths/ranges,
submodule SHAs, verification excerpt, or code-risk summary changes. Record the
snapshot, changed sections, and reason at the top; do not rewrite unchanged
sections. The complete synchronization contract is in
[chatgpt-codex-cooperation.md](chatgpt-codex-cooperation.md).
