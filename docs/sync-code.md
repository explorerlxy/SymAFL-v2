# Browser Sync — Code Digest

Companion to [`sync-docs.md`](sync-docs.md). Upload both for browser-side design
or review. Curated excerpts only — not a substitute for the local worktree.

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

## 2. Init: both targets required; SYMAFL_TRACE_MODE ignored

`symsan/driver/aflpp/symsan.cpp` (~L228–265)

```cpp
// require SYMAFL_CONCOLIC_TARGET + SYMAFL_CONCRETE_TARGET (executable)
// pcbt_mode = 1; store concrete path for later switch
// SYMAFL_TRACE_MODE only warns: lifecycle selects transport
```

`saturated` in deinit is `screening ? 0 : 1` (also true under `SYMAFL_NO_SCREEN`).

---

## 3. Arming transports

`symsan.cpp` (~L299–336)

```cpp
// bootstrap / no frontier  -> SYMAFL_TRACE_FULL_STREAM
// steady known frontier    -> SUFFIX_SHM, skip_depth = node->depth
// overflow replay after gain -> SUFFIX_PIPE, same skip_depth
```

---

## 4. Screening + phase request

`afl_custom_post_process` (~L546–601)

```cpp
// previous admit without gain: rCnt[dir]++
// CheckInput admit -> arm full or shm-suffix; return buf
// veto; if IsSaturated: screening=false; pcbt_switch_pending=1
// *out_buf=NULL; return 0  // skip execution
```

---

## 5. Coverage-gain insert + overflow replay

`afl_custom_queue_new_entry` (~L512–540)

```cpp
// after bootstrap + armed capture only
// insert SHM suffix | pipe suffix | full stream
// on failure with known frontier: replay_pipe_suffix(same bytes)
```

Decoder inserts **condition** frames with nonzero non-init labels only.

---

## 6. Runtime writer

`solver_common.cpp` `__taint_send_cond` (~L80–135)

```cpp
// SUFFIX_SHM: skip to skip_depth; stop if overflow; else append or set overflow
// FULL_STREAM | SUFFIX_PIPE: optional skip, then pipe write
// Child always runs full DFSan; modes only change export
```

---

## 7. PCBT CheckInput / InsertSuffix / saturation

`pcbt.cpp`

```cpp
// CheckInput: empty admit-all; opaque admit no frontier;
//   eval fail -> dir 0; terminal veto; frontier iff rCnt < rlimit
// InsertSuffix: no prefix check; empty -> terminal; else child[dir]=raw
// IsSaturated: opaque => false; else all dirs saturated|terminal|rCnt done
```

---

## 8. Predicate risks

`pred.cpp`

```cpp
// RunConverter::overflow_ is run-global
// size==0 || size>64 -> opaque (no truncation)
// eval_predicate walks i=0..root (arena prefix, not only deps)
```

---

## 9. AFL++ parent drain

`afl-forkserver.c` (~L394–478): `select(status_fd, sym_trace_fd)`; raw append to
`sym_trace_buf`; no frame interpretation; len reset each run.

## 10. Concrete phase switch

`afl-fuzz.c` `switch_pcbt_to_concrete` (~L546+): retarget forkserver to concrete;
resize map if needed; clear coverage-derived state; retain queue files.

---

## Open code concerns

1. Per-predicate vs run-global `overflow_`
2. `eval_predicate` prefix walk vs dependency subgraph
3. `InsertSuffix` missing unexplored-edge assertion
4. Short-input → direction 0
5. `saturated` introspection conflates no-screen and true saturation
6. `timeouts` / `memerr` counters unused

## Refresh when

Transport arming/writer/insert, CheckInput/InsertSuffix/saturation, predicate
convert/eval, phase-switch, or pipe-drain ownership change — or cited ranges
move substantially. For a surgical fix outside these excerpts, upload that one
file instead.
