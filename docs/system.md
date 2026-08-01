# SymAFL v2 System Design

## Purpose and contribution

SymAFL v2 evaluates whether a Path Constraint Binary Tree (PCBT) can reduce the
cost of concolic fuzzing without using constraint solving. It combines AFL++
mutation and coverage feedback with SymSan/DFSan branch-predicate collection.

The central contribution is in-process candidate screening. Before a candidate
executes, the custom mutator evaluates the PCBT predicates already learned from
prior concolic runs. A candidate that can only follow explored terminal paths is
vetoed; a candidate that can reach an unexplored symbolic frontier is admitted.
This is screening, not input synthesis: the current hot path has no constraint
solver, no solver-generated inputs, and no Jigsaw JIT evaluation.

A second contribution is frontier-anchored trace transport. Every admitted child
still performs complete target execution, DFSan propagation, and label-DAG
construction. After bootstrap, it exports only condition events following the
known frontier. This reduces transfer and insertion work without changing the
child's concolic execution.

Current non-goals:

- no constraint solving or solver-generated inputs;
- no Jigsaw JIT in the PCBT hot path;
- no claim that every SymSan event type is consumed by the mutator; and
- no cross-target or network interaction outside the declared experiment.

## Execution model

### Two binaries, two temporal phases

**Phase A: concolic PCBT screening.** The active target is built with
SymSan/DFSan tracing plus AFL-compatible coverage and forkserver support. Each
candidate that survives `afl_custom_post_process` executes as a concolic child.
PCBT grows from its symbolic-condition events.

**Phase B: concrete AFL++.** When the PCBT has no remaining evaluable frontier,
the mutator requests a phase switch. AFL++ replaces the concolic forkserver with
the configured concrete target, retains queue files, recreates coverage-derived
state for the concrete binary, recalibrates the retained queue, and resumes
ordinary AFL++ fuzzing.

Concolic and concrete targets do not share a valid coverage universe merely
because they reuse the same queue files.

### Components and ownership

```text
AFL++ parent process
├── mutation and coverage scheduling
├── custom mutator callbacks
│   ├── PCBT screening
│   ├── transport arming
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

The target forkserver never consumes the SymAFL event pipe. The AFL++ parent
only drains raw bytes. The custom mutator owns frame decoding, semantic
interpretation, and PCBT insertion.

| Responsibility | Owner | Primary implementation path |
|---|---|---|
| Mutation, coverage scheduling, pipe drain, phase switch | AFL++ | `AFLplusplus/src/afl-forkserver.c`, `AFLplusplus/src/afl-fuzz.c` |
| Mutator lifecycle, screening, capture arming, decode, insertion | SymSan custom mutator | `symsan/driver/aflpp/symsan.cpp` |
| PCBT and predicate semantics | SymSan custom mutator | `symsan/driver/aflpp/pcbt.{hpp,cpp}`, `pred.{hpp,cpp}` |
| Trace control and DFSan propagation | SymSan runtime | `symsan/runtime/dfsan/dfsan.h`, runtime implementation |
| Condition-event export | SymSan backend | `symsan/backend/solver_common.cpp` |

## Runtime workflow and transport

### Initialization

Before the target forkserver starts, `afl_custom_init`:

1. requires executable `SYMAFL_CONCOLIC_TARGET` and `SYMAFL_CONCRETE_TARGET`;
2. enables PCBT mode and stores the concrete target path in AFL state;
3. creates the shared union-table and event-control objects;
4. creates a non-blocking pipe for full/suffix streams and assigns its read end
   to `afl->fsrv.sym_trace_fd`;
5. appends shared-memory names, sizes, and pipe fd to `TAINT_OPTIONS`; and
6. initializes the mutator's PCBT state.

The target inherits the pipe write end and shared-memory identifiers before its
forkserver initializes.

### Lifecycle-selected capture modes

| Internal mode | Lifecycle trigger | Channel | Exported conditions | Consumer |
|---|---|---|---|---|
| `SYMAFL_TRACE_FULL_STREAM` | initial corpus, empty tree, or admission without a concrete frontier | pipe | all symbolic conditions | `InsertTrace` |
| `SYMAFL_TRACE_SUFFIX_SHM` | admission at a known frontier | bounded SHM | events after `skip_depth` | `InsertSuffix` after coverage gain |
| `SYMAFL_TRACE_SUFFIX_PIPE` | SHM overflow and confirmed coverage gain | pipe replay | events after `skip_depth` | `InsertSuffix` |
| `SYMAFL_TRACE_OFF` | no armed capture | none | none | none |

`SYMAFL_TRACE_MODE` is intentionally ignored: runtime lifecycle, not a user
override, selects the production transport.

### Bootstrap and steady state

```text
Bootstrap
post_process -> tree empty / no concrete frontier -> arm full pipe stream
child runs -> writes condition frames -> AFL++ parent drains pipe
post_run -> mutator decodes frames -> InsertTrace
queue_get -> mark bootstrap complete

