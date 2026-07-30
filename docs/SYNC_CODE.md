# Browser Sync Digest — Critical Code

Companion to [`SYNC_DOCS.md`](SYNC_DOCS.md). Upload both for browser-side design
or review. This is a **curated excerpt digest**, not a substitute for the local
worktree.

```text
Snapshot: AFLplusplus ef727c6, symsan ee90b4a, 2026-07-30
If a line range drifts, re-open the path in the local checkout.
```

## Source map

| Path | Role |
|---|---|
| `symsan/driver/aflpp/symsan.cpp` | mutator lifecycle, arming, screening, queue insert |
| `symsan/driver/aflpp/pcbt.{hpp,cpp}` | tree, CheckInput, InsertTrace/InsertSuffix, saturation |
| `symsan/driver/aflpp/pred.{hpp,cpp}` | convert + ≤64-bit interpreter |
| `symsan/runtime/dfsan/dfsan.h` | SHM control block + mode constants |
| `symsan/backend/solver_common.cpp` | condition export (pipe/shm) |
| `AFLplusplus/src/afl-forkserver.c` | parent pipe drain |
| `AFLplusplus/src/afl-fuzz.c` | concrete phase switch |
| `AFLplusplus/include/afl-fuzz.h` | `pcbt_switch_pending`, concrete target fields |
| `scripts/run-fuzz.sh` | smoke modes |
| `tests/pcbt_toy_modes_check.py` | transport mode regression |

---

## 1. Shared control block and modes

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

---

## 2. Init: require both targets; ignore SYMAFL_TRACE_MODE

`symsan/driver/aflpp/symsan.cpp` (~L228–265)

```cpp
const char *concolic = getenv("SYMAFL_CONCOLIC_TARGET");
const char *concrete = getenv("SYMAFL_CONCRETE_TARGET");
if (!concolic || !*concolic || !concrete || !*concrete) {
  FATAL("PCBT mode requires SYMAFL_CONCOLIC_TARGET and "
        "SYMAFL_CONCRETE_TARGET");
}
data->afl->pcbt_mode = 1;
data->afl->pcbt_concrete_target = ck_strdup((u8 *)concrete);

if (const char *mode = getenv("SYMAFL_TRACE_MODE")) {
  WARNF("SYMAFL_TRACE_MODE=%s is ignored: PCBT transport is selected "
        "by lifecycle (bootstrap=pipe-full, steady=shm-suffix, "
        "overflow+gain=pipe-suffix)\n", mode);
}
```

`saturated` in deinit is `screening ? 0 : 1` (also true under `SYMAFL_NO_SCREEN`).

---

## 3. Arming transports

`symsan.cpp` (~L299–336)

```cpp
// bootstrap / no frontier
mode = SYMAFL_TRACE_FULL_STREAM;

// steady-state known frontier
control->skip_depth = node->depth;
mode = SYMAFL_TRACE_SUFFIX_SHM;

// overflow replay after confirmed gain
control->skip_depth = node->depth;
mode = SYMAFL_TRACE_SUFFIX_PIPE;
```

---

## 4. Screening + phase request

`symsan.cpp` `afl_custom_post_process` (~L546–601)

```cpp
// previous admitted candidate without gain: rCnt[dir]++
if (tree.CheckInput(buf, len, &node, &dir, rlimit)) {
  // admit: bootstrap/no-node -> full; else shm-suffix
  return buf_size;
}
// veto
if (tree.IsSaturated(rlimit)) {
  screening = false;
  afl->pcbt_switch_pending = 1;
}
*out_buf = NULL;
return 0;  // skip execution
```

---

## 5. Coverage-gain insert + overflow replay

`symsan.cpp` `afl_custom_queue_new_entry` (~L512–540)

```cpp
// only after bootstrap and while capture armed
// SHM suffix | pipe suffix | full stream insert
// if insert failed and frontier node known: replay_pipe_suffix(...)
```

Replay re-arms `SYMAFL_TRACE_SUFFIX_PIPE` and re-runs the same queue bytes
through the concolic forkserver.

Decoder inserts **condition** frames with nonzero non-init labels only; memerr
is not path-bound today.

---

## 6. Runtime writer

`symsan/backend/solver_common.cpp` `__taint_send_cond` (~L80–135)

```cpp
// SUFFIX_SHM + armed:
//   skip labels until skip_depth; if overflow set, stop writing;
//   else append event or set overflow when capacity exceeded.
// FULL_STREAM or SUFFIX_PIPE:
//   optional skip_depth (pipe-suffix uses control->skip_depth),
//   then write condition frame to pipe.
// Child still runs full DFSan; modes only change export.
```

`IsTraceStreamEnabled()` is true for FULL_STREAM **or** SUFFIX_PIPE.

---

## 7. PCBT CheckInput / InsertSuffix / saturation

`symsan/driver/aflpp/pcbt.cpp`

**CheckInput** (~L117–154):

```cpp
// empty tree -> admit all
// opaque/missing arena -> conservative admit, no frontier node
// eval fail (e.g. short input) -> direction 0   // intentional current rule
// terminal edge -> veto
// unexplored edge -> admit iff rCnt[d] < rlimit; return parent/dir
```

**InsertSuffix** (~L75–115):

```cpp
// no prefix replay/validation
// empty events -> mark terminal[direction]
// else attach chain with cur->child[dir] = raw  // can overwrite if misused
```

**IsSaturated** (~L160–172):

```cpp
// opaque/missing pred -> not saturated
// every direction: saturated subtree | terminal | rCnt >= rlimit
```

---

## 8. Predicate converter / evaluator risks

`symsan/driver/aflpp/pred.cpp`

```cpp
// convert(): if overflow_ already set, stay opaque (run-global flag)
// size == 0 || size > 64 -> overflow_ = true (no truncation)
//
// eval_predicate():
//   for (i = 0; i <= pred.root; i++)  // whole arena prefix, not only deps
//   Read past end -> return false
```

These two behaviors are the current high-priority correctness targets.

---

## 9. AFL++ parent drain

`AFLplusplus/src/afl-forkserver.c` (~L394–478)

```c
// read_s32_timed_with_trace:
//   select(status_fd, sym_trace_fd)
//   if pipe readable: drain_sym_trace (raw append to sym_trace_buf)
//   no frame interpretation here
// sym_trace_len reset at start of each target run
```

---

## 10. Concrete phase switch

`AFLplusplus/src/afl-fuzz.c` `switch_pcbt_to_concrete` (~L546+)

```c
// require pcbt_switch_pending + concrete target; native forkserver only
// kill fsrv; retarget argv/target_path to concrete
// possibly resize map; memset virgin_* / coverage-derived state
// retain queue files; recalibrate in concrete universe
```

---

## Open code concerns (for review prompts)

1. Per-predicate vs run-global `overflow_`.
2. `eval_predicate` prefix walk vs dependency subgraph.
3. `InsertSuffix` missing unexplored-edge assertion.
4. Short-input → direction 0 may false-veto / mis-steer.
5. `saturated` introspection conflates no-screen and true saturation.
6. `timeouts` / `memerr` counters unused.

---

## When to refresh this digest

Refresh after changes to:

- transport arming / writer / queue insert path;
- CheckInput / InsertSuffix / saturation semantics;
- predicate conversion or evaluation;
- phase-switch or pipe-drain ownership;
- any line ranges cited above if they move substantially.

For a surgical bugfix outside these excerpts, upload the single affected file
instead of regenerating the whole digest.
