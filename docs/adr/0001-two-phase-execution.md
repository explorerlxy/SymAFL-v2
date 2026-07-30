# ADR 0001: Two-Phase Concolic-to-Concrete Execution

- Status: Accepted
- Scope: system architecture

## Context

Running the concolic target indefinitely imposes DFSan overhead after PCBT can
no longer identify useful unexplored frontiers. Reusing a concrete coverage map
for a differently instrumented target would also be invalid.

## Decision

Use two local target builds in temporal phases:

1. concolic target during PCBT construction and screening;
2. concrete AFL++ target after PCBT saturation.

Retain queue files across the transition, but recreate coverage-derived state
and recalibrate the retained queue in the concrete coverage universe.

## Consequences

- PCBT mode requires both target paths at startup.
- AFL++ needs a constrained scheduler/forkserver integration.
- End-to-end phase-switch verification is mandatory.
- Queue identity and coverage identity must be documented separately.