Known frontier
post_process -> CheckInput -> admit frontier -> arm SHM suffix at parent.depth
child runs -> writes only post-frontier events to SHM
no coverage gain -> next post_process increments rCnt and discards capture
coverage gain -> queue_new_entry inserts SHM suffix
              -> overflow replays same queue bytes through pipe suffix, then inserts
```

The parent waits on both forkserver status and the optional trace pipe. It drains
until `EAGAIN` into a dynamically grown byte buffer, resets the buffer at the
start of the next target execution, and does not decode frames. This prevents a
child blocked on a full pipe from deadlocking while its parent waits for child
status.

A vetoed candidate triggers saturation evaluation. When all evaluable paths are
exhausted, the mutator disables screening and sets `pcbt_switch_pending`; AFL++
owns forkserver replacement, coverage reset, recalibration, and scheduler
resumption.

### Framing and failure behavior

The reviewed mutator inserts only `cond_type` messages with nonzero,
non-initializing labels. It recognizes lengths for selected non-condition frames
only to preserve framing alignment. Memerr events are not currently bound to
PCBT findings.

- Invalid pipe framing increments `failed_runs` and aborts that insertion.
- Invalid SHM labels abort suffix insertion.
- SHM overflow replays with pipe suffix only after confirmed coverage gain.
- A failed replay increments `failed_runs` and leaves the tree unchanged.
- Timeout policy is not implemented merely because an introspection field exists.

## PCBT model and screening

### Tree and edge states

PCBT is a binary trie over symbolic branch outcomes. A node stores:

```text
cid
predicate
child[2]
rCnt[2]
depth
```

Nodes live in one Tree-owned, index-addressed arena. `child[d]` is a 32-bit
node reference: `0` means unexplored and the reserved reference `1` is the
single global Terminal node. The virtual root has no predicate and
`root.child[0]` is the sole entry slot for the first symbolic condition, so
compatible first conditions require a deterministic target. `rCnt[d]` is an
8-bit saturating retry count; its configured limit is therefore `0..255`.

| Edge state | Representation | Screening meaning |
|---|---|---|
| Unexplored | `child[d] == 0` | frontier |
| Next node | `child[d] > 1` | continue walking |
| Terminal | `child[d] == 1` | explored; veto |

An empty suffix changes an unexplored edge to Terminal.

### Trace insertion

`InsertTrace` walks an existing prefix by `(cid, result)` until a missing edge.
A mismatched `cid` or attempt to extend a terminal edge is a conflict and stops
insertion. The remaining events become new nodes through one `RunConverter`
whose per-run label memo writes into the Tree-owned shared predicate arena.
This is the only insertion path that checks prefix `cid` consistency.

`InsertSuffix(parent, direction, events, ...)` attaches after a previously
saved frontier without replaying the prefix. It is valid only if the caller has
proved that:

1. `parent` is a current tree node reference;
2. `direction` is 0 or 1;
3. `parent->child[direction]` is unexplored;
4. the saved candidate reached that exact frontier in the execution that
   produced the suffix;
5. screening, skip-depth, export, and insertion use the same event filter; and
6. no intervening tree mutation invalidated the saved node.

The API writes `cur->child[dir] = raw`; violating the unexplored-edge condition
can overwrite reachable topology. Tests must reject duplicate or replayed suffix
attempts before this API is called.

### Candidate screening, retry counts, and saturation

`CheckInput` evaluates predicates from the first node and takes one of five
outcomes:

1. opaque predicate: admit conservatively without a frontier,
   so the mutator arms a full trace;
2. failed concrete evaluation (for example, a read past the candidate end):
   admit conservatively without choosing a direction;
3. known child: continue walking;
4. terminal edge: veto; or
5. unexplored edge: admit while `rCnt[d] < rlimit` and return its parent and
   direction as the frontier.

`rCnt[d]` counts admitted attempts at a frontier direction that did not create a
new queue entry. The following candidate's `post_process` updates the count from
saved state.

The tree is saturated only when each evaluable direction is backed by a
saturated subtree, terminal, or an unexplored frontier whose retry count reached
the limit. An opaque predicate prevents precise saturation through its node.

If predicate evaluation fails because a candidate read exceeds its length, it
is an explicit conservative admission. It never selects an invented direction
and therefore cannot cause a veto.

## Predicate model and semantic boundary

A Tree owns one append-only post-order `PredArena`; a `RunConverter` maps the
current run's union-table labels into it. Each PCBT node carries a lightweight
`Predicate` view consisting of a root index, opacity flag, and input-read
ranges. Failed conversion of one root rolls back that root's partial arena
append and does not make later roots in the same trace opaque.

The admitted scalar grammar supports integer bit-vectors up to 64 bits:

- reads and constants;
- add/sub/mul, signed and unsigned div/rem;
- shifts and bitwise operations;
- integer comparisons; and
- zero/sign extension, extraction, and concatenation.

It also supports a direct `fmemcmp` result compared with zero when the DFSan
label records at most eight bytes. Its canonical `-1/0/+1` byte-lexicographic
result preserves the C sign contract for that use. Wider `fmemcmp`, indirect
uses of its sign-only result, floating point, and string-theory labels remain
outside this grammar and must be conservatively admitted or rejected by target
preflight; they are never assigned an invented value.

Unsupported, malformed, too-wide, or resource-bounded conversions become
opaque. Conversion is iterative, so expression nesting has no call-stack depth
limit; a failed root rolls back only its own append and cannot poison later
roots in the same trace. The
interpreter uses fixed-width masking, SMT-style divide-by-zero behavior, and
shift-by-width semantics. Reads are little-endian and at most eight bytes. It
must never silently truncate or invent semantics for unsupported expressions.

`eval_predicate` starts at the requested root and executes only its reachable
DAG with an iterative post-order work stack and sparse value scratch. One
`CheckInput` shares that scratch across all roots visited for its candidate, so
common PNodes from a captured trace are evaluated once. Unrelated earlier arena
nodes are neither evaluated nor allowed to affect the predicate result.

## System invariants

1. Bootstrap uses full pipe; steady-state frontier execution uses SHM suffix;
   only overflow plus coverage gain uses pipe suffix.
2. Suffix modes suppress event export only, never target execution, DFSan
   propagation, or label construction.
3. The AFL++ parent drains pipe bytes and the mutator is their sole semantic
   consumer.
4. `CheckInput` owns the frontier parent, direction, and depth later used for
   suffix capture and insertion.
5. Concolic and concrete phases use separate coverage-derived state.
6. Opaque predicates are conservatively admitted and prevent precise saturation.
7. Deterministic targets are required. Conflicting full traces are discarded;
   suffix insertion cannot diagnose prefix drift.
8. AFL++ changes remain limited to scheduling, pipe drain, phase switching, and
   the related coverage-state reset. PCBT policy, predicates, and trace insertion
   remain in SymSan.

Use [evaluation.md](evaluation.md) for experiment design, configuration,
verification criteria, and reproducibility requirements. Use
[status.md](status.md) for the current code-path mapping, recorded results, and
durable engineering gaps.
