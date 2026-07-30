# PCBT and Predicate Semantics

## Tree model

The tree is a binary trie over symbolic branch outcomes. A node stores:

```text
cid
predicate
child[2]
terminal[2]
rCnt[2]
id
depth
```

The virtual root has no predicate. `root.child[0]` is the single entry slot for
the first symbolic condition. This assumes deterministic targets reach a
compatible first symbolic condition.

## Edge states

Each direction has exactly one semantic state:

| State | Representation | Screening meaning |
|---|---|---|
| Unexplored | `child[d] == nullptr && !terminal[d]` | frontier |
| Next node | `child[d] != nullptr` | continue walking |
| Terminal | `child[d] == nullptr && terminal[d]` | explored; veto |

An empty suffix transitions an unexplored edge to Terminal.

## Full-trace insertion

`InsertTrace` walks existing nodes by `(cid, result)` until it finds a missing
edge. If an existing node has a different `cid`, or the path attempts to extend
a terminal edge, insertion records a conflict and stops. Remaining events are
converted into new nodes using one `RunConverter` and one shared predicate arena
for that trace.

Full-trace insertion is the only insertion path that checks the known prefix for
`cid` conflicts.

## Suffix insertion

`InsertSuffix` directly attaches new nodes at a saved frontier. It deliberately
performs no prefix replay and no conflict check. This is a semantic-preserving
optimization only under the frontier-prefix invariant defined in
`RUNTIME_PROTOCOL.md`.

Because the implementation writes `cur->child[dir] = raw`, violating the
unexplored-edge precondition can overwrite the reachable topology. Tests must
cover duplicate/replayed suffix attempts and reject them before this API is
called.

## Screening

`CheckInput` evaluates predicates from the first node until one of four outcomes:

1. **Opaque or missing predicate arena:** admit conservatively without a
   frontier node; the mutator uses a full trace.
2. **Known child:** continue.
3. **Terminal edge:** veto.
4. **Unexplored edge:** admit only while `rCnt[d] < rlimit`, and return the
   frontier parent/direction.

If `eval_predicate` fails because a read exceeds the candidate length, the
current implementation chooses direction `0`; it does not perform an opaque
admission. This behavior is part of current code and requires a directed test
because it can affect screening decisions for short inputs.

## rCnt and saturation

`rCnt[d]` counts admitted attempts for a frontier direction that did not create
a new queue entry. The increment happens when the next candidate reaches
`post_process`, using state saved for the previous admitted input.

A tree is saturated only when every evaluable direction is one of:

- backed by a saturated subtree;
- terminal; or
- an unexplored frontier whose `rCnt` reached the limit.

An opaque predicate returns `false` from saturation checks, so precise PCBT
saturation cannot be declared through that node.

## Predicate representation

A `RunConverter` turns SymSan union-table labels into a shared post-order arena.
A tree node stores a lightweight `Predicate` view:

```text
shared arena + root index + opaque flag + input-read ranges
```

Supported operations are integer bit-vector operations up to 64 bits:

- reads and constants;
- add/sub/mul, signed and unsigned div/rem;
- shifts and bitwise operations;
- integer comparisons;
- zero/sign extension, extraction, concatenation.

Unsupported, too-wide, too-deep, or oversized conversions become opaque.

## Current evaluator semantics

The interpreter implements fixed-width masking, SMT-style divide-by-zero
results, and shift-by-width behavior. Reads are little-endian and limited to at
most eight bytes.

Two implementation details need explicit regression coverage:

1. `RunConverter::overflow_` is shared across all predicates converted by one
   run. Once an unsupported subtree sets it, later predicates from the same
   converter also become opaque.
2. `eval_predicate` evaluates every arena node from index `0` through `root`,
   not only the root's reachable subtree. Because the arena is shared by several
   branch predicates, an earlier unrelated read may affect evaluation of a
   later predicate. This should be validated with disjoint-subtree tests before
   relying on the optimization.

These are current code properties, not intended architectural guarantees.

## Determinism requirements

PCBT assumes stable symbolic branch order for the same input and compatible
predicate meaning for a node along its path prefix. Non-deterministic traces may
be rejected by full insertion, but suffix insertion cannot detect prefix drift.
Use deterministic targets and include replay/bitmap equivalence checks in any
experiment that depends on suffix correctness.
