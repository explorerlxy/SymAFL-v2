# ADR 0003: Frontier-Anchored Suffix Insertion

- Status: Accepted
- Scope: PCBT insertion

## Context

Screening already identifies the existing path prefix, frontier parent,
direction, and symbolic depth. Re-transmitting and re-matching that prefix for a
coverage-gaining input is redundant.

## Decision

Export only condition events after the saved frontier depth and call
`InsertSuffix(parent, direction, suffix)` directly. The concolic child still
executes from program entry and performs complete DFSan propagation and label
construction.

Represent a suffix with no later symbolic condition as a Terminal edge.

## Correctness condition

The candidate's concolic execution must follow the same symbolic prefix used by
screening, with identical condition filtering and depth counting. The insertion
API does not revalidate this condition.

## Consequences

- Prefix serialization, pipe traffic, decoding, and root matching are removed
  from suffix insertion.
- Deterministic targets and replay-equivalence tests are required.
- The caller must reject insertion into a non-frontier edge.
