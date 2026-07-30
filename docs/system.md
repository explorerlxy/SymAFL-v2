# SymAFL v2 Architecture

## Purpose and non-goals

SymAFL v2 evaluates whether PCBT-guided candidate screening can offset the cost
of executing a concolic target. It combines AFL++ mutation and coverage feedback
with SymSan/DFSan branch-predicate collection.

Current non-goals:

- no constraint solving;
- no solver-generated inputs;
- no Jigsaw JIT in the PCBT hot path;
- no claim that every SymSan event type is consumed by the mutator;
- no cross-target or network interaction outside the declared experiment.

## Two binaries, two temporal phases

### Phase A — concolic PCBT screening

The active target is built with SymSan/DFSan tracing plus AFL-compatible
coverage/forkserver support. Every candidate that survives `post_process` is
executed as a concolic child. PCBT is incrementally built from symbolic
condition events.

### Phase B — concrete AFL++

When all evaluable PCBT paths end in terminal edges or rCnt-pruned frontiers,
the mutator requests a phase switch. The concrete target becomes active. Queue
files are retained, while coverage-derived state must be recreated for the
concrete binary and the retained queue recalibrated.

The reviewed mutator sets `pcbt_switch_pending`; the scheduler-side restart and
coverage reset must be verified in the corresponding AFL++ scheduler files and
end-to-end smoke test.

## Component boundaries

```text
AFL++ parent process
├── mutation and coverage scheduling
├── custom mutator callbacks
│   ├── PCBT screening
│   ├── trace-mode arming
│   ├── event decoding
│   └── PCBT insertion
├── forkserver-control wait loop
│   └── drains optional SymAFL pipe into sym_trace_buf
└── phase-switch coordinator

Target forkserver process
├── remains resident during a phase
├── receives AFL control messages
└── forks one target child per execution

Concolic child
├── executes the target from program entry
├── performs DFSan propagation and label/AST construction
└── exports condition events according to the armed mode
```

The target forkserver does not consume the SymAFL event pipe. The AFL++ parent
only drains bytes; the custom mutator owns framing, semantic decoding, and tree
insertion.

## Main code map

| Responsibility | Path |
|---|---|
| Mutator lifecycle and callbacks | `symsan/driver/aflpp/symsan.cpp` |
| PCBT node/edge semantics | `symsan/driver/aflpp/pcbt.hpp`, `pcbt.cpp` |
| Predicate conversion/evaluation | `symsan/driver/aflpp/pred.hpp`, `pred.cpp` |
| Runtime trace control protocol | `symsan/runtime/dfsan/dfsan.h` and runtime implementation |
| Condition-event export | `symsan/backend/solver_common.cpp` |
| Parent-side pipe drain | `AFLplusplus/include/forkserver.h`, `AFLplusplus/src/afl-forkserver.c` |
| Smoke entrypoint | `scripts/run-fuzz.sh` |

## Data ownership

- PCBT nodes and predicate arenas live in the AFL++ parent process through the
  custom mutator.
- The union table and suffix event buffer are shared with the concolic
  forkserver/children.
- Pipe bytes are buffered per target execution in `afl_forkserver_t` and reset
  before the next `afl_fsrv_run_target` call.
- A suffix is consumed only after AFL++ confirms a new queue entry; non-gaining
  suffix data is discarded before the next candidate.

## Architectural invariants

1. **Lifecycle-selected transport:** bootstrap uses full pipe; normal frontier
   execution uses SHM suffix; only overflow plus confirmed gain uses pipe suffix.
2. **Full concolic execution:** suffix modes suppress event export only; they do
   not skip target execution, taint propagation, or label construction.
3. **Single consumer:** pipe content is drained by AFL++ parent and semantically
   consumed by the mutator.
4. **Frontier ownership:** `CheckInput` records the parent node, direction, and
   depth used by suffix capture and insertion.
5. **Coverage separation:** concolic and concrete targets do not share a valid
   coverage universe merely because queue files are reusable.
6. **Conservative opacity:** an opaque predicate prevents precise screening and
   therefore prevents the tree from being considered saturated along that path.
