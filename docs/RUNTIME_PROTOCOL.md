# Runtime Trace and Phase Protocol

## Actors

| Actor | Responsibility |
|---|---|
| `afl-fuzz` parent | mutation, coverage accounting, custom mutator, pipe drain, phase scheduling |
| target forkserver | persistent execution coordinator; not an event-pipe reader |
| concolic child | target execution, DFSan propagation, event production |

## Initialization

`afl_custom_init` performs these actions before the target forkserver starts:

1. requires executable `SYMAFL_CONCOLIC_TARGET` and
   `SYMAFL_CONCRETE_TARGET` paths;
2. enables PCBT mode and stores the concrete target path in AFL state;
3. creates a shared union-table object and a shared event-control object;
4. creates a pipe for full/suffix streaming and makes its read endpoint
   non-blocking;
5. assigns the read endpoint to `afl->fsrv.sym_trace_fd`;
6. appends the SHM names, sizes, and pipe fd to `TAINT_OPTIONS`;
7. initializes the PCBT mutator state.

The target must inherit the write endpoint and shared-memory identifiers before
forkserver initialization.

## Capture modes

| Internal mode | Lifecycle trigger | Export channel | Exported conditions | Consumer |
|---|---|---|---|---|
| `SYMAFL_TRACE_FULL_STREAM` | initial corpus, empty tree, or admission without a concrete frontier | pipe | all symbolic condition events | `InsertTrace` |
| `SYMAFL_TRACE_SUFFIX_SHM` | steady-state admission at a known frontier | bounded SHM | events after `skip_depth` | `InsertSuffix` on coverage gain |
| `SYMAFL_TRACE_SUFFIX_PIPE` | SHM overflow and confirmed coverage gain | pipe replay | events after `skip_depth` | `InsertSuffix` |
| `SYMAFL_TRACE_OFF` | no armed capture | none | none | none |

`SYMAFL_TRACE_MODE` is intentionally ignored. Production transport is selected
by lifecycle, not by a user override.

## Callback timeline

### Bootstrap

```text
post_process
  └─ tree empty or bootstrap incomplete
      └─ arm full stream

forkserver child runs
  ├─ child writes condition frames
  └─ AFL++ parent drains pipe while waiting for child status

post_run
  └─ decode pipe frames
      └─ InsertTrace

queue_get
  └─ mark bootstrap complete
```

### Steady-state candidate with known frontier

```text
post_process
  ├─ CheckInput(candidate)
  ├─ admit frontier parent/direction
  └─ arm SHM suffix with skip_depth = parent.depth

child runs once
  └─ stores only post-frontier conditions in SHM

no coverage gain
  └─ next post_process increments rCnt and discards armed data

coverage gain
  └─ queue_new_entry reads the saved queue file
      ├─ SHM valid: InsertSuffix
      └─ SHM overflow: replay same input in pipe-suffix mode, then InsertSuffix
```

### Saturation

A vetoed candidate triggers `Tree::IsSaturated`. When true, the mutator disables
screening and sets `afl->pcbt_switch_pending`. The actual forkserver replacement,
coverage reset, queue recalibration, and scheduler resumption are AFL++-side
responsibilities.

## Pipe drain contract

The AFL++ parent waits on both `fsrv_st_fd` and `sym_trace_fd` with `select()`.
When the event pipe is readable, it drains bytes until `EAGAIN` and appends them
to a dynamically grown `sym_trace_buf`. It does not interpret frames there.

This avoids the circular wait that would occur if a child blocked on a full
pipe while the parent waited only for child completion. `sym_trace_len` is reset
at the beginning of each target execution.

## Frame decoding in the reviewed mutator

The current decoder inserts only `cond_type` messages with a nonzero,
non-initializing label. It understands trailer lengths for selected non-condition
message types only so that framing remains aligned. It does not currently turn
memerr events into PCBT-linked findings.

Therefore:

- condition-stream validity is an implemented concern;
- memerr path binding is not current behavior in the reviewed mutator;
- any future event consumer must be specified and tested separately.

## Failure behavior

- Invalid pipe framing increments `failed_runs` and aborts insertion for that
  capture.
- Invalid SHM labels abort suffix insertion.
- SHM overflow causes pipe-suffix replay only after coverage gain.
- A failed replay increments `failed_runs` and leaves the PCBT unchanged for
  that suffix.
- Timeouts and crashes require explicit policy. The reviewed statistics expose
  a timeout field, but the reviewed mutator does not increment it.

## Strict suffix preconditions

`InsertSuffix(parent, direction, events, ...)` does not verify the root prefix.
The caller must guarantee all of the following:

1. `parent` belongs to the current tree;
2. `direction` is 0 or 1;
3. `parent->child[direction]` is unexplored;
4. the saved candidate reached that exact frontier in the execution that
   produced the suffix;
5. symbolic-condition counting uses the same filter in screening, skip-depth,
   SHM, pipe, and insertion;
6. no concurrent tree mutation invalidated the saved node.

An empty suffix marks the frontier edge terminal.
